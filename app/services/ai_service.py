import json
from datetime import datetime
from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from typing import AsyncGenerator, List, Dict, Any
from app.database import db
import os

async def get_tools_for_user(user: dict):
    user_id = user.get("id")
    emp_no_id = user.get("employee_no_id")
    role = user.get("role", "employee").lower()
    name = user.get("name", "User")
    
    employee_mongo_id = None
    if emp_no_id:
        emp_record = await db["employees"].find_one({"employee_no_id": emp_no_id})
        if emp_record:
            employee_mongo_id = str(emp_record.get("_id"))
            
    identifiers = [id for id in [user_id, emp_no_id, name, employee_mongo_id] if id]

    @tool
    async def get_attendance() -> str:
        """Fetch recent attendance records for the user."""
        try:
            query = {}
            if role != "admin":
                query = {"employee_id": {"$in": identifiers}}
            
            # Sort by date descending
            records = await db["attendance"].find(query).sort("date", -1).limit(10).to_list(length=10)
            if not records:
                return "No attendance records found."
            
            summary = []
            for r in records:
                summary.append(f"Date: {r.get('date')} | Clock In: {r.get('clock_in')} | Clock Out: {r.get('clock_out')} | Status: {r.get('status')} | Sub-Status: {r.get('attendance_status')}")
            return "\n".join(summary)
        except Exception as e:
            return f"Error fetching attendance: {str(e)}"


    @tool
    async def get_user_profile() -> str:
        """Get the current user's own profile and role details."""
        return f"Name: {name}\nRole: {role}\nEmployee ID: {emp_no_id}"

    return [get_attendance, get_user_profile]

async def chat_stream(query: str, history: list, user: dict) -> AsyncGenerator[str, None]:
    """Generates a streaming response using LangChain's AgentExecutor, incorporating conversation history."""
    
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        
    if not api_key:
        yield "Error: GEMINI_API_KEY or GOOGLE_API_KEY environment variable is not set on the server."
        return

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash", 
        google_api_key=api_key,
        temperature=0.2,
        streaming=True
    )
    
    tools = await get_tools_for_user(user)
    
    system_prompt = (
        "You are the FAIR-PAY AI Assistant. You help users manage their attendance and profile information. "
        "You have access to tools to fetch this data from the database. Always use the tools to answer questions about the user's data. "
        "If you do not find data via the tools, tell the user gracefully. Keep responses concise, professional, and helpful. "
        f"The current user's name is {user.get('name', 'User')} and their role is {user.get('role', 'employee')}."
    )
    
    agent = create_react_agent(llm, tools, prompt=system_prompt)

    try: 
        langchain_messages = []
        for msg in history:
            role = msg.get("role")
            content = msg.get("content")
            if role and content: 
                mapped_role = "human" if role == "user" else "assistant"
                langchain_messages.append((mapped_role, content))
                
        # Append the current query
        langchain_messages.append(("human", query))

        # LangGraph uses a different event streaming approach
        async for event in agent.astream_events(
            {"messages": langchain_messages},
            version="v2"
        ):
            kind = event["event"]
            if kind == "on_chat_model_stream":
                # We only want to yield the AI's direct responses, not the tool calling internal thoughts
                if "chunk" in event["data"]:
                    content = event["data"]["chunk"].content
                    if content and isinstance(content, str):
                        yield content
    except Exception as e:
        yield f"\n\n[Error communicating with AI: {str(e)}]"

