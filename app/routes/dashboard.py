
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
            now_utc = datetime.utcnow()
            today_str = now_utc.strftime("%Y-%m-%d")
            
            # 1. Employee Analytics
            employees, _ = await repo.get_employees(limit=1000)
            thirty_days_ago = (now_utc - timedelta(days=30)).strftime("%Y-%m-%d")
            sixty_days_ago = (now_utc - timedelta(days=60)).strftime("%Y-%m-%d")
            
            total_employees = len(employees)
            active_employees = len([e for e in employees if e.get("status") == "Active"])
            inactive_employees = total_employees - active_employees
            
            new_hires_this_month = len([e for e in employees if e.get("date_of_joining") and e.get("date_of_joining") >= thirty_days_ago])
            new_hires_last_month = len([e for e in employees if e.get("date_of_joining") and sixty_days_ago <= e.get("date_of_joining") < thirty_days_ago])
            
            growth_rate = 0
            if total_employees - new_hires_this_month > 0:
                growth_rate = round((new_hires_this_month / (total_employees - new_hires_this_month)) * 100, 1)

            # Attrition (Mock logic for now as we don't have exit data clearly tracked in basic employees list)
            attrition_this_month = len([e for e in employees if e.get("status") == "Inactive" and e.get("updated_at") and str(e.get("updated_at")) >= thirty_days_ago])
            attrition_rate = round((attrition_this_month / total_employees) * 100, 1) if total_employees > 0 else 0

            # Work Mode Distribution
            work_modes = {"Office": 0, "Remote": 0, "Hybrid": 0}
            for e in employees:
                m = e.get("work_mode", "Office")
                if m in work_modes: work_modes[m] += 1
            
            work_mode_dist = {
                "office": work_modes["Office"],
                "remote": work_modes["Remote"],
                "hybrid": work_modes["Hybrid"],
                "office_percentage": round((work_modes["Office"] / total_employees) * 100, 1) if total_employees > 0 else 0,
                "remote_percentage": round((work_modes["Remote"] / total_employees) * 100, 1) if total_employees > 0 else 0,
                "hybrid_percentage": round((work_modes["Hybrid"] / total_employees) * 100, 1) if total_employees > 0 else 0
            }

            recent_hires = sorted(
                [e for e in employees if e.get("date_of_joining")],
                key=lambda x: x.get("date_of_joining"),
                reverse=True
            )[:5]
            
            upcoming_confirmations = []
            for e in employees:
                conf_date = e.get("confirmation_date")
                if conf_date and conf_date >= today_str:
                    days_diff = (datetime.strptime(conf_date, "%Y-%m-%d") - datetime.strptime(today_str, "%Y-%m-%d")).days
                    if days_diff <= 30:
                        upcoming_confirmations.append({**e, "days_until_confirmation": days_diff})
            
            upcoming_exits = []
            for e in employees:
                last_day = e.get("last_working_day")
                if last_day and last_day >= today_str:
                    days_diff = (datetime.strptime(last_day, "%Y-%m-%d") - datetime.strptime(today_str, "%Y-%m-%d")).days
                    if days_diff <= 30:
                        upcoming_exits.append({**e, "days_remaining": days_diff})

            employee_analytics = {
                "overview": {
                    "total_count": total_employees,
                    "active_count": active_employees,
                    "inactive_count": inactive_employees,
                    "new_hires_this_month": new_hires_this_month,
                    "new_hires_last_month": new_hires_last_month,
                    "growth_rate_percentage": growth_rate,
                    "attrition_this_month": attrition_this_month,
                    "attrition_rate_percentage": attrition_rate
                },
                "work_mode_distribution": work_mode_dist,
                "recent_hires": [
                    {
                        "id": e.get("id"), "name": e.get("name"), "email": e.get("email"),
                        "profile_picture": e.get("profile_picture"), "department": e.get("department"),
                        "designation": e.get("designation"), "date_of_joining": e.get("date_of_joining")
                    } for e in recent_hires
                ],
                "upcoming_confirmations": [
                    {
                        "id": e.get("id"), "name": e.get("name"), "email": e.get("email"),
                        "profile_picture": e.get("profile_picture"), "department": e.get("department"),
                        "confirmation_date": e.get("confirmation_date"), "days_until_confirmation": e.get("days_until_confirmation")
                    } for e in sorted(upcoming_confirmations, key=lambda x: x["confirmation_date"])[:5]
                ],
                "upcoming_exits": [
                    {
                        "id": e.get("id"), "name": e.get("name"), "email": e.get("email"),
                        "profile_picture": e.get("profile_picture"), "department": e.get("department"),
                        "last_working_day": e.get("last_working_day"), "days_remaining": e.get("days_remaining")
                    } for e in sorted(upcoming_exits, key=lambda x: x["last_working_day"])[:5]
                ]
            }

            # 2. Attendance Analytics
            start_of_week = (now_utc - timedelta(days=now_utc.weekday())).strftime("%Y-%m-%d")
            start_of_month = now_utc.replace(day=1).strftime("%Y-%m-%d")
            
            att_today_res = await repo.get_all_attendance(date=today_str, limit=2000)
            att_week_res = await repo.get_all_attendance(start_date=start_of_week, end_date=today_str, limit=2000)
            att_month_res = await repo.get_all_attendance(start_date=start_of_month, end_date=today_str, limit=2000)
            
            # Extract Metrics correctly (nested in repo response)
            repo_metrics = (att_today_res or {}).get("metrics", {})
            today_counts = repo_metrics.get("today", {})
            month_counts = repo_metrics.get("month", {})
            
            # Extract Data for manual calculations
            today_data = (att_today_res or {}).get("data", [])
            week_data = (att_week_res or {}).get("data", [])
            month_data = (att_month_res or {}).get("data", [])

            # Helper for Avg Hours
            def calc_avg_hours(data_list):
                 if not data_list: return 0
                 total_hours = sum(float(r.get("total_work_hours", 0)) for r in data_list)
                 return round(total_hours / len(data_list), 1) if len(data_list) > 0 else 0

            today_avg_hours = calc_avg_hours(today_data)
            
            # Week Calculations (Manual)
            week_present = len([r for r in week_data if r.get("status") in ["Present", "Late"]])
            week_late = len([r for r in week_data if r.get("status") == "Late" or r.get("is_late")])
            week_avg_hours = calc_avg_hours(week_data)
            
            # Punctuality/Attendance Concerns
            attendance_concerns = []
            att_records_month = month_data
            emp_att_summary = {}
            for r in att_records_month:
                eid = r.get("employee_id")
                if eid not in emp_att_summary: emp_att_summary[eid] = {"late": 0, "absent": 0, "present": 0}
                status = r.get("status")
                if status == "Late" or r.get("is_late"): emp_att_summary[eid]["late"] += 1
                elif status == "Absent": emp_att_summary[eid]["absent"] += 1
                elif status == "Present": emp_att_summary[eid]["present"] += 1

            for eid, stats in emp_att_summary.items():
                if stats["late"] > 3 or stats["absent"] > 2:
                    emp_info = next((e for e in employees if str(e.get("employee_no_id")) == str(eid) or str(e.get("id")) == str(eid)), {})
                    attendance_concerns.append({
                        "employee_id": eid,
                        "name": emp_info.get("name", "Unknown"),
                        "profile_picture": emp_info.get("profile_picture"),
                        "late_count": stats["late"],
                        "absent_days": stats["absent"],
                        "concern_level": "high" if stats["late"] > 5 or stats["absent"] > 3 else "medium"
                    })

            attendance_analytics = {
                "today": {
                    "date": today_str,
                    "total_employees": total_employees,
                    "present": today_counts.get("total_present", 0),
                    "on_time": today_counts.get("on_time", 0),
                    "absent": today_counts.get("absent", 0),
                    "on_leave": today_counts.get("leave", 0),
                    "late": today_counts.get("late", 0),
                    "half_day": today_counts.get("half_day", 0),
                    "permission": today_counts.get("permission", 0),
                    "holiday": today_counts.get("holiday", 0),
                    "present_percentage": round((today_counts.get("total_present", 0) / total_employees) * 100, 1) if total_employees > 0 else 0,
                    "avg_work_hours": today_avg_hours
                },
                "this_week": {
                    "avg_attendance_percentage": round((week_present / (total_employees * 5)) * 100, 1) if total_employees > 0 else 0,
                    "total_late_instances": week_late,
                    "avg_work_hours_per_day": week_avg_hours
                },
                "this_month": {
                    "total_late_instances": month_counts.get("late", 0),
                    "total_absences": month_counts.get("absent", 0),
                    "avg_work_hours_per_day": calc_avg_hours(month_data)
                },
                "attendance_concerns": sorted(attendance_concerns, key=lambda x: x["late_count"] + x["absent_days"], reverse=True)[:5]
            }

            # 3. Leave Management
            leave_requests = await repo.get_leave_requests()
            pending_leaves = [l for l in leave_requests if l.get("status") == "Pending"]
            approved_today = len([l for l in leave_requests if l.get("status") == "Approved" and l.get("start_date") <= today_str <= l.get("end_date")])
            
            leave_analytics = {
                "overview": {
                    "pending_requests": len(pending_leaves),
                    "approved_today": approved_today,
                    "total_leaves_this_month": len([l for l in leave_requests if l.get("status") == "Approved" and l.get("start_date") >= start_of_month])
                },
                "pending_requests": [
                    {
                        "id": str(l.get("id")), "employee_name": (l.get("employee_details") or {}).get("name"),
                        "leave_type": (l.get("leave_type_details") or {}).get("name"),
                        "start_date": l.get("start_date"), "end_date": l.get("end_date"),
                        "total_days": l.get("total_days"), "reason": l.get("reason"),
                        "applied_on": l.get("created_at")
                    } for l in sorted(pending_leaves, key=lambda x: str(x.get("created_at")), reverse=True)[:5]
                ]
            }

            # 4. Project Analytics
            projects = await repo.get_projects()
            project_analytics = {
                "overview": {
                    "total_projects": len(projects),
                    "active_projects": len([p for p in projects if p.get("status") == "Active"]),
                    "completed_projects": len([p for p in projects if p.get("status") == "Completed"]),
                    "on_hold_projects": len([p for p in projects if p.get("status") == "On Hold"])
                }
            }

            # 5. Task Analytics
            all_tasks = await repo.get_tasks()
            
            # Overview Metrics
            total_tasks = len(all_tasks)
            completed_tasks = len([t for t in all_tasks if t.get("status") == "Completed"])
            in_progress_tasks = len([t for t in all_tasks if t.get("status") == "In Progress"])
            pending_tasks = len([t for t in all_tasks if t.get("status") == "Pending"])
            review_tasks = len([t for t in all_tasks if t.get("status") == "In Review"]) # Assuming this status exists
            
            overdue_tasks_count = len([
                t for t in all_tasks 
                if t.get("end_date") and t.get("end_date") < today_str and t.get("status") != "Completed"
            ])
            
            completion_rate = round((completed_tasks / total_tasks) * 100, 1) if total_tasks > 0 else 0.0

            # Status Distribution
            status_dist = {
                "todo": pending_tasks,
                "in_progress": in_progress_tasks,
                "in_review": review_tasks,
                "completed": completed_tasks
            }

            # Priority Breakdown
            prio_counts = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
            for t in all_tasks:
                p = t.get("priority", "Medium")
                if p in prio_counts: prio_counts[p] += 1
            
            priority_breakdown = {
                "critical": prio_counts["Critical"],
                "high": prio_counts["High"],
                "medium": prio_counts["Medium"],
                "low": prio_counts["Low"]
            }

            # Productivity Trends (Mock Data / Logic based on updated_at if available)
            # For now, we'll keep the structure ready with mock last 7 days data to match the UI request
            productivity_trends = {
                "labels": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
                "completed": [5, 8, 12, 5, 20, 15, 10], # Mocked
                "created": [10, 12, 15, 8, 12, 10, 5]   # Mocked
            }

            # Top Contributors
            contributor_map = {}
            for t in all_tasks:
                if t.get("status") == "Completed":
                    raw_assignee = t.get("assigned_to")
                    assignees = []
                    if isinstance(raw_assignee, list):
                        assignees = raw_assignee
                    elif raw_assignee:
                        assignees = [raw_assignee]
                        
                    for assignee_id in assignees:
                         if assignee_id not in contributor_map:
                             contributor_map[assignee_id] = {"count": 0, "name": "Unknown"}
                         contributor_map[assignee_id]["count"] += 1
            
            # Enrich with names
            top_contributors = []
            for eid, data in contributor_map.items():
                emp = next((e for e in employees if str(e.get("employee_no_id")) == str(eid)), None) # Using employee_no_id as link key
                # Or try matching _id if assigned_to uses ObjectIds
                if not emp:
                     emp = next((e for e in employees if str(e.get("_id")) == str(eid)), None)

                if emp:
                    top_contributors.append({
                        "name": emp.get("name"),
                        "role": emp.get("designation", "Employee"),
                        "completed": data["count"],
                        "efficiency": random.randint(70, 99) # Placeholder for efficiency metric
                    })
            
            top_contributors.sort(key=lambda x: x["completed"], reverse=True)
            top_contributors = top_contributors[:5]

            recent_overdue_tasks = []
            for t in all_tasks:
                if t.get("end_date") and t.get("end_date") < today_str and t.get("status") != "Completed":
                     assignee_name = "Unassigned"
                     
                     # robustly get first assignee ID
                     raw_assignee = t.get("assigned_to")
                     assignee_id = None
                     if isinstance(raw_assignee, list) and len(raw_assignee) > 0:
                         assignee_id = raw_assignee[0]
                     elif raw_assignee and not isinstance(raw_assignee, list):
                         assignee_id = raw_assignee

                     if assignee_id:
                         emp = next((e for e in employees if str(e.get("employee_no_id")) == str(assignee_id)), None)
                         if not emp: emp = next((e for e in employees if str(e.get("_id")) == str(assignee_id)), None)
                         if emp: assignee_name = emp.get("name")
                         
                     recent_overdue_tasks.append({
                         "id": str(t.get("_id", "")),
                         "title": t.get("task_name"),
                         "assigned_to": assignee_name,
                         "due_date": t.get("end_date"),
                         "priority": t.get("priority")
                     })
            
            task_analytics = {
                "overview": {
                    "total_assigned": total_tasks,
                    "completed": completed_tasks,
                    "in_progress": in_progress_tasks,
                    "pending": pending_tasks,
                    "overdue": overdue_tasks_count,
                    "completion_rate_percentage": completion_rate
                },
                "status_distribution": status_dist,
                "priority_breakdown": priority_breakdown,
                "productivity_trends": productivity_trends,
                "top_contributors": top_contributors,
                "recent_overdue_tasks": recent_overdue_tasks[:5]
            }

            # 6. Alerts & Notifications
            alerts = {
                "critical": [], "warnings": [], "info": []
            }
            # Overdue Projects
            overdue_projs = [p for p in projects if p.get("status") == "Active" and p.get("end_date") and p.get("end_date") < today_str]
            if overdue_projs:
                alerts["critical"].append({
                    "type": "project_overdue", "severity": "critical",
                    "message": f"{len(overdue_projs)} projects are overdue",
                    "count": len(overdue_projs), "action_required": True, "link": "/projects"
                })
            
            # Pending Leaves
            if pending_leaves:
                alerts["critical"].append({
                    "type": "pending_leave_requests", "severity": "high",
                    "message": f"{len(pending_leaves)} leave requests pending approval",
                    "count": len(pending_leaves), "action_required": True, "link": "/leaves"
                })

            # Low Attendance Concern
            low_att_emps = [c for c in attendance_concerns if c["concern_level"] == "high"]
            if low_att_emps:
                alerts["warnings"].append({
                    "type": "low_attendance", "severity": "medium",
                    "message": f"{len(low_att_emps)} employees with critical attendance issues",
                    "count": len(low_att_emps), "action_required": False, "link": "/attendance"
                })

            # 6. Recent Activities
            recent_activities = []
            # Recent Employee Joins
            for e in sorted(employees, key=lambda x: x.get("created_at") or "", reverse=True)[:3]:
                recent_activities.append({
                    "type": "employee_joined", "icon": "user-plus",
                    "message": f"{e.get('name')} joined as {e.get('designation')}",
                    "timestamp": e.get("created_at"), "priority": "low"
                })
            # Recent Project Creations
            for p in sorted(projects, key=lambda x: x.get("created_at") or "", reverse=True)[:3]:
                recent_activities.append({
                    "type": "project_created", "icon": "folder",
                    "message": f"New project '{p.get('name')}' created",
                    "timestamp": p.get("created_at"), "priority": "high"
                })
            # Recent Leave Requests
            for l in sorted(leave_requests, key=lambda x: x.get("created_at") or "", reverse=True)[:3]:
                msg = f"{(l.get('employee_details') or {}).get('name')} requested {(l.get('leave_type_details') or {}).get('name')}"
                recent_activities.append({
                    "type": "leave_request", "icon": "calendar",
                    "message": msg, "timestamp": l.get("created_at"), "priority": "medium"
                })
            
            recent_activities = sorted(recent_activities, key=lambda x: str(x["timestamp"]), reverse=True)[:10]

            # 7. Upcoming Events
            # Holidays
            upcoming_holidays_list = []
            for h in upcoming_holidays:
                upcoming_holidays_list.append({
                    "name": h.get("name"), "date": h.get("date"),
                    "days_until": (datetime.strptime(h.get("date"), "%Y-%m-%d") - datetime.strptime(today_str, "%Y-%m-%d")).days,
                    "type": h.get("holiday_type")
                })
            
            # Birthdays & Anniversaries
            birthdays = []
            anniversaries = []
            for e in employees:
                # Birthday Logic
                dob_str = e.get("date_of_birth")
                if dob_str:
                    try:
                        dob = datetime.strptime(dob_str, "%Y-%m-%d")
                        this_year_bday = dob.replace(year=now_utc.year)
                        if this_year_bday < now_utc.replace(hour=0, minute=0, second=0, microsecond=0):
                            this_year_bday = dob.replace(year=now_utc.year + 1)
                        days_diff = (this_year_bday - now_utc.replace(hour=0, minute=0, second=0, microsecond=0)).days
                        if days_diff == 0:
                            birthdays.append({
                                "name": e.get("name"), "date": this_year_bday.strftime("%b %d"),
                                "days_until": days_diff, "profile_picture": e.get("profile_picture")
                            })
                    except: pass
                
                # Anniversary Logic
                doj_str = e.get("date_of_joining")
                if doj_str:
                    try:
                        doj = datetime.strptime(doj_str, "%Y-%m-%d")
                        this_year_anniv = doj.replace(year=now_utc.year)
                        if this_year_anniv < now_utc.replace(hour=0, minute=0, second=0, microsecond=0):
                             this_year_anniv = doj.replace(year=now_utc.year + 1)
                        days_diff = (this_year_anniv - now_utc.replace(hour=0, minute=0, second=0, microsecond=0)).days
                        if 0 <= days_diff <= 30:
                            anniversaries.append({
                                "name": e.get("name"), "date": this_year_anniv.strftime("%Y-%m-%d"),
                                "days_until": days_diff, "years_completed": this_year_anniv.year - doj.year,
                                "profile_picture": e.get("profile_picture")
                            })
                    except: pass

            upcoming_events = {
                "holidays": upcoming_holidays_list,
                "birthdays": sorted(birthdays, key=lambda x: x["days_until"]),
                "anniversaries": sorted(anniversaries, key=lambda x: x["days_until"])
            }

            data = {
                "type": "admin",
                "employee_analytics": employee_analytics,
                "attendance_analytics": attendance_analytics,
                "leave_analytics": leave_analytics,
                "project_analytics": project_analytics,
                "task_analytics": task_analytics,
                "alerts": alerts,
                "recent_activities": recent_activities,
                "upcoming_events": upcoming_events
            }
            
            return JSONResponse(status_code=200, content={"success": True, "data": data})


        else:
            # --- EMPLOYEE DASHBOARD ---
            employee_id = current_user.get("employee_no_id")
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
            
            # Use both IDs to find all records (legacy and new)
            # The user wants to move to MongoID, so we facilitate that by reading both 
            # but we should ensure writes use MongoID (handled in repository)
            emp_ids_to_query = [str(emp_doc["_id"])]
            if emp_doc.get("employee_no_id"):
                emp_ids_to_query.append(emp_doc.get("employee_no_id"))

            attendance_cursor = repo.attendance.find({
                "employee_id": {"$in": emp_ids_to_query},
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
            half_day_days = 0
            permission_days = 0
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
                        att_status = (att_record.get("attendance_status") or "").lower()
                        # Handle varied status cases
                        if status in ["Present", "Late", "Half Day"] or att_record.get("is_late"): 
                            present_days += 1
                        elif status == "Absent": 
                            absent_days += 1
                        
                        if att_record.get("is_late") or status == "Late" or att_status == "late": 
                            late_days += 1
                        
                        if att_record.get("is_half_day") or status == "Half Day" or att_status == "half day":
                            half_day_days += 1
                        
                        if att_record.get("is_permission") or att_status == "permission":
                            permission_days += 1
                        
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
                "on_time_days": present_days - late_days,
                "absent_days": absent_days,
                "late_days": late_days,
                "half_day_days": half_day_days,
                "permission_days": permission_days,
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
                        # Check if birthday is today
                        this_year_bday = dob.replace(year=today_date.year)
                        
                        # Normalize today_date to midnight for day-based comparison
                        today_midnight = today_date.replace(hour=0, minute=0, second=0, microsecond=0)
                        
                        if this_year_bday < today_midnight:
                            this_year_bday = dob.replace(year=today_date.year + 1)
                        
                        days_diff = (this_year_bday - today_midnight).days
                        if days_diff == 0:
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
