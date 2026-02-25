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
            
            # Exclude sensitive or internal fields
            exclude_fields = ["_id", "password", "hashed_password", "tokens"]
            
            details = [f"Full Profile Details for {emp_record.get('name', 'Employee')}:"]
            for key, value in emp_record.items():
                if key in exclude_fields:
                    continue
                
                # Format key for readability
                display_key = key.replace("_", " ").title()
                
                # Handle different value types
                if value is None:
                    details.append(f"{display_key}: N/A")
                elif isinstance(value, list):
                    details.append(f"{display_key}: {len(value)} items recorded")
                elif isinstance(value, dict):
                    details.append(f"{display_key}: {json.dumps(value)}")
                elif isinstance(value, datetime):
                    details.append(f"{display_key}: {value.strftime('%Y-%m-%d %H:%M:%S')}")
                else:
                    details.append(f"{display_key}: {value}")
            
            return "\n".join(details)
        except Exception as e:
            return f"Error: {str(e)}"

    @tool
    async def get_projects(status: str = None, search: str = None, employee_matcher: str = None) -> str:
        """Fetch projects. Employees see their own assigned projects. Admins see all projects.
        Admins can provide employee_matcher (name or employee ID) to see a specific employee's projects.
        Optional: filter by status (Planned/Active/Completed/On Hold) or search by project name."""
        try:
            query = {}
            # Resolve target identifiers: either the logged-in user or a looked-up employee
            target_ids = identifiers
            if role == "admin" and employee_matcher:
                emp = await db["employees"].find_one({
                    "$or": [
                        {"name": {"$regex": employee_matcher, "$options": "i"}},
                        {"employee_no_id": employee_matcher}
                    ]
                })
                if not emp:
                    return f"No employee found matching '{employee_matcher}'."
                emp_mongo_id = str(emp["_id"])
                target_ids = [i for i in [emp.get("employee_no_id"), emp_mongo_id, emp.get("name")] if i]

            if role != "admin" or employee_matcher:
                # Filter to projects where the target employee appears in any team field
                query = {
                    "$or": [
                        {"project_manager_ids": {"$in": target_ids}},
                        {"team_leader_ids": {"$in": target_ids}},
                        {"team_member_ids": {"$in": target_ids}},
                    ]
                }

            if status:
                query["status"] = {"$regex": status, "$options": "i"}
            if search:
                query["name"] = {"$regex": search, "$options": "i"}

            projects = await db["projects"].find(query).sort("created_at", -1).limit(20).to_list(length=20)
            if not projects:
                return "No projects found."

            lines = []
            for p in projects:
                name = p.get("name", "Unnamed")
                st = p.get("status", "N/A")
                priority = p.get("priority", "N/A")
                start = p.get("start_date", "N/A")
                end = p.get("end_date", "N/A")
                budget = p.get("budget", 0)
                currency = p.get("currency", "")
                lines.append(f"Project: {name} | Status: {st} | Priority: {priority} | Dates: {start} → {end} | Budget: {currency} {budget}")
            return f"Found {len(lines)} project(s):\n" + "\n".join(lines)
        except Exception as e:
            return f"Error: {str(e)}"

    @tool
    async def get_tasks(status: str = None, priority: str = None, project_name: str = None, employee_matcher: str = None, include_old: bool = False) -> str:
        """Fetch tasks. Employees see tasks assigned to them. Admins see all tasks.
        Admins can provide employee_matcher (name or employee ID) to see a specific employee's tasks.
        By default shows only active/upcoming tasks. Set include_old=True to include old completed records.
        Optional filters: status (Todo/In Progress/Done/Overdue), priority (Low/Medium/High/Critical), project name."""
        try:
            from datetime import timedelta
            query = {}
            # Resolve target identifiers: either the logged-in user or a looked-up employee
            target_ids = identifiers
            if role == "admin" and employee_matcher:
                emp = await db["employees"].find_one({
                    "$or": [
                        {"name": {"$regex": employee_matcher, "$options": "i"}},
                        {"employee_no_id": employee_matcher}
                    ]
                })
                if not emp:
                    return f"No employee found matching '{employee_matcher}'."
                emp_mongo_id = str(emp["_id"])
                target_ids = [i for i in [emp.get("employee_no_id"), emp_mongo_id, emp.get("name")] if i]

            if role != "admin" or employee_matcher:
                query = {"assigned_to": {"$in": target_ids}}

            if status:
                query["status"] = {"$regex": status, "$options": "i"}
            elif not include_old:
                # Default: exclude tasks that are fully done AND older than 30 days
                cutoff = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
                query["$or"] = [
                    {"status": {"$nin": ["Done", "Completed"]}},      # Still active
                    {"end_date": {"$gte": cutoff}}                     # OR completed recently
                ]

            if priority:
                query["priority"] = {"$regex": priority, "$options": "i"}
            if project_name:
                proj = await db["projects"].find_one({"name": {"$regex": project_name, "$options": "i"}})
                if proj:
                    query["project_id"] = str(proj["_id"])
                else:
                    return f"No project found matching '{project_name}'."

            tasks = await db["tasks"].find(query).sort("end_date", 1).limit(20).to_list(length=20)
            if not tasks:
                return "No tasks found." + ("" if include_old or status else " (Showing active tasks only. Ask to include old records if needed.)")

            lines = []
            for t in tasks:
                tname = t.get("task_name", "Unnamed")
                st = t.get("status", "N/A")
                pri = t.get("priority", "N/A")
                prog = t.get("progress", 0)
                end = t.get("end_date", "N/A")
                lines.append(f"Task: {tname} | Status: {st} | Priority: {pri} | Progress: {prog}% | Due: {end}")
            return f"Found {len(lines)} task(s):\n" + "\n".join(lines)
        except Exception as e:
            return f"Error: {str(e)}"

    @tool
    async def get_assets(employee_matcher: str = None) -> str:
        """Fetch assets assigned to the current employee. Admins can provide an employee name or ID to look up their assets, or leave empty to see all assets."""
        try:
            if role == "admin":
                if employee_matcher:
                    emp = await db["employees"].find_one({
                        "$or": [
                            {"name": {"$regex": employee_matcher, "$options": "i"}},
                            {"employee_no_id": employee_matcher}
                        ]
                    })
                    if not emp:
                        return f"No employee found matching '{employee_matcher}'."
                    target_id = str(emp["_id"])
                    query = {"assigned_to": target_id}
                else:
                    query = {}  # Admins see all assets
            else:
                query = {"assigned_to": {"$in": identifiers}}

            assets = await db["assets"].find(query).sort("created_at", -1).limit(20).to_list(length=20)
            if not assets:
                return "No assets found."

            lines = []
            for a in assets:
                aname = a.get("asset_name", "Unnamed")
                status = a.get("status", "N/A")
                condition = a.get("condition", "N/A")
                model = a.get("model_no", "N/A")
                serial = a.get("serial_no", "N/A")
                warranty = a.get("warranty_expiry", "N/A")
                lines.append(f"Asset: {aname} | Status: {status} | Condition: {condition} | Model: {model} | Serial: {serial} | Warranty Expiry: {warranty}")
            return f"Found {len(lines)} asset(s):\n" + "\n".join(lines)
        except Exception as e:
            return f"Error: {str(e)}"

    @tool
    async def get_expenses(start_date: str = None, end_date: str = None, employee_matcher: str = None) -> str:
        """Fetch expense records. Employees see their own expenses. Admins can provide an employee name/ID or leave empty to see all. Optionally filter by date range (YYYY-MM-DD)."""
        try:
            if role == "admin":
                if employee_matcher:
                    emp = await db["employees"].find_one({
                        "$or": [
                            {"name": {"$regex": employee_matcher, "$options": "i"}},
                            {"employee_no_id": employee_matcher}
                        ]
                    })
                    if not emp:
                        return f"No employee found matching '{employee_matcher}'."
                    target_ids = [str(emp["_id"]), emp.get("employee_no_id")]
                    target_ids = [i for i in target_ids if i]
                    query = {"employee_id": {"$in": target_ids}}
                else:
                    query = {}  # Admins see all expenses
            else:
                query = {"employee_id": {"$in": identifiers}}

            if start_date:
                query.setdefault("date", {})["$gte"] = start_date
            if end_date:
                query.setdefault("date", {})["$lte"] = end_date

            expenses = await db["expenses"].find(query).sort("date", -1).limit(20).to_list(length=20)
            if not expenses:
                return "No expense records found."

            total = sum(e.get("amount", 0) for e in expenses)
            lines = []
            for e in expenses:
                amt = e.get("amount", 0)
                purpose = e.get("purpose", "N/A")
                payment_mode = e.get("payment_mode", "N/A")
                date = e.get("date", "N/A")
                lines.append(f"Date: {date} | Amount: {amt} | Purpose: {purpose} | Payment: {payment_mode}")
            return f"Found {len(lines)} expense(s). Total: {total:.2f}\n" + "\n".join(lines)
        except Exception as e:
            return f"Error: {str(e)}"

    @tool
    async def get_leaves(employee_matcher: str = None) -> str:
        """Fetch leave records including approved, available, and rejected leaves. Admins can provide an employee name or ID."""
        try:
            target_ids = identifiers
            target_name = name
            if role == "admin" and employee_matcher:
                emp = await db["employees"].find_one({
                    "$or": [
                        {"name": {"$regex": employee_matcher, "$options": "i"}},
                        {"employee_no_id": employee_matcher}
                    ]
                })
                if not emp:
                    return f"No employee found matching '{employee_matcher}'."
                emp_mongo_id = str(emp["_id"])
                target_ids = [i for i in [emp.get("employee_no_id"), emp_mongo_id, emp.get("name")] if i]
                target_name = emp.get("name", employee_matcher)

            # 1. Fetch all leave types
            leave_types = await db["leave_types"].find({"status": "Active"}).to_list(length=100)
            if not leave_types:
                return "No active leave types found in the system."

            # 2. Fetch all leave requests for the target employee
            leave_requests = await db["leave_requests"].find({"employee_id": {"$in": target_ids}}).to_list(length=100)
            
            # 3. Calculate used days per leave type (only Approved)
            used_days = {} # leave_type_id -> total_days
            history_lines = []
            
            for req in leave_requests:
                lt_id = str(req.get("leave_type_id"))
                status = req.get("status", "Pending")
                days = req.get("total_days", 0)
                
                if status == "Approved":
                    used_days[lt_id] = used_days.get(lt_id, 0) + days
                
                # Add to history
                date_range = f"{req.get('start_date')} to {req.get('end_date')}"
                if req.get('start_date') == req.get('end_date'):
                    date_range = req.get('start_date')
                
                reason = f" | Reason: {req.get('rejection_reason')}" if status == "Rejected" and req.get("rejection_reason") else ""
                history_lines.append(f"- {date_range}: {status} ({days} days){reason}")

            # 4. Generate summary
            summary = [f"Leave Status for {target_name}:"]
            summary.append("\nAvailable Balance:")
            for lt in leave_types:
                lt_id = str(lt["_id"])
                lt_name = lt.get("name")
                allowed = lt.get("number_of_days", 0)
                used = used_days.get(lt_id, 0)
                available = allowed - used
                summary.append(f"- {lt_name}: {available} days remaining (Allowed: {allowed}, Used: {used})")
            
            if history_lines:
                summary.append("\nRecent Leave History:")
                summary.extend(history_lines[-10:]) # Show last 10
            else:
                summary.append("\nNo leave history found.")
                
            return "\n".join(summary)
        except Exception as e:
            return f"Error: {str(e)}"

    tools = [get_attendance, get_user_profile, get_projects, get_tasks, get_assets, get_expenses, get_leaves]
    
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
        "You are the FAIR-PAY AI Assistant, but you're also a friendly buddy! 🚀 You help users manage their work data like attendance, profile, projects, tasks, assets, expenses, and leaves. "
        "You have access to tools to fetch this data from the database. Always use the tools to answer questions about data. "
        "For leave queries, use the 'get_leaves' tool to show available balance, approved leaves, and rejected leaves (with reasons). "
        "If you are an admin, you can use parameters in tools to search for other employees' data. "
        "If you do not find data via the tools, tell the user nicely with a bit of humor. Keep responses friendly, funny, and use emojis to keep things lively! ✨ "
        f"The current user's name is {user.get('name', 'User')} and their role is {user.get('role', 'employee')}."
        f"\nIMPORTANT: The current date and time is {today}."
    )
    
    agent = create_react_agent(llm, tools, prompt=system_prompt)

    try: 
        # Trim history to last 10 messages to keep token count low and responses fast
        MAX_HISTORY = 5
        trimmed_history = history[-MAX_HISTORY:] if len(history) > MAX_HISTORY else history

        langchain_messages = []
        for msg in trimmed_history:
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
                    # content can be a plain string (direct answer) OR
                    # a list of content parts (after a tool call with Gemini)
                    if isinstance(content, str) and content:
                        yield content
                    elif isinstance(content, list):
                        # Extract text from each part in the list
                        for part in content:
                            if isinstance(part, dict) and part.get("type") == "text":
                                text = part.get("text", "")
                                if text:
                                    yield text
    except Exception as e:
        yield f"\n\n[Error communicating with AI: {str(e)}]"

