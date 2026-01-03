
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from app.crud.repository import repository as repo
from app.auth import get_current_user, verify_token
from typing import List, Optional
from datetime import datetime, timedelta

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
            employees = await repo.get_employees()
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
                # Fallback if no linked employee profile
                return JSONResponse(status_code=400, content={"success": False, "message": "No employee profile linked"})

            # 1. Profile
            # Get employee details
            emp_doc = await repo.employees.find_one({"employee_no_id": employee_id})
            if not emp_doc:
                 return JSONResponse(status_code=404, content={"success": False, "message": "Employee profile not found"})
            
            from app.utils import normalize
            emp_profile = normalize(emp_doc)
            if "hashed_password" in emp_profile: del emp_profile["hashed_password"]
            if "password" in emp_profile: del emp_profile["password"]

            # 2. Attendance Summary (Current Month)
            attendance_data = await repo.get_employee_attendance(employee_id)
            att_metrics = attendance_data.get("metrics", {})

            # 3. Leave Balance
            leave_types = await repo.get_leave_types()
            my_leaves = await repo.get_leave_requests(str(emp_doc.get("_id"))) 
            
            leave_balance = []
            for lt in leave_types:
                total_allowed = lt.get("number_of_days", 0)
                used = 0
                for l in my_leaves:
                    if l.get("leave_type_id") == lt.get("id") and l.get("status") == "Approved":
                         used += float(l.get("total_days", 0))
                
                leave_balance.append({
                    "type": lt.get("name"),
                    "balance": total_allowed - used,
                    "total": total_allowed,
                    "used": used
                })

            # 4. My Tasks
            my_tasks = await repo.get_tasks(assigned_to=employee_id) 
            task_overview = {
                "total_assigned": len(my_tasks),
                "pending": 0,
                "in_progress": 0,
                "completed": 0,
                "overdue": 0
            }
            
            for t in my_tasks:
                status = t.get("status")
                if status == "Completed":
                    task_overview["completed"] += 1
                else:
                    task_overview["pending"] += 1
                    if status == "In Progress":
                        task_overview["in_progress"] += 1
                    
                    if t.get("end_date") and t.get("end_date") < today_str:
                        task_overview["overdue"] += 1

            # Recent Tasks
            sorted_tasks = sorted(my_tasks, key=lambda x: x.get("created_at") or "", reverse=True)
            recent_tasks = sorted_tasks[:5]

            # 5. My Projects
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
                        "id": p.get("id"),
                        "name": p.get("name"),
                        "status": p.get("status"),
                        "role": role,
                        "end_date": p.get("end_date")
                    })
            
            # 6. Recent Leaves
            sorted_leaves = sorted(my_leaves, key=lambda x: x.get("created_at", ""), reverse=True)
            recent_leaves = sorted_leaves[:5]

            data = {
                "type": "employee",
                "profile": emp_profile,
                "attendance_summary": {
                    "present_days": att_metrics.get("present", 0),
                    "absent_days": att_metrics.get("absent", 0),
                    "late_days": att_metrics.get("late", 0),
                    "half_days": 0, # Metric not standardly calc'd yet
                    "total_working_days": att_metrics.get("total_records", 0), # Approx
                    "average_work_hours": att_metrics.get("avg_work_hours", 0)
                },
                "leave_balance": leave_balance,
                "my_tasks": {
                    "overview": task_overview,
                    "recent_tasks": recent_tasks
                },
                "my_projects": my_projects,
                "recent_leaves": recent_leaves,
                "upcoming_holidays": upcoming_holidays
            }
            
            return JSONResponse(status_code=200, content={"success": True, "data": data})

    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "message": str(e)})
