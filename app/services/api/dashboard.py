from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
import random
from bson import ObjectId
from app.database import (
    employees_collection,
    attendance_collection,
    leave_requests_collection,
    leave_types_collection,
    projects_collection,
    tasks_collection,
    holidays_collection
)
from app.utils import normalize
import traceback


class DashboardService:

    @staticmethod
    async def get_dashboard_data(current_user: dict) -> Tuple[Optional[dict], Optional[str]]:
        try:
            user_role = current_user.get("role", "employee")
            today_str = datetime.utcnow().strftime("%Y-%m-%d")

            # Common Data: Upcoming Holidays
            all_holidays_raw = await holidays_collection.find({"is_deleted": {"$ne": True}}).to_list(length=None)
            all_holidays = [normalize(h) for h in all_holidays_raw]

            upcoming_holidays = [
                h for h in all_holidays
                if h.get("date") >= today_str and h.get("status") == "Active"
            ]
            upcoming_holidays.sort(key=lambda x: x.get("date"))
            upcoming_holidays = upcoming_holidays[:3]

            if user_role in ["admin", "super_admin"]:
                # --- ADMIN DASHBOARD ---
                now_utc = datetime.utcnow()
                today_str = now_utc.strftime("%Y-%m-%d")

                # 1. Employee Analytics
                employees_raw = await employees_collection.find({"is_deleted": {"$ne": True}}).limit(1000).to_list(length=1000)
                employees = [normalize(e) for e in employees_raw]

                thirty_days_ago = (now_utc - timedelta(days=30)).strftime("%Y-%m-%d")
                sixty_days_ago = (now_utc - timedelta(days=60)).strftime("%Y-%m-%d")

                total_employees = len(employees)
                active_employees = len([e for e in employees if e.get("status") == "Active"])
                inactive_employees = total_employees - active_employees

                new_hires_this_month = len([e for e in employees if e.get("date_of_joining") and e.get("date_of_joining") >= thirty_days_ago])
                new_hires_last_month = len([e for e in employees if e.get("date_of_joining") and sixty_days_ago <= e.get("date_of_joining") < thirty_days_ago])

                growth_rate = 0.0
                if total_employees - new_hires_this_month > 0:
                    growth_rate = round((new_hires_this_month / (total_employees - new_hires_this_month)) * 100, 1)

                attrition_this_month = len([e for e in employees if e.get("status") == "Inactive" and e.get("updated_at") and str(e.get("updated_at")) >= thirty_days_ago])
                attrition_rate = round((attrition_this_month / total_employees) * 100, 1) if total_employees > 0 else 0.0

                # Work Mode Distribution
                work_modes = {"Office": 0, "Remote": 0, "Hybrid": 0}
                for e in employees:
                    m = e.get("work_mode", "Office")
                    if m in work_modes:
                        work_modes[m] += 1

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
                        try:
                            days_diff = (datetime.strptime(conf_date, "%Y-%m-%d") - datetime.strptime(today_str, "%Y-%m-%d")).days
                            if days_diff <= 30:
                                upcoming_confirmations.append({**e, "days_until_confirmation": days_diff})
                        except Exception:
                            pass

                upcoming_exits = []
                for e in employees:
                    last_day = e.get("last_working_day")
                    if last_day and last_day >= today_str:
                        try:
                            days_diff = (datetime.strptime(last_day, "%Y-%m-%d") - datetime.strptime(today_str, "%Y-%m-%d")).days
                            if days_diff <= 30:
                                upcoming_exits.append({**e, "days_remaining": days_diff})
                        except Exception:
                            pass

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

                today_records = await attendance_collection.find({"date": today_str, "is_deleted": {"$ne": True}}).limit(2000).to_list(length=2000)
                week_records = await attendance_collection.find({"date": {"$gte": start_of_week, "$lte": today_str}, "is_deleted": {"$ne": True}}).limit(2000).to_list(length=2000)
                month_records = await attendance_collection.find({"date": {"$gte": start_of_month, "$lte": today_str}, "is_deleted": {"$ne": True}}).limit(2000).to_list(length=2000)

                today_data = [normalize(r) for r in today_records]
                week_data = [normalize(r) for r in week_records]
                month_data = [normalize(r) for r in month_records]

                def calc_avg_hours(data_list):
                    if not data_list:
                        return 0.0
                    total_hours = sum(float(r.get("total_work_hours", 0)) for r in data_list)
                    return round(total_hours / len(data_list), 1) if len(data_list) > 0 else 0.0

                today_avg_hours = calc_avg_hours(today_data)
                week_present = len([r for r in week_data if r.get("status") in ["Present", "Late"]])
                week_late = len([r for r in week_data if r.get("status") == "Late" or r.get("is_late")])
                week_avg_hours = calc_avg_hours(week_data)

                # Counts for today
                today_present_cnt = len([r for r in today_data if r.get("status") in ["Present", "Late", "Overtime"]])
                today_absent_cnt = len([r for r in today_data if r.get("status") == "Absent"])
                today_leave_cnt = len([r for r in today_data if r.get("status") == "Leave"])
                today_late_cnt = len([r for r in today_data if r.get("status") == "Late" or r.get("is_late") or (r.get("attendance_status") or "").lower() == "late"])
                today_half_day_cnt = len([r for r in today_data if r.get("is_half_day") or (r.get("attendance_status") or "").lower() == "half day"])
                today_permission_cnt = len([r for r in today_data if (r.get("attendance_status") or "").lower() == "permission"])
                today_ontime_cnt = len([r for r in today_data if (r.get("attendance_status") or "").lower() == "ontime"])

                # Month counts
                month_late_cnt = len([r for r in month_data if r.get("status") == "Late" or r.get("is_late") or (r.get("attendance_status") or "").lower() == "late"])
                month_absent_cnt = len([r for r in month_data if r.get("status") == "Absent"])

                # Concerns
                attendance_concerns = []
                emp_att_summary = {}
                for r in month_data:
                    eid = r.get("employee_id")
                    if eid not in emp_att_summary:
                        emp_att_summary[eid] = {"late": 0, "absent": 0, "present": 0}
                    status = r.get("status")
                    if status == "Late" or r.get("is_late"):
                        emp_att_summary[eid]["late"] += 1
                    elif status == "Absent":
                        emp_att_summary[eid]["absent"] += 1
                    elif status == "Present":
                        emp_att_summary[eid]["present"] += 1

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
                        "present": today_present_cnt,
                        "on_time": today_ontime_cnt,
                        "absent": today_absent_cnt,
                        "on_leave": today_leave_cnt,
                        "late": today_late_cnt,
                        "half_day": today_half_day_cnt,
                        "permission": today_permission_cnt,
                        "holiday": len([h for h in all_holidays if h.get("date") == today_str]),
                        "present_percentage": round((today_present_cnt / total_employees) * 100, 1) if total_employees > 0 else 0,
                        "avg_work_hours": today_avg_hours
                    },
                    "this_week": {
                        "avg_attendance_percentage": round((week_present / (total_employees * 5)) * 100, 1) if total_employees > 0 else 0,
                        "total_late_instances": week_late,
                        "avg_work_hours_per_day": week_avg_hours
                    },
                    "this_month": {
                        "total_late_instances": month_late_cnt,
                        "total_absences": month_absent_cnt,
                        "avg_work_hours_per_day": calc_avg_hours(month_data)
                    },
                    "attendance_concerns": sorted(attendance_concerns, key=lambda x: x["late_count"] + x["absent_days"], reverse=True)[:5]
                }

                # 3. Leave Management
                leave_requests_raw = await leave_requests_collection.find({"is_deleted": {"$ne": True}}).to_list(length=None)
                leave_requests = [normalize(l) for l in leave_requests_raw]

                # Map details
                leave_types_raw = await leave_types_collection.find({"is_deleted": {"$ne": True}}).to_list(length=None)
                lt_map = {str(lt["_id"]): normalize(lt) for lt in leave_types_raw}
                emp_map = {str(e["_id"]): e for e in employees}

                for l in leave_requests:
                    emp_val = emp_map.get(str(l.get("employee_id")))
                    l["employee_details"] = emp_val
                    l["leave_type_details"] = lt_map.get(str(l.get("leave_type_id")))

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
                projects_raw = await projects_collection.find({"is_deleted": {"$ne": True}}).to_list(length=None)
                projects = [normalize(p) for p in projects_raw]

                project_analytics = {
                    "overview": {
                        "total_projects": len(projects),
                        "active_projects": len([p for p in projects if p.get("status") == "Active"]),
                        "completed_projects": len([p for p in projects if p.get("status") == "Completed"]),
                        "on_hold_projects": len([p for p in projects if p.get("status") == "On Hold"])
                    }
                }

                # 5. Task Analytics
                tasks_raw = await tasks_collection.find({"is_deleted": {"$ne": True}}).to_list(length=None)
                all_tasks = [normalize(t) for t in tasks_raw]

                total_tasks = len(all_tasks)
                completed_tasks = len([t for t in all_tasks if t.get("status") in ["Completed", "Done"]])
                in_progress_tasks = len([t for t in all_tasks if t.get("status") == "In Progress"])
                pending_tasks = len([t for t in all_tasks if t.get("status") in ["Pending", "Todo"]])
                review_tasks = len([t for t in all_tasks if t.get("status") in ["In Review", "Review"]])

                overdue_tasks_count = len([
                    t for t in all_tasks
                    if t.get("end_date") and t.get("end_date") < today_str and t.get("status") not in ["Completed", "Done"]
                ])
                completion_rate = round((completed_tasks / total_tasks) * 100, 1) if total_tasks > 0 else 0.0

                status_dist = {
                    "todo": pending_tasks,
                    "in_progress": in_progress_tasks,
                    "in_review": review_tasks,
                    "completed": completed_tasks
                }

                prio_counts = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
                for t in all_tasks:
                    p = t.get("priority", "Medium")
                    if p in prio_counts:
                        prio_counts[p] += 1

                priority_breakdown = {
                    "critical": prio_counts["Critical"],
                    "high": prio_counts["High"],
                    "medium": prio_counts["Medium"],
                    "low": prio_counts["Low"]
                }

                productivity_trends = {
                    "labels": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
                    "completed": [5, 8, 12, 5, 20, 15, 10],
                    "created": [10, 12, 15, 8, 12, 10, 5]
                }

                contributor_map = {}
                for t in all_tasks:
                    if t.get("status") in ["Completed", "Done"]:
                        raw_assignee = t.get("assigned_to")
                        assignees = raw_assignee if isinstance(raw_assignee, list) else ([raw_assignee] if raw_assignee else [])
                        for assignee_id in assignees:
                            if assignee_id not in contributor_map:
                                contributor_map[assignee_id] = {"count": 0}
                            contributor_map[assignee_id]["count"] += 1

                top_contributors = []
                for eid, data in contributor_map.items():
                    emp = next((e for e in employees if str(e.get("employee_no_id")) == str(eid) or str(e.get("id")) == str(eid)), None)
                    if emp:
                        top_contributors.append({
                            "name": emp.get("name"),
                            "role": emp.get("designation", "Employee"),
                            "completed": data["count"],
                            "efficiency": random.randint(70, 99)
                        })

                top_contributors.sort(key=lambda x: x["completed"], reverse=True)
                top_contributors = top_contributors[:5]

                recent_overdue_tasks = []
                for t in all_tasks:
                    if t.get("end_date") and t.get("end_date") < today_str and t.get("status") not in ["Completed", "Done"]:
                        raw_assignee = t.get("assigned_to")
                        assignee_id = raw_assignee[0] if isinstance(raw_assignee, list) and raw_assignee else (raw_assignee if raw_assignee and not isinstance(raw_assignee, list) else None)
                        assignee_name = "Unassigned"
                        if assignee_id:
                            emp = next((e for e in employees if str(e.get("employee_no_id")) == str(assignee_id) or str(e.get("id")) == str(assignee_id)), None)
                            if emp:
                                assignee_name = emp.get("name")

                        recent_overdue_tasks.append({
                            "id": str(t.get("id", "")),
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
                alerts = {"critical": [], "warnings": [], "info": []}
                overdue_projs = [p for p in projects if p.get("status") == "Active" and p.get("end_date") and p.get("end_date") < today_str]
                if overdue_projs:
                    alerts["critical"].append({
                        "type": "project_overdue", "severity": "critical",
                        "message": f"{len(overdue_projs)} projects are overdue",
                        "count": len(overdue_projs), "action_required": True, "link": "/projects"
                    })

                if pending_leaves:
                    alerts["critical"].append({
                        "type": "pending_leave_requests", "severity": "high",
                        "message": f"{len(pending_leaves)} leave requests pending approval",
                        "count": len(pending_leaves), "action_required": True, "link": "/leaves"
                    })

                low_att_emps = [c for c in attendance_concerns if c["concern_level"] == "high"]
                if low_att_emps:
                    alerts["warnings"].append({
                        "type": "low_attendance", "severity": "medium",
                        "message": f"{len(low_att_emps)} employees with critical attendance issues",
                        "count": len(low_att_emps), "action_required": False, "link": "/attendance"
                    })

                # 7. Upcoming Events
                upcoming_holidays_list = []
                for h in upcoming_holidays:
                    upcoming_holidays_list.append({
                        "name": h.get("name"), "date": h.get("date"),
                        "days_until": (datetime.strptime(h.get("date"), "%Y-%m-%d") - datetime.strptime(today_str, "%Y-%m-%d")).days,
                        "type": h.get("holiday_type")
                    })

                birthdays = []
                anniversaries = []
                for e in employees:
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
                        except Exception:
                            pass

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
                        except Exception:
                            pass

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
                    "upcoming_events": upcoming_events
                }
                return data, None

            else:
                # --- EMPLOYEE DASHBOARD ---
                employee_id = current_user.get("employee_no_id")
                if not employee_id:
                    return None, "No employee profile linked"

                emp_doc = await employees_collection.find_one({"employee_no_id": employee_id, "is_deleted": {"$ne": True}})
                if not emp_doc:
                    return None, "Employee profile not found"

                emp_profile = normalize(emp_doc)
                for k in ["hashed_password", "password"]:
                    emp_profile.pop(k, None)

                # Greeting Logic
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
                greeting_obj = {"greeting_text": greeting_text, "message": message}

                # Work Hours & Attendance Metrics
                start_of_month = datetime.utcnow().replace(day=1).strftime("%Y-%m-%d")
                today_dt = datetime.utcnow()
                today_str = today_dt.strftime("%Y-%m-%d")
                start_of_week = (today_dt - timedelta(days=today_dt.weekday())).strftime("%Y-%m-%d")

                emp_ids_to_query = [str(emp_doc["_id"])]
                if emp_doc.get("employee_no_id"):
                    emp_ids_to_query.append(emp_doc.get("employee_no_id"))

                month_attendance = await attendance_collection.find({
                    "employee_id": {"$in": emp_ids_to_query},
                    "date": {"$gte": start_of_month},
                    "is_deleted": {"$ne": True}
                }).to_list(length=None)
                att_map = {a.get("date"): a for a in month_attendance}

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

                leave_types_raw = await leave_types_collection.find({"is_deleted": {"$ne": True}}).to_list(length=None)
                leave_types = [normalize(lt) for lt in leave_types_raw]

                my_leaves_raw = await leave_requests_collection.find({"employee_id": str(emp_doc.get("_id")), "is_deleted": {"$ne": True}}).to_list(length=None)
                my_leaves = [normalize(l) for l in my_leaves_raw]

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
                emp_weekly_off = emp_doc.get("weekly_off", [6])

                for single_date in daterange(start_date_obj, current_date_obj):
                    d_str = single_date.strftime("%Y-%m-%d")
                    is_weekly_off = single_date.weekday() in emp_weekly_off
                    is_holiday = d_str in month_holidays

                    if not is_weekly_off and not is_holiday:
                        att_record = att_map.get(d_str)
                        is_leave = leave_date_map.get(d_str) == "Leave"

                        increment_total = True
                        if d_str == today_str and not att_record and not is_leave:
                            increment_total = False

                        if increment_total:
                            total_working_days_elapsed += 1

                        if att_record:
                            status = att_record.get("status", "Present")
                            att_status = (att_record.get("attendance_status") or "").lower()
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

                            wh = float(att_record.get("total_work_hours", 0))
                            hours_month += wh
                            if d_str == today_str:
                                hours_today += wh
                            if d_str >= start_of_week:
                                hours_week += wh
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
                    "half_day_days": half_day_days,
                    "permission_days": permission_days,
                    "holiday_days": len(month_holidays),
                    "leave_days": leaves_this_month,
                    "total_working_days": total_working_days_elapsed
                }

                # Task Metrics
                my_tasks_raw = await tasks_collection.find({"assigned_to": str(emp_doc["_id"]), "is_deleted": {"$ne": True}}).to_list(length=None)
                my_tasks = [normalize(t) for t in my_tasks_raw]

                task_metric_counts = {
                    "total_assigned": len(my_tasks),
                    "pending": 0,
                    "in_progress": 0,
                    "completed": 0,
                    "overdue": 0
                }

                for t in my_tasks:
                    status = t.get("status")
                    if status in ["Completed", "Done"]:
                        task_metric_counts["completed"] += 1
                    elif status == "In Progress":
                        task_metric_counts["in_progress"] += 1
                    else:
                        task_metric_counts["pending"] += 1

                    if t.get("end_date") and t.get("end_date") < today_str and status not in ["Completed", "Done"]:
                        task_metric_counts["overdue"] += 1

                # Projects
                all_projects_raw = await projects_collection.find({"is_deleted": {"$ne": True}}).to_list(length=None)
                all_projects = [normalize(p) for p in all_projects_raw]
                emp_oid = str(emp_doc["_id"])
                my_projects = []
                for p in all_projects:
                    members = p.get("team_member_ids", [])
                    leaders = p.get("team_leader_ids", [])
                    managers = p.get("project_manager_ids", [])

                    role = None
                    if emp_oid in managers:
                        role = "Project Manager"
                    elif emp_oid in leaders:
                        role = "Team Leader"
                    elif emp_oid in members:
                        role = "Team Member"

                    if role:
                        my_projects.append({
                            "name": p.get("name"),
                            "role": role,
                            "status": p.get("status"),
                            "deadline": p.get("end_date"),
                            "logo": p.get("logo")
                        })

                # Birthdays
                all_employees_raw = await employees_collection.find({"is_deleted": {"$ne": True}}).limit(1000).to_list(length=1000)
                all_employees = [normalize(e) for e in all_employees_raw]
                birthdays = []
                today_date = datetime.utcnow()
                for e in all_employees:
                    dob_str = e.get("date_of_birth")
                    if dob_str:
                        try:
                            dob = datetime.strptime(dob_str, "%Y-%m-%d")
                            this_year_bday = dob.replace(year=today_date.year)
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
                        except Exception:
                            pass

                birthdays.sort(key=lambda x: x.get("date"))

                # Leave Insights
                leave_insights = {
                    "total_allotted": 0,
                    "total_used": 0,
                    "total_pending": 0,
                    "total_available": 0,
                    "details": []
                }

                leave_used_map = {}
                leave_pending_map = {}
                for l in my_leaves:
                    lt_id = str(l.get("leave_type_id"))
                    status = l.get("status")
                    days = float(l.get("total_days", 0))
                    if status == "Approved":
                        leave_used_map[lt_id] = leave_used_map.get(lt_id, 0) + days
                        leave_insights["total_used"] += days
                    elif status == "Pending":
                        leave_pending_map[lt_id] = leave_pending_map.get(lt_id, 0) + days
                        leave_insights["total_pending"] += days

                for lt in leave_types:
                    lt_id = str(lt.get("id"))
                    allowance = float(lt.get("number_of_days", 0))
                    used = leave_used_map.get(lt_id, 0)
                    available = allowance - used

                    leave_insights["total_allotted"] += allowance
                    leave_insights["total_available"] += available

                    leave_insights["details"].append({
                        "id": lt_id,
                        "type": lt.get("name"),
                        "code": lt.get("code"),
                        "total": allowance,
                        "used": used,
                        "available": max(0, available),
                        "pending": leave_pending_map.get(lt_id, 0)
                    })

                data = {
                    "type": "employee",
                    "greeting": greeting_obj,
                    "profile": emp_profile,
                    "work_hours": work_hours,
                    "attendance_metrics": attendance_metrics,
                    "projects": my_projects,
                    "task_metrics": task_metric_counts,
                    "upcoming_holidays": upcoming_holidays,
                    "birthdays": birthdays,
                    "leave_insights": leave_insights
                }
                return data, None

        except Exception as e:
            traceback.print_exc()
            return None, str(e)
