from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from app.auth import get_current_user
from app.crud.repository import repository as repo
from app.utils import normalize
import os
import json
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional
from pydantic import BaseModel

# AI Imports
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

router = APIRouter(prefix="/ai", tags=["ai"])

class ChatRequest(BaseModel):
    message: str
    history: Optional[List[dict]] = []

async def get_user_context(current_user: dict):
    """
    Aggregates all relevant user data from MongoDB to provide context to the AI.
    """
    employee_id = current_user.get("employee_no_id")
    user_oid = current_user.get("id")
    role = current_user.get("role", "employee").lower()
    
    context = {
        "user_role": role,
        "user_profile": {},
        "personal_stats": {
            "attendance": [],
            "leave_balance": [],
            "active_tasks": []
        },
        "company_info": {
            "upcoming_holidays": []
        }
    }

    # 1. Profile (Always personal)
    if employee_id:
        emp_doc = await repo.db["employees"].find_one({"employee_no_id": employee_id})
        if emp_doc:
            profile = normalize(emp_doc)
            # Remove sensitive info
            for k in ["hashed_password", "password", "documents"]:
                profile.pop(k, None)
            context["user_profile"] = profile

    # 2. Personal Data (Leaves, Tasks, Attendance)
    if user_oid:
        balances = await repo.get_employee_leave_balances(user_oid)
        context["personal_stats"]["leave_balance"] = balances

        tasks = await repo.get_tasks(assigned_to=user_oid)
        active_tasks = [
            {
                "name": t.get("task_name"),
                "status": t.get("status"),
                "priority": t.get("priority"),
                "due_date": t.get("end_date")
            }
            for t in tasks if t.get("status") != "Completed"
        ]
        context["personal_stats"]["active_tasks"] = active_tasks[:10]

        now = datetime.utcnow()
        start_date = (now - timedelta(days=30)).strftime("%Y-%m-%d")
        attendance_records = await repo.db["attendance"].find({
            "employee_id": user_oid,
            "date": {"$gte": start_date}
        }).to_list(length=100)
        
        context["personal_stats"]["attendance"] = [
            {"date": a.get("date"), "status": a.get("status"), "clock_in": a.get("clock_in"), "clock_out": a.get("clock_out")}
            for a in attendance_records
        ]

    # 3. Company-Wide Data (Role Based)
    # Holidays (All see this)
    holidays = await repo.get_holidays()
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    context["company_info"]["upcoming_holidays"] = [
        {"name": h.get("name"), "date": h.get("date")}
        for h in holidays if h.get("date") >= today_str and h.get("status") == "Active"
    ][:5]

    # Admin/Manager Level Summaries
    if role in ["admin", "manager"]:
        # Employee Summary
        emp_summary = await repo.get_all_employees_summary()
        context["company_info"]["employee_stats"] = emp_summary

        # Today's Leaves
        today_leaves = await repo.db["leave_requests"].find({
            "start_date": {"$lte": today_str},
            "end_date": {"$gte": today_str},
            "status": "Approved"
        }).to_list(length=50)
        
        context["company_info"]["leaves_today"] = [
            {"employee_name": l.get("employee_name"), "leave_type": l.get("leave_type")}
            for l in today_leaves
        ]

        # Task Overview (Total counts)
        total_tasks = await repo.db["tasks"].count_documents({"status": {"$ne": "Completed"}})
        context["company_info"]["total_pending_tasks"] = total_tasks

    return context

@router.post("/chat")
async def chat_with_assistant(request: ChatRequest, current_user: dict = Depends(get_current_user)):
    try:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="Gemini API Key not configured")

        user_context = await get_user_context(current_user)
        
        # Initialize Gemini
        llm = ChatGoogleGenerativeAI(model="gemini-flash-latest", google_api_key=api_key, streaming=True)

        system_prompt = f"""
        You are 'Fair-Tasker AI', a highly helpful and proactive HR Assistant for the company Fair Pay Tech Works.
        You have contextual knowledge about the current user's profile and relevant company data based on their role.
        
        USER CONTEXT:
        {json.dumps(user_context, indent=2)}
        
        GUIDELINES:
        1. Use the data above to answer user questions personally.
        2. Your responses must respect the user's role ({user_context['user_role']}).
        3. If the user is an 'admin', you can provide company-wide summaries found in 'company_info'.
        4. If the user is an 'employee', focus strictly on their 'user_profile' and 'personal_stats'.
        5. If asked about taking leave, look at their balance AND upcoming holidays to give advice.
        6. Be professional, friendly, and concise.
        7. Today's date is {datetime.utcnow().strftime("%Y-%m-%d")}.
        """

        messages = [SystemMessage(content=system_prompt)]
        
        # Add history
        for msg in request.history:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                messages.append(AIMessage(content=msg["content"]))
        
        messages.append(HumanMessage(content=request.message))

        async def generate():
            async for chunk in llm.astream(messages):
                content = chunk.content
                if isinstance(content, str):
                    yield content
                elif isinstance(content, list):
                    for part in content:
                        if isinstance(part, str):
                            yield part
                        elif isinstance(part, dict) and "text" in part:
                            yield part["text"]
                else:
                    # Fallback to string representation if it's something else
                    yield str(content)

        return StreamingResponse(generate(), media_type="text/plain")

    except Exception as e:
        print(f"AI Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
