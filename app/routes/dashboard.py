
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from app.crud.repository import repository as repo
from app.auth import get_current_user, verify_token
from typing import List, Optional
from datetime import datetime, timedelta
import random

router = APIRouter(prefix="/dashboard", tags=["dashboard"], dependencies=[Depends(verify_token)])

@router.get("")
async def get_dashboard_data(current_user: dict = Depends(get_current_user)):
    try:
        user_role = current_user.get("role", "employee")
        today_str = datetime.utcnow().strftime("%Y-%m-%d")
        
        # Common Data: Upcoming Holidays
        all_holidays = await repo.get_holidays()
        upcoming_holidays = [
            h for h in all_holidays 
            if h.get("date") >= today_str and h.get("status") == "Active"
        ]
        upcoming_holidays.sort(key=lambda x: x.get("date"))
        upcoming_holidays = upcoming_holidays[:3]

        if user_role == "admin":
            # --- ADMIN DASHBOARD ---
            
            # 1. Overview Counts
            employees, _ = await repo.get_employees(limit=1000)
            clients = await repo.get_clients()
            projects = await repo.get_projects()
            leave_requests = await repo.get_leave_requests()
            
            total_employees = len(employees)
            total_clients = len(clients)
            total_projects = len(projects)
            active_projects = len([p for p in projects if p.get("status") == "Active"])
            pending_leaves = len([l for l in leave_requests if l.get("status") == "Pending"])
            
            approved_leaves_today = 0
            for l in leave_requests:
                if l.get("status") == "Approved" and l.get("start_date") <= today_str <= l.get("end_date"):
                    approved_leaves_today += 1

            # 2. Task Metrics
            all_tasks = await repo.get_tasks()
            total_tasks_pending = 0
            total_tasks_completed = 0
            tasks_overdue = 0
            by_priority = {"High": 0, "Medium": 0, "Low": 0}
            by_status = {"Todo": 0, "In Progress": 0, "Review": 0, "Completed": 0}
            
            for t in all_tasks:
                status = t.get("status", "Todo")
                priority = t.get("priority", "Medium")
                if status == "Completed":
                    total_tasks_completed += 1
                else:
                    total_tasks_pending += 1
                    if t.get("end_date") and t.get("end_date") < today_str:
                        tasks_overdue += 1
                
                # Safe increment
                if priority in by_priority: by_priority[priority] += 1
                
                # Safe increment status
                if status not in by_status: by_status[status] = 0
                by_status[status] += 1

            completion_rate = 0
            if len(all_tasks) > 0:
                completion_rate = round((total_tasks_completed / len(all_tasks)) * 100, 1)

            # 3. Attendance Metrics (Today)
            attendance_data = await repo.get_all_attendance(date=today_str)
            att_metrics = attendance_data.get("metrics", {})
            
            # 4. New Employees (Last 30 days)
            thirty_days_ago = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")
            new_employees = [
                e for e in employees 
                if e.get("date_of_joining") and e.get("date_of_joining") >= thirty_days_ago
            ]
            new_employees.sort(key=lambda x: x.get("date_of_joining"), reverse=True)
            new_employees = new_employees[:5] # Top 5
            
            # 5. Department Distribution
            dept_counts = {}
            for e in employees:
                d = e.get("department", "Unknown")
                dept_counts[d] = dept_counts.get(d, 0) + 1
            
            department_distribution = [{"name": k, "count": v} for k, v in dept_counts.items()]
            
            # 6. Recent Activity (Simplified Mock or Real)
            # We can combine recent leave requests and maybe recent project creations
            # Real implementation: Recent pending leaves + Recent created projects
            recent_activities = []
            
            # Recent Leaves
            sorted_leaves = sorted(leave_requests, key=lambda x: x.get("created_at", ""), reverse=True)
            for l in sorted_leaves[:3]:
                emp_name = l.get("employee_details", {}).get("name", "Unknown")
                recent_activities.append({
                    "type": "leave_request",
                    "message": f"{emp_name} requested {l.get('leave_type_details', {}).get('name', 'Leave')}",
                    "timestamp": l.get("created_at")
                })
                
            # Recent Projects
            sorted_projects = sorted(projects, key=lambda x: x.get("created_at", ""), reverse=True)
            for p in sorted_projects[:3]:
                 recent_activities.append({
                    "type": "project_create",
                    "message": f"New project '{p.get('name')}' created",
                    "timestamp": p.get("created_at")
                })
            
            # Sort combined
            recent_activities.sort(key=lambda x: str(x.get("timestamp")), reverse=True)
            recent_activities = recent_activities[:5]

            # Client Stats
            active_clients = len([c for c in clients if c.get("status") == "Active"])
            # New clients logic similar to employees if needed, skipping complex date logic for now, utilizing simplified stat
            
            data = {
                "type": "admin",
                "overview": {
                    "total_employees": total_employees,
                    "total_clients": total_clients,
                    "active_projects": active_projects,
                    "total_projects": total_projects,
                    "pending_leaves": pending_leaves,
                    "approved_leaves_today": approved_leaves_today
                },
                "task_metrics": {
                    "total_pending": total_tasks_pending,
                    "total_completed": total_tasks_completed,
                    "overdue": tasks_overdue,
                    "completion_rate": completion_rate,
                    "by_priority": by_priority,
                    "by_status": by_status
                },
                "attendance_metrics": {
                    "today_stats": att_metrics,
                    # average_check_in_time could be calculated if needed
                },
                "new_employees": new_employees,
                "department_distribution": department_distribution,
                "recent_activities": recent_activities,
                "client_stats": {
                    "active_clients": active_clients,
                    "new_clients_this_month": 0 # Placeholder or implement date logic
                },
                "upcoming_holidays": upcoming_holidays
            }
            
            return JSONResponse(status_code=200, content={"success": True, "data": data})

        else:
            # --- EMPLOYEE DASHBOARD ---
            employee_id = current_user.get("employee_id")
            if not employee_id:
                return JSONResponse(status_code=400, content={"success": False, "message": "No employee profile linked"})

            # 1. Profile
            emp_doc = await repo.employees.find_one({"employee_no_id": employee_id})
            if not emp_doc:
                 return JSONResponse(status_code=404, content={"success": False, "message": "Employee profile not found"})
            
            from app.utils import normalize
            emp_profile = normalize(emp_doc)
            # Remove sensitive fields
            for k in ["hashed_password", "password"]:
                emp_profile.pop(k, None)

            # 2. Greeting Logic
            # IST Offset approx +5.5 hours, or use simple hour check
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
            
            attendance_cursor = repo.attendance.find({
                "employee_id": employee_id,
                "date": {"$gte": start_of_month}
            })
            month_attendance = await attendance_cursor.to_list(length=None)
            att_map = {a.get("date"): a for a in month_attendance}

            # Helper for date range
            def daterange(start_date, end_date):
                for n in range(int((end_date - start_date).days) + 1):
                    yield start_date + timedelta(n)

            start_date_obj = datetime.strptime(start_of_month, "%Y-%m-%d")
            current_date_obj = datetime.strptime(today_str, "%Y-%m-%d")

            present_days = 0
            absent_days = 0
            late_days = 0
            hours_today = 0.0
            hours_week = 0.0
            hours_month = 0.0
            
            # Leave Days Calculation (Sum of approved leaves in this month)
            leave_types = await repo.get_leave_types()
            my_leaves = await repo.get_leave_requests(str(emp_doc.get("_id"))) 
            
            leaves_this_month = 0.0
            leave_date_map = {} # Map date -> status for quick lookup in loop
            for l in my_leaves:
                if l.get("status") == "Approved":
                     # Add to sum
                     if l.get("start_date") >= start_of_month:
                         leaves_this_month += float(l.get("total_days", 0))
                     
                     # Add to map
                     l_start = datetime.strptime(l.get("start_date"), "%Y-%m-%d")
                     l_end = datetime.strptime(l.get("end_date"), "%Y-%m-%d")
                     for d in daterange(l_start, l_end):
                         leave_date_map[d.strftime("%Y-%m-%d")] = "Leave"

            # Filter Holidays for this month
            month_holidays = set()
            for h in all_holidays:
                 h_date = h.get("date")
                 if h_date >= start_of_month and h_date <= today_str and h.get("status") == "Active":
                     month_holidays.add(h_date)

            # Loop through every day of month until today
            total_working_days_elapsed = 0
            
            for single_date in daterange(start_date_obj, current_date_obj):
                d_str = single_date.strftime("%Y-%m-%d")
                is_sunday = single_date.weekday() == 6
                is_holiday = d_str in month_holidays
                
                # Check metrics if it's a working day (Include Saturdays, Exclude Sundays/Holidays)
                if not is_sunday and not is_holiday:
                    
                    att_record = att_map.get(d_str)
                    is_leave = leave_date_map.get(d_str) == "Leave"
                    
                    # Only count "Today" in total if a status exists (Present/Leave) or if we decide to mark it Absent
                    # To match user expectation (Total = Present + Absent + Leave):
                    # If we skip Absent for Today, we should skip Total for Today if no record.
                    
                    increment_total = True
                    if d_str == today_str and not att_record and not is_leave:
                        increment_total = False
                    
                    if increment_total:
                        total_working_days_elapsed += 1
                    
                    if att_record:
                        # Record Exists
                        status = att_record.get("status", "Present")
                        if status == "Present": present_days += 1
                        elif status == "Absent": absent_days += 1
                        
                        if att_record.get("is_late"): late_days += 1
                        
                        # Hours
                        wh = float(att_record.get("total_work_hours", 0))
                        hours_month += wh
                        if d_str == today_str: hours_today += wh
                        if d_str >= start_of_week: hours_week += wh
                        
                    elif is_leave:
                        pass # Covered by Leave
                    else:
                        # No Record, No Leave, Working Day => Absent
                        if d_str != today_str: 
                            absent_days += 1

            work_hours = {
                "today": round(hours_today, 1),
                "this_week": round(hours_week, 1),
                "this_month": round(hours_month, 1)
            }
            
            attendance_metrics = {
                "present_days": present_days,
                "absent_days": absent_days,
                "late_days": late_days,
                "half_days": 0, 
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
            
            # Recent Leaves
            sorted_leaves = sorted(my_leaves, key=lambda x: x.get("created_at", ""), reverse=True)
            recent_requests_status = []
            for l in sorted_leaves[:3]:
                lt_name = "Leave"
                # Find type name
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
            my_tasks = await repo.get_tasks(assigned_to=employee_id) 
            
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
            
            # Sort combined
            recent_activity.sort(key=lambda x: str(x.get("time")), reverse=True)
            recent_activity = recent_activity[:5]

            # 8. Birthdays
            all_employees, _ = await repo.get_employees(limit=1000)
            birthdays = []
            today_date = datetime.utcnow()
            for e in all_employees:
                dob_str = e.get("date_of_birth")
                if dob_str:
                    try:
                        # Parse date, assuming YYYY-MM-DD
                        dob = datetime.strptime(dob_str, "%Y-%m-%d")
                        # Check if birthday is in next 30 days
                        this_year_bday = dob.replace(year=today_date.year)
                        if this_year_bday < today_date:
                            this_year_bday = dob.replace(year=today_date.year + 1)
                        
                        days_diff = (this_year_bday - today_date).days
                        if 0 <= days_diff <= 30:
                            birthdays.append({
                                "name": e.get("name"),
                                "date": this_year_bday.strftime("%b %d"),
                                "profile_picture": e.get("profile_picture")
                            })
                    except:
                        pass 
            
            birthdays.sort(key=lambda x: x.get("date"))

            # 9. Response
            data = {
                "type": "employee",
                "greeting": greeting_obj,
                "profile": emp_profile,
                "work_hours": work_hours,
                "attendance_metrics": attendance_metrics,
                "leave_details": leave_details,
                "projects": my_projects,
                "task_metrics": task_metric_counts,
                "recent_tasks": recent_tasks_list,
                "recent_activity": recent_activity,
                "upcoming_holidays": upcoming_holidays,
                "birthdays": birthdays
            }
            
            return JSONResponse(status_code=200, content={"success": True, "data": data})

    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "message": str(e)})
