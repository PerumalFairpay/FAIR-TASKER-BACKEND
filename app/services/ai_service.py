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
from app.crud.repository import repository as repo
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
        Use this for questions like 'who is married?', 'list onboarding employees', 
        'who is a developer?', or 'who works in the first shift?'.
        'include_all_profile_details': Set to true if the user specifically asks for 'all details' or 'everything'.
        'search': general search string (name, email, mobile, id).
        'status': e.g., 'Active', 'Joined', 'Resigned', 'Terminated'.
        'role_filter': e.g., 'admin', 'employee', 'manager'.
        'shift_id': the ID of the shift (use get_organization_metadata to find IDs).
        """
        try:
            # If no specific filters and not asking for full details, return the summary (FAST)
            if not include_all_profile_details and not any([search, status, role_filter, work_mode, shift_id, gender, marital_status, designation, department, employee_type]):
                return await repo.get_all_employees_summary()
            
            # If filters are present OR include_all_profile_details is True, use the more comprehensive get_employees
            employees, _ = await repo.get_employees(
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

            # Clean up the data for better LLM context and table rendering
            cleaned_employees = []
            for emp in employees:
                clean_emp = {k: v for k, v in emp.items() if v is not None and k not in ["_id", "id", "hashed_password", "password", "onboarding_checklist", "offboarding_checklist", "documents", "created_at", "updated_at"]}
                # Add summarized versions of complex fields if helpful
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
        Use this when you want to know about your own data.
        """
        try:
            # Find employee by employee_no_id which is linked to the user
            employee = await repo.employees.find_one({"employee_no_id": emp_no_id})
            if not employee:
                return "Your employee record could not be found."
            
            emp_id = str(employee["_id"])
            
            # Aggregate comprehensive data
            data = {
                "profile": await repo.get_employee(emp_id),
                "leave_summary": await repo.get_employee_leave_balances(emp_id),
                "task_metrics": await repo.get_employee_task_metrics(emp_id),
                "attendance_stats": await repo.get_employee_attendance_stats(emp_id),
                "assigned_projects": await repo.get_employee_assigned_projects(emp_id),
                "assigned_assets": await repo.get_assets_by_employee(emp_id)
            }
            return data
        except Exception as e:
            return f"Error fetching your details: {str(e)}"

    @tool
    async def get_any_employee_details(search_query: str):
        """
        Retrieves full details for a specific employee identified by name, email, mobile, or ID.
        Returns personal info, tasks, leave balances, attendance stats, projects, and assets.
        'search_query': Any identifying information about the employee.
        """
        try:
            # Search for the employee using the repository's search capability
            employees, _ = await repo.get_employees(search=search_query, limit=1)
            if not employees:
                return f"No employee found matching '{search_query}'"
            
            emp = employees[0]
            emp_id = emp["id"]

            # Aggregate comprehensive data
            data = {
                "profile": await repo.get_employee(emp_id),
                "leave_summary": await repo.get_employee_leave_balances(emp_id),
                "task_metrics": await repo.get_employee_task_metrics(emp_id),
                "attendance_stats": await repo.get_employee_attendance_stats(emp_id),
                "assigned_projects": await repo.get_employee_assigned_projects(emp_id),
                "assigned_assets": await repo.get_assets_by_employee(emp_id)
            }
            return data
        except Exception as e:
            return f"Error fetching employee details: {str(e)}"

    @tool
    async def get_organization_metadata():
        """
        Retrieves reference information about the organization, such as lists of 
        Departments, Shifts, and Leave Types. 
        Use this to find correct IDs or names when answering questions about specific company units or shifts.
        """
        try:
            shifts = await repo.get_shifts()
            departments = await repo.get_departments()
            leave_types = await repo.get_leave_types()
            doc_categories = await repo.get_document_categories()
            
            return {
                "shifts": [{"id": s["id"], "name": s["name"], "time": f"{s['start_time']}-{s['end_time']}"} for s in shifts],
                "departments": [{"id": d["id"], "name": d["name"]} for d in departments],
                "leave_types": [{"id": lt["id"], "name": lt["name"], "days": lt["number_of_days"]} for lt in leave_types],
                "document_categories": [{"id": dc["id"], "name": dc["name"]} for dc in doc_categories]
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
        Use this for questions like 'who applied for leave today?' or 'what are my pending leaves?'.
        'employee_id': filter by a specific employee's ID.
        'status': filter by status (Pending, Approved, Rejected). Use 'All' for everything.
        'date': filter for requests active on a specific date (YYYY-MM-DD). Use this for 'today' or a specific day.
        """
        try:
            # Enforce self-only for non-admins
            if role != "admin":
                # Find current employee's internal ID based on their linked employee_no_id
                employee = await repo.employees.find_one({"employee_no_id": emp_no_id})
                if not employee:
                    return "Could not identify your employee record to list leaves."
                employee_id = str(employee["_id"])
                
            return await repo.get_leave_requests(employee_id=employee_id, status=status, date=date)
        except Exception as e:
            return f"Error listing leave requests: {str(e)}"

    @tool
    async def list_documents(
        search: Optional[str] = None,
        status: Optional[str] = "Active"
    ):
        """
        Retrieves a list of company documents (Policies, Agreements, Manuals, etc.).
        Use this to see what documents are available and their metadata like expiry dates.
        'search': filter by document name.
        'status': filter by status (Active, Archived, etc.). Use 'All' for everything.
        """
        try:
            # Enforce Active status for non-admins
            if role != "admin":
                status = "Active"
            return await repo.get_documents(status=status, search=search)
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
        Use this for questions about company policies, rules, procedures, or specifics inside PDFs/Docs.
        'query': the natural language question or search terms to find inside the documents.
        'category_id': optional filter to search only within a specific document category.
        """
        try:
            filter_dict = {"category_id": category_id} if category_id else {}
            
            # For non-admins, only search active documents
            if role != "admin":
                active_docs = await repo.get_documents(status="Active")
                active_doc_ids = [str(doc["id"]) for doc in active_docs]
                if not active_doc_ids:
                    return "No relevant active documents found to search."
                filter_dict["document_id"] = active_doc_ids

            results = await vector_store_service.search_documents(query=query, filter_dict=filter_dict, limit=limit)
            
            if not results:
                return f"No relevant information found inside documents for '{query}'."
            
            return results
        except Exception as e:
            return f"Error searching document content: {str(e)}"

    if role == "admin":
        return [list_employees, get_any_employee_details, get_organization_metadata, list_leave_requests, list_documents, search_document_content]
    
    # Default: Only allow getting own details + searching company policies & metadata (Active documents only)
    return [get_my_details, list_documents, search_document_content, get_organization_metadata, list_leave_requests]

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
        "You are the Fyro AI Assistant. Your purpose is to help users manage and query their workplace data. "
        "Maintain a helpful, formal, and objective tone throughout the conversation, utilizing relevant emojis where appropriate to enhance the interaction. "
        f"The current user is {user.get('name', 'User')} and their role is {user.get('role', 'employee')}."
        "\nYou have access to full employee profile details, leave requests, and company documents metadata/content. "
        "When users ask for a 'list' or 'details', use `list_employees`, `list_leave_requests`, or `list_documents` with appropriate filters to get the data. "
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

