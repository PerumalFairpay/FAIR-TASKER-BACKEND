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

from bson import ObjectId

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
            
    # Common identifiers for filtering
    identifiers = [id for id in [user_id, emp_no_id, name, employee_mongo_id] if id]

    today = datetime.now().strftime("%Y-%m-%d")

    @tool
    async def get_attendance(employee_matcher: str = None, date: str = None) -> str:
        """Fetch attendance records. Use format 'YYYY-MM-DD' for a specific date. Admins can provide an employee name or ID."""
        try:
            query = {}
            if role != "admin":
                query = {"employee_id": {"$in": identifiers}}
            elif employee_matcher:
                emp = await db["employees"].find_one({
                    "$or": [
                        {"name": {"$regex": employee_matcher, "$options": "i"}},
                        {"employee_no_id": employee_matcher}
                    ]
                })
                if emp:
                    emp_id = str(emp["_id"])
                    query = {"employee_id": {"$in": [emp_id, emp.get("employee_no_id")]}}
                else:
                    return f"No employee found matching '{employee_matcher}'"
            
            if date:
                query["date"] = date
            
            records = await db["attendance"].find(query).sort("date", -1).limit(10).to_list(length=10)
            if not records: 
                msg = f"No attendance records found"
                if date: msg += f" for {date}"
                return msg + f". (Current Date: {today})"
            
            summary = [f"Date: {r.get('date')} | Status: {r.get('status')} | In: {r.get('clock_in')} | Out: {r.get('clock_out')}" for r in records]
            return f"(Today is {today})\n" + "\n".join(summary)
        except Exception as e:
            return f"Error: {str(e)}"

    @tool
    async def get_user_profile(employee_matcher: str = None) -> str:
        """Get profile details. Admins can provide an employee name or ID."""
        try:
            target_emp_no = emp_no_id
            if role == "admin" and employee_matcher:
                emp = await db["employees"].find_one({
                    "$or": [
                        {"name": {"$regex": employee_matcher, "$options": "i"}},
                        {"employee_no_id": employee_matcher}
                    ]
                })
                if not emp: return f"Employee '{employee_matcher}' not found."
                target_emp_no = emp.get("employee_no_id")

            emp_record = await db["employees"].find_one({"employee_no_id": target_emp_no})
            if not emp_record: return "Profile not found."
            
            details = [
                f"Name: {emp_record.get('name')}",
                f"Role: {emp_record.get('role')}",
                f"Employee ID: {emp_record.get('employee_no_id')}",
                f"Email: {emp_record.get('email')}",
                f"Department: {emp_record.get('department')}",
                f"Designation: {emp_record.get('designation')}",
                f"Status: {emp_record.get('status')}",
                f"Joining Date: {emp_record.get('date_of_joining')}"
            ]
            return "\n".join(details)
        except Exception as e:
            return f"Error: {str(e)}"

    tools = [get_attendance, get_user_profile]
    if role == "admin":
        tools.append(search_employees)
    
    return tools

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
    
    today = datetime.now().strftime("%Y-%m-%d, %A")
    system_prompt = (
        "You are the FAIR-PAY AI Assistant. You help users manage their attendance and profile information. "
        "You have access to tools to fetch this data from the database. Always use the tools to answer questions about data. "
        "If you are an admin, you can use parameters in tools to search for other employees' data and profiles. "
        "If you do not find data via the tools, tell the user gracefully. Keep responses concise, professional, and helpful. "
        f"The current user's name is {user.get('name', 'User')} and their role is {user.get('role', 'employee')}."
        f"\nIMPORTANT: The current date and time is {today}."
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

