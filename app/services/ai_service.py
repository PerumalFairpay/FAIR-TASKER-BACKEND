import json
from datetime import datetime
from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent
from langchain_core.prompts import ChatPromptTemplate
from typing import AsyncGenerator, List, Dict, Any, Optional
import os
from bson import ObjectId
from langchain_core.tools import tool

from app.database import employees_collection
from app.services.api import (
    EmployeeService,
    DepartmentService,
    ShiftService,
    LeaveTypeService,
    DocumentCategoryService,
    LeaveRequestService,
    DocumentService,
    HolidayService,
    BlogService,
    AttendanceService,
    AssetService
)
from app.services.vector_store import vector_store_service


async def get_tools_for_user(user: dict):
    """Returns tools based on user roles and data access permissions."""
    role = user.get("role", "employee")
    emp_no_id = user.get("employee_no_id")

    @tool
    async def list_employees(
        include_all_profile_details: bool = False,
        search: Optional[str] = None,
        status: Optional[str] = None,
        role_filter: Optional[str] = None,
        work_mode: Optional[str] = None,
        shift_id: Optional[str] = None,
        gender: Optional[str] = None,
        marital_status: Optional[str] = None,
        designation: Optional[str] = None,
        department: Optional[str] = None,
        employee_type: Optional[str] = None,
        limit: int = 50
    ):
        """
        Retrieves a filtered list of employees including their profile details.
        """
        if role != "admin":
            return "Access Denied: You do not have permission to view other employees' details. You can only view your own details using get_my_details."
        try:
            if not include_all_profile_details and not any([search, status, role_filter, work_mode, shift_id, gender, marital_status, designation, department, employee_type]):
                summary, err = await EmployeeService.get_all_summary()
                return summary if summary is not None else []
            
            employees, _, err = await EmployeeService.list(
                limit=limit,
                search=search,
                status=status,
                role=role_filter,
                work_mode=work_mode,
                shift_id=shift_id,
                gender=gender,
                marital_status=marital_status,
                designation=designation,
                department=department,
                employee_type=employee_type
            )
            if err:
                return f"Error: {err}"

            cleaned_employees = []
            for emp in (employees or []):
                clean_emp = {k: v for k, v in emp.items() if v is not None and k not in ["_id", "id", "hashed_password", "password", "onboarding_checklist", "offboarding_checklist", "documents", "created_at", "updated_at"]}
                if emp.get("onboarding_checklist"):
                    completed = sum(1 for item in emp["onboarding_checklist"] if item.get("status") == "Completed")
                    clean_emp["onboarding_status"] = f"{completed}/{len(emp['onboarding_checklist'])} completed"
                cleaned_employees.append(clean_emp)
            
            return cleaned_employees
        except Exception as e:
            return f"Error listing filtered employees: {str(e)}"

    @tool
    async def get_my_details():
        """
        Retrieves your own comprehensive profile details, including personal info,
        task metrics, leave balances, attendance stats, assigned projects, and assets.
        """
        try:
            employee = await employees_collection.find_one({"employee_no_id": emp_no_id, "is_deleted": {"$ne": True}})
            if not employee:
                return "Your employee record could not be found."
            
            emp_id = str(employee["_id"])
            
            profile, _ = await EmployeeService.get(emp_id)
            leave_summary, _ = await EmployeeService.get_leave_balances(emp_id)
            task_metrics, _ = await EmployeeService.get_task_metrics(emp_id)
            attendance_stats, _ = await EmployeeService.get_attendance_stats(emp_id)
            assigned_projects, _ = await EmployeeService.get_assigned_projects(emp_id)
            assigned_assets, _ = await AssetService.get_by_employee(emp_id)

            return {
                "profile": profile,
                "leave_summary": leave_summary,
                "task_metrics": task_metrics,
                "attendance_stats": attendance_stats,
                "assigned_projects": assigned_projects,
                "assigned_assets": assigned_assets
            }
        except Exception as e:
            return f"Error fetching your details: {str(e)}"

    @tool
    async def get_any_employee_details(search_query: str):
        """
        Retrieves full details for a specific employee identified by name, email, mobile, or ID.
        """
        if role != "admin":
            return "Access Denied: You do not have permission to view other employees' details. You can only view your own details using get_my_details."
        try:
            employees, _, err = await EmployeeService.list(search=search_query, limit=1)
            if not employees:
                return f"No employee found matching '{search_query}'"
            
            emp = employees[0]
            emp_id = emp["id"]

            profile, _ = await EmployeeService.get(emp_id)
            leave_summary, _ = await EmployeeService.get_leave_balances(emp_id)
            task_metrics, _ = await EmployeeService.get_task_metrics(emp_id)
            attendance_stats, _ = await EmployeeService.get_attendance_stats(emp_id)
            assigned_projects, _ = await EmployeeService.get_assigned_projects(emp_id)
            assigned_assets, _ = await AssetService.get_by_employee(emp_id)

            return {
                "profile": profile,
                "leave_summary": leave_summary,
                "task_metrics": task_metrics,
                "attendance_stats": attendance_stats,
                "assigned_projects": assigned_projects,
                "assigned_assets": assigned_assets
            }
        except Exception as e:
            return f"Error fetching employee details: {str(e)}"

    @tool
    async def get_organization_metadata():
        """
        Retrieves reference information about the organization, such as lists of 
        Departments, Shifts, and Leave Types.
        """
        try:
            shifts, _ = await ShiftService.list()
            departments, _ = await DepartmentService.list()
            leave_types, _ = await LeaveTypeService.list()
            doc_categories, _ = await DocumentCategoryService.list()
            
            return {
                "shifts": [{"id": s["id"], "name": s["name"], "time": f"{s.get('start_time')}-{s.get('end_time')}"} for s in (shifts or [])],
                "departments": [{"id": d["id"], "name": d["name"]} for d in (departments or [])],
                "leave_types": [{"id": lt["id"], "name": lt["name"], "days": lt.get("number_of_days")} for lt in (leave_types or [])],
                "document_categories": [{"id": dc["id"], "name": dc["name"]} for dc in (doc_categories or [])]
            }
        except Exception as e:
            return f"Error fetching organization metadata: {str(e)}"

    @tool
    async def list_leave_requests(
        employee_id: Optional[str] = None,
        status: Optional[str] = "Pending",
        date: Optional[str] = None
    ):
        """
        Retrieves a list of leave requests from employees.
        """
        try:
            if role != "admin":
                employee = await employees_collection.find_one({"employee_no_id": emp_no_id, "is_deleted": {"$ne": True}})
                if not employee:
                    return "Could not identify your employee record to list leaves."
                employee_id = str(employee["_id"])
                
            leaves, _, err = await LeaveRequestService.list(employee_id=employee_id, status=status, date=date)
            if err:
                return f"Error: {err}"
            return leaves
        except Exception as e:
            return f"Error listing leave requests: {str(e)}"

    @tool
    async def list_documents(
        search: Optional[str] = None,
        status: Optional[str] = "Active"
    ):
        """
        Retrieves a list of company documents.
        """
        try:
            if role != "admin":
                status = "Active"
            docs, err = await DocumentService.list(status=status, search=search)
            if err:
                return f"Error: {err}"
            return docs
        except Exception as e:
            return f"Error listing documents: {str(e)}"

    @tool
    async def search_document_content(
        query: str,
        category_id: Optional[str] = None,
        limit: int = 5
    ):
        """
        Searches INSIDE the actual text content of company documents for answers to questions.
        """
        try:
            filter_dict = {"category_id": category_id} if category_id else {}
            
            if role != "admin":
                active_docs, _ = await DocumentService.list(status="Active")
                active_doc_ids = [str(doc["id"]) for doc in (active_docs or [])]
                if not active_doc_ids:
                    return "No relevant active documents found to search."
                filter_dict["document_id"] = active_doc_ids

            results = await vector_store_service.search_documents(query=query, filter_dict=filter_dict, limit=limit)
            
            if not results:
                return f"No relevant information found inside documents for '{query}'."
            
            return results
        except Exception as e:
            return f"Error searching document content: {str(e)}"

    @tool
    async def list_holidays():
        """
        Retrieves a list of all company holidays.
        """
        try:
            holidays, err = await HolidayService.list()
            if err:
                return f"Error: {err}"
            return holidays
        except Exception as e:
            return f"Error listing holidays: {str(e)}"

    @tool
    async def list_blogs(search_query: Optional[str] = None, page: int = 1, limit: int = 10):
        """
        Retrieves a list of company blog posts or announcements.
        """
        try:
            blogs, _, err = await BlogService.list(page=page, limit=limit, search=search_query)
            if err:
                return f"Error: {err}"
            return blogs
        except Exception as e:
            return f"Error listing blogs: {str(e)}"

    @tool
    async def list_attendance(
        date: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        employee_id: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        limit: int = 50
    ):
        """
        Retrieves a list of attendance records for all employees or filtered by date, employee, or status.
        Only admins have permission to use this tool.
        """
        if role != "admin":
            return "Access Denied: You do not have permission to view other employees' attendance records."
        try:
            records, _, err = await AttendanceService.get_all(
                date=date,
                start_date=start_date,
                end_date=end_date,
                employee_id=employee_id,
                status=status,
                page=page,
                limit=limit
            )
            if err:
                return f"Error: {err}"
            return records
        except Exception as e:
            return f"Error fetching attendance records: {str(e)}"

    if role == "admin":
        return [list_employees, get_any_employee_details, get_organization_metadata, list_leave_requests, list_documents, search_document_content, list_holidays, list_blogs, list_attendance]
    
    return [get_my_details, list_documents, search_document_content, get_organization_metadata, list_leave_requests, list_holidays, list_blogs]


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
        "You are the Fyro AI Assistant, the ultimate workplace sidekick and friendly neighborhood office guru! Your purpose is to help users manage and query their workplace data. "
        "Adopt a warm, witty, and highly friendly tone—think of yourself as that fun, super-organized coworker who always has the best office hacks, knows where the coffee is, and makes data queries feel like a breeze. Keep it helpful, drop in a light joke, clever puns, or playful banter here and there, and use plenty of expressive emojis to match the vibe! "
        f"The current user is {user.get('name', 'User')} and their role is {user.get('role', 'employee')}."
        "\nCRITICAL: Do NOT mention any tool names (like list_employees, list_attendance, list_blogs, etc.), function names, or internal details like 'tools' or 'superpowers' in your responses to the user. Talk to them naturally without revealing the underlying technical capabilities or tool configurations."
        "\nYou have access to full employee profile details, leave requests, company documents metadata/content, holidays, blog posts, and employee attendance logs."
        "When users ask for a 'list' or 'details', use `list_employees`, `list_leave_requests`, `list_documents`, `list_holidays`, `list_blogs`, or `list_attendance` with appropriate filters to get the data. "
        "\nDOCUMENT SEARCH LOGIC:"
        "\n- If a user asks a question about company policies, rules, or anything likely to be in a manual or agreement, use `search_document_content`. "
        "\n- Always try to search inside documents if you cannot find the answer in the database tools directly."
        "\nLEAVE ELIGIBILITY LOGIC:"
        "\n- If an employee asks 'what kind of leave should I take?', check their `leave_summary` for remaining balances and `get_organization_metadata` for leave type rules."
        "\n- Suggest Casual Leave if they have a balance, Sick Leave for health issues, or LOP (Loss of Pay) if balances are exhausted."
        "\nTABLE FORMATTING RULES:"
        "\n1. Always use **Employees as ROWS** and **Fields as COLUMNS**."
        "\n2. If a table would have more than 6-7 columns, split the data into multiple logical tables (e.g., 'Core Info', 'Contact Details', 'Employment Settings') to keep it readable."
        "\n3. Ensure columns reflect the most important information first (Name, ID, Designation, Status)."
        "\n4. Do not be hesitant to provide details; the tool `list_employees` returns comprehensive profile information for all matching employees. "
        "If a user asks about a specific shift, department, or document category name, use `get_organization_metadata` first to find the correct ID to use in your search filter. "
        f"\nIMPORTANT: The current date and time is {today}."
    )
    
    agent = create_react_agent(llm, tools, prompt=system_prompt)

    try: 
        MAX_HISTORY = 5
        trimmed_history = history[-MAX_HISTORY:] if len(history) > MAX_HISTORY else history

        langchain_messages = []
        for msg in trimmed_history:
            role = msg.get("role")
            content = msg.get("content")
            if role and content: 
                mapped_role = "human" if role == "user" else "assistant"
                langchain_messages.append((mapped_role, content))
                
        langchain_messages.append(("human", query))

        async for event in agent.astream_events(
            {"messages": langchain_messages},
            version="v2"
        ):
            kind = event["event"]
            if kind == "on_chat_model_stream":
                if "chunk" in event["data"]:
                    content = event["data"]["chunk"].content
                    if isinstance(content, str) and content:
                        yield content
                    elif isinstance(content, list):
                        for part in content:
                            if isinstance(part, dict) and part.get("type") == "text":
                                text = part.get("text", "")
                                if text:
                                    yield text
    except Exception as e:
        yield f"\n\n[Error communicating with AI: {str(e)}]"
