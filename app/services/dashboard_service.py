from app.crud.repository import repository as repo
from datetime import datetime, timedelta
import random
from app.utils import normalize
from typing import Optional, List

async def get_employee_dashboard_data(employee_id: str):
    # 1. Profile
    emp_doc = await repo.employees.find_one({"employee_no_id": employee_id})
    if not emp_doc:
        # Try finding by _id
        try:
             from bson import ObjectId
             emp_doc = await repo.employees.find_one({"_id": ObjectId(employee_id)})
        except:
             pass
    
    if not emp_doc:
         return None
    
    emp_profile = normalize(emp_doc)
    # Remove sensitive fields
    for k in ["hashed_password", "password"]:
        emp_profile.pop(k, None)

    # 2. Greeting Logic
    hour = (datetime.utcnow().hour + 5) % 24 
    
    greeting_text = "Good Morning"
    period = "Morning"
    if 12 <= hour < 17:
        greeting_text = "Good Afternoon"
        period = "Afternoon"
    elif hour >= 17:
        greeting_text = "Good Evening"
        period = "Evening"
    
    first_name = emp_profile.get("first_name", emp_profile.get("name", "there"))
    greeting_text = f"{greeting_text}, {first_name}"

    motivational_quotes = {
        "Morning": [
            "Let's make today count!",
            "Ready to achieve great things?",
            "Rise and shine!",
            "Today is a fresh start."
        ],
        "Afternoon": [
            "Hope your day is going well.",
            "Keep up the great momentum!",
            "You're doing great.",
            "Halfway through the day!"
        ],
        "Evening": [
            "Time to unwind soon.",
            "Great work today!",
            "Rest and recharge.",
            "Have a wonderful evening."
        ]
    }
    
    message = random.choice(motivational_quotes.get(period, ["Have a great day!"]))

    greeting_obj = {
        "greeting_text": greeting_text,
        "message": message
    }

    # 3. Work Hours & Attendance Metrics (Enhanced)
    start_of_month = datetime.utcnow().replace(day=1).strftime("%Y-%m-%d")
    today_dt = datetime.utcnow()
    today_str = today_dt.strftime("%Y-%m-%d")
    start_of_week = (today_dt - timedelta(days=today_dt.weekday())).strftime("%Y-%m-%d")
    
    emp_ids_to_query = [str(emp_doc["_id"])]
    if emp_doc.get("employee_no_id"):
        emp_ids_to_query.append(emp_doc.get("employee_no_id"))

    attendance_cursor = repo.attendance.find({
        "employee_id": {"$in": emp_ids_to_query},
        "date": {"$gte": start_of_month}
    })
    month_attendance = await attendance_cursor.to_list(length=None)
    att_map = {a.get("date"): a for a in month_attendance}

    def daterange(start_date, end_date):
        for n in range(int((end_date - start_date).days) + 1):
            yield start_date + timedelta(n)

    all_holidays = await repo.get_holidays()

    start_date_obj = datetime.strptime(start_of_month, "%Y-%m-%d")
    current_date_obj = datetime.strptime(today_str, "%Y-%m-%d")

    present_days = 0
    absent_days = 0
    late_days = 0
    hours_today = 0.0
    hours_week = 0.0
    hours_month = 0.0
    
    # Leave Days Calculation
    leave_types = await repo.get_leave_types()
    my_leaves = await repo.get_leave_requests(str(emp_doc.get("_id"))) 
    
    leaves_this_month = 0.0
    leave_date_map = {} 
    for l in my_leaves:
        if l.get("status") == "Approved":
             if l.get("start_date") >= start_of_month:
                 leaves_this_month += float(l.get("total_days", 0))
             
             l_start = datetime.strptime(l.get("start_date"), "%Y-%m-%d")
             l_end = datetime.strptime(l.get("end_date"), "%Y-%m-%d")
             for d in daterange(l_start, l_end):
                 leave_date_map[d.strftime("%Y-%m-%d")] = "Leave"

    month_holidays = set()
    for h in all_holidays:
         h_date = h.get("date")
         if h_date >= start_of_month and h_date <= today_str and h.get("status") == "Active":
             month_holidays.add(h_date)

    total_working_days_elapsed = 0
    
    for single_date in daterange(start_date_obj, current_date_obj):
        d_str = single_date.strftime("%Y-%m-%d")
        is_sunday = single_date.weekday() == 6
        is_holiday = d_str in month_holidays
        
        if not is_sunday and not is_holiday:
            
            att_record = att_map.get(d_str)
            is_leave = leave_date_map.get(d_str) == "Leave"
            
            increment_total = True
            if d_str == today_str and not att_record and not is_leave:
                increment_total = False
            
            if increment_total:
                total_working_days_elapsed += 1
            
            if att_record:
                status = att_record.get("status", "Present")
                if status in ["Present", "Late"] or att_record.get("is_late"): 
                    present_days += 1
                elif status == "Absent": 
                    absent_days += 1
                
                if att_record.get("is_late") or status == "Late": 
                    late_days += 1
                
                wh = float(att_record.get("total_work_hours", 0))
                hours_month += wh
                if d_str == today_str: hours_today += wh
                if d_str >= start_of_week: hours_week += wh
                
            elif is_leave:
                pass 
            else:
                if d_str != today_str: 
                    absent_days += 1

    work_hours = {
        "today": round(hours_today, 1),
        "this_week": round(hours_week, 1),
        "this_month": round(hours_month, 1)
    }
    
    attendance_metrics = {
        "present_days": present_days,
        "on_time_days": present_days - late_days,  
        "absent_days": absent_days,
        "late_days": late_days,
        "holiday_days": len(month_holidays), 
        "leave_days": leaves_this_month,
        "total_working_days": total_working_days_elapsed
    }
    
    leave_balance = []
    total_allowed_all = 0
    total_taken_all = 0
    
    for lt in leave_types:
        total_allowed = lt.get("number_of_days", 0)
        used = 0
        for l in my_leaves:
            if l.get("leave_type_id") == lt.get("id") and l.get("status") == "Approved":
                 used += float(l.get("total_days", 0))
        
        total_allowed_all += total_allowed
        total_taken_all += used
        
        leave_balance.append({
            "type": lt.get("name"),
            "balance": total_allowed - used,
            "total": total_allowed,
            "used": used
        })
    
    pending_leaves_count = len([l for l in my_leaves if l.get("status") == "Pending"])
    
    sorted_leaves = sorted(my_leaves, key=lambda x: x.get("created_at", ""), reverse=True)
    recent_requests_status = []
    for l in sorted_leaves[:3]:
        lt_name = "Leave"
        for lt in leave_types:
            if lt.get("id") == l.get("leave_type_id"):
                lt_name = lt.get("name")
                break
        
        recent_requests_status.append({
            "type": lt_name,
            "status": l.get("status"),
            "date": l.get("start_date")
        })

    leave_details = {
        "summary": {
            "total_allowed": total_allowed_all,
            "total_taken": total_taken_all,
            "total_remaining": total_allowed_all - total_taken_all,
            "pending_requests": pending_leaves_count
        },
        "balance": leave_balance,
        "recent_requests_status": recent_requests_status
    }

    # 5. Task Metrics & Recent Tasks
    my_tasks = await repo.get_tasks(assigned_to=str(emp_doc["_id"])) 
    
    task_metric_counts = {
        "total_assigned": len(my_tasks),
        "pending": 0,
        "in_progress": 0,
        "completed": 0,
        "overdue": 0
    }
    
    for t in my_tasks:
        status = t.get("status")
        if status == "Completed": task_metric_counts["completed"] += 1
        elif status == "In Progress": task_metric_counts["in_progress"] += 1
        else: task_metric_counts["pending"] += 1 
        
        if t.get("end_date") and t.get("end_date") < today_str and status != "Completed":
            task_metric_counts["overdue"] += 1

    sorted_tasks = sorted(my_tasks, key=lambda x: x.get("created_at") or "", reverse=True)
    recent_tasks_list = []
    for t in sorted_tasks[:5]:
        recent_tasks_list.append({
            "task_name": t.get("task_name"),
            "priority": t.get("priority"),
            "status": t.get("status"),
            "due_date": t.get("end_date")
        })

    # 6. Projects
    all_projects = await repo.get_projects()
    emp_oid = str(emp_doc["_id"])
    my_projects = []
    for p in all_projects:
        members = p.get("team_member_ids", [])
        leaders = p.get("team_leader_ids", [])
        managers = p.get("project_manager_ids", [])
        
        role = None
        if emp_oid in managers: role = "Project Manager"
        elif emp_oid in leaders: role = "Team Leader"
        elif emp_oid in members: role = "Team Member"
        
        if role:
            my_projects.append({
                "name": p.get("name"),
                "role": role,
                "status": p.get("status"),
                "deadline": p.get("end_date")
            })

    # 7. Recent Activity (Mashup)
    recent_activity = []
    # Add tasks
    for t in sorted_tasks[:3]:
        msg = f"Task '{t.get('task_name')}' is {t.get('status')}"
        if t.get("status") == "Completed": msg = f"You completed task '{t.get('task_name')}'"
        recent_activity.append({
            "type": "task",
            "message": msg,
            "time": t.get("updated_at") or t.get("created_at")
        })
    # Add leaves
    for l in sorted_leaves[:3]:
        recent_activity.append({
            "type": "leave",
            "message": f"Leave request {l.get('status')}",
            "time": l.get("updated_at") or l.get("created_at")
        })
    
    recent_activity.sort(key=lambda x: str(x.get("time")), reverse=True)
    recent_activity = recent_activity[:5]

    # 8. Upcoming Events
    upcoming_events = {
        "holidays": [], 
        "birthdays": [],
        "anniversaries": []
    }
    
    # Re-implement upcoming holidays for the employee
    upcoming_holidays = [
        h for h in all_holidays 
        if h.get("date") >= today_str and h.get("status") == "Active"
    ]
    upcoming_holidays.sort(key=lambda x: x.get("date"))
    upcoming_holidays = upcoming_holidays[:3]
    
    upcoming_holidays_list = []
    for h in upcoming_holidays:
        upcoming_holidays_list.append({
            "name": h.get("name"), "date": h.get("date"),
            "days_until": (datetime.strptime(h.get("date"), "%Y-%m-%d") - datetime.strptime(today_str, "%Y-%m-%d")).days,
            "type": h.get("holiday_type")
        })
    upcoming_events["holidays"] = upcoming_holidays_list

    data = {
        "type": "employee",
        "profile": emp_profile,
        "greeting": greeting_obj,
        "work_hours": work_hours,
        "attendance_metrics": attendance_metrics,
        "leave_details": leave_details,
        "task_metrics": task_metric_counts,
        "recent_tasks": recent_tasks_list,
        "projects": my_projects,
        "recent_activity": recent_activity,
        "upcoming_events": upcoming_events
    }
    return data
