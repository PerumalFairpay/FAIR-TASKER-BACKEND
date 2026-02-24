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
    async def get_tasks() -> str:
        """Fetch tasks. Returns tasks assigned to the user, or all tasks if the user is an admin."""
        try:
            query = {}
            if role != "admin":
                query = {"assigned_to": {"$in": identifiers}}
            tasks = await db["tasks"].find(query).to_list(length=20)
            if not tasks:
                return "No tasks found."
            
            summary = []
            for t in tasks:
                summary.append(f"Task: {t.get('task_name')} | Status: {t.get('status')} | Priority: {t.get('priority')} | Due: {t.get('end_date')}")
            return "\n".join(summary)
        except Exception as e:
            return f"Error fetching tasks: {str(e)}"

    @tool
    async def get_projects() -> str:
        """Fetch projects the user is involved in."""
        try:
            query = {}
            if role != "admin":
                query = {
                    "$or": [
                        {"project_manager_ids": {"$in": identifiers}},
                        {"team_leader_ids": {"$in": identifiers}},
                        {"team_member_ids": {"$in": identifiers}}
                    ]
                }
            projects = await db["projects"].find(query).to_list(length=20)
            if not projects:
                return "No projects found."
            
            summary = []
            for p in projects:
                summary.append(f"Project: {p.get('name')} | Status: {p.get('status')} | End Date: {p.get('end_date')}")
            return "\n".join(summary)
        except Exception as e:
            return f"Error fetching projects: {str(e)}"

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
    async def get_leaves() -> str:
        """Fetch leave requests and balances for the user."""
        try:
            query = {}
            if role != "admin":
                query = {"employee_id": {"$in": identifiers}}
            
            records = await db["leave_requests"].find(query).sort("start_date", -1).limit(10).to_list(length=10)
            if not records:
                return "No leave requests found."
            
            summary = []
            for r in records:
                summary.append(f"Start: {r.get('start_date')} | End: {r.get('end_date')} | Days: {r.get('total_days')} | Reason: {r.get('reason')} | Status: {r.get('status')}")
            return "\n".join(summary)
        except Exception as e:
            return f"Error fetching leaves: {str(e)}"

    @tool
    async def get_expenses() -> str:
        """Fetch expenses submitted by the user."""
        try:
            # Note: If expenses don't have employee_id, this might need adjustment based on db schema.
            # Assuming expenses have some linkage. For now, just return a generic response or all if admin.
            if role != "admin":
                 # We will attempt to filter if a field exists, else we restrict it
                 return "Detailed personal expense lookup requires an explicit user mapping in the database. Contact admin."
            
            records = await db["expenses"].find({}).sort("date", -1).limit(10).to_list(length=10)
            if not records:
                return "No expenses found."
            
            summary = []
            for r in records:
                summary.append(f"Date: {r.get('date')} | Amount: {r.get('amount')} | Purpose: {r.get('purpose')}")
            return "\n".join(summary)
        except Exception as e:
            return f"Error fetching expenses: {str(e)}"

    @tool
    async def get_user_profile() -> str:
        """Get the current user's own profile and role details."""
        return f"Name: {name}\nRole: {role}\nEmployee ID: {emp_no_id}"

    return [get_tasks, get_projects, get_attendance, get_leaves, get_expenses, get_user_profile]

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
        "You are the FAIR-PAY AI Assistant. You help users manage their tasks, attendance, leaves, projects, and expenses. "
        "You have access to tools to fetch this data from the database. Always use the tools to answer questions about the user's data. "
        "If you do not find data via the tools, tell the user gracefully. Keep responses concise, professional, and helpful. "
        f"The current user's name is {user.get('name', 'User')} and their role is {user.get('role', 'employee')}."
    )
    
    agent = create_react_agent(llm, tools, prompt=system_prompt)

    try:
        # Format the history into LangChain message tuples
        langchain_messages = []
        for msg in history:
            role = msg.get("role")
            content = msg.get("content")
            if role and content:
                # LangGraph typically uses "human" instead of "user" for the HumanMessage role
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

