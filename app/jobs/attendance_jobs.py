from datetime import datetime, timedelta
from app.crud.repository import repository as repo
from typing import Optional
import logging

logger = logging.getLogger(__name__)

from bson import ObjectId

async def generate_attendance_for_date(target_date: str = None, preplanned_only: bool = False, shift_type_filter: str = None) -> dict:
    """
    Generate attendance records for a specific date.
    Creates Absent, Holiday, or Leave records for employees who didn't clock in.
    
    Args:
        target_date: Date in YYYY-MM-DD format. Defaults to yesterday.
        preplanned_only: If True, only generates Holiday and Leave records (skips Absent).
        shift_type_filter: "Day" or "Night". If provided, only processes employees in that shift type.
                           If None, processes all employees.
                           "Day" includes employees with no assigned shift (default).
    """
    try:
        today_str = datetime.utcnow().strftime("%Y-%m-%d")

        # Default definition logic
        if not target_date:
            # If preplanned (morning job), default to TODAY
            if preplanned_only:
                target_date = today_str
            else:
                # If full run (end of day job), default to YESTERDAY (safe default)
                # But typically the scheduler will pass 'today' for the night job.
                yesterday = datetime.utcnow() - timedelta(days=1)
                target_date = yesterday.strftime("%Y-%m-%d")
        
        # Don't generate records for future dates
        if target_date > today_str:
            logger.info(f"Skipping future date: {target_date}")
            return {"success": False, "message": "Cannot generate records for future dates"}
        
        logger.info(f"Generating attendance for {target_date} (Preplanned: {preplanned_only}, Shift: {shift_type_filter})")
        
        # Fetch all employees
        employees = await repo.employees.find().to_list(length=None)
        
        # Fetch all shifts to map ID -> Shift Type
        shifts = await repo.shifts.find().to_list(length=None)
        shift_map = {str(s["_id"]): s for s in shifts}
        
        # Fetch existing attendance records for this date
        existing_records = await repo.attendance.find({"date": target_date}).to_list(length=None)
        existing_employee_ids = set()
        for r in existing_records:
            # Add both possible ID formats to the set to be safe
            if r.get("employee_id"):
                existing_employee_ids.add(str(r.get("employee_id")))
        
        # Check if this date is a holiday
        holiday = await repo.holidays.find_one({"date": target_date})
        holiday_name = holiday.get("name") if holiday else None
        
        # Fetch all approved leaves that overlap with this date
        approved_leaves = await repo.leave_requests.find({
            "status": "Approved",
            "start_date": {"$lte": target_date},
            "end_date": {"$gte": target_date}
        }).to_list(length=None)
        
        # Create a map of employee_id -> leave info
        # Map both ObjectId and Employee No if possible
        leave_map = {}
        for leave in approved_leaves:
            emp_id_str = str(leave.get("employee_id"))

            # Fetch leave type code
            leave_type_code = None
            leave_type_id = leave.get("leave_type_id")
            if leave_type_id:
                try:
                    from bson import ObjectId as _ObjId
                    lt = await repo.leave_types.find_one({"_id": _ObjId(leave_type_id)})
                    if lt:
                        leave_type_code = lt.get("code")
                except Exception:
                    pass

            leave_map[emp_id_str] = {
                "reason":             leave.get("reason", "On Leave"),
                "leave_type_code":    leave_type_code,
                "leave_duration_type": leave.get("leave_duration_type", "Single"),
                "half_day_session":   leave.get("half_day_session"),
            }

        
        # Parse date once (used inside loop for per-employee weekly_off check)
        dt_parsed = datetime.strptime(target_date, "%Y-%m-%d")
        day_of_week = dt_parsed.weekday()  # 0=Mon, …, 6=Sun

        records_created = 0
        records_to_insert = []
        
        for emp in employees:
            emp_no_id = str(emp.get("employee_no_id"))
            emp_mongo_id = str(emp.get("_id"))
            
            # --- SHIFT FILTERING START ---
            if shift_type_filter:
                emp_shift_id = emp.get("shift_id")
                is_night_shift = False # Default to Day
                
                # Check assigned shift
                if emp_shift_id and emp_shift_id in shift_map:
                    is_night_shift = shift_map[emp_shift_id].get("is_night_shift", False)
                elif emp.get("department"):
                     # Fallback to Dept Default
                     pass 

                # Filter Logic
                if shift_type_filter == "Day" and is_night_shift:
                    continue # Skip Night shift employees in Day job
                
                if shift_type_filter == "Night" and not is_night_shift:
                    continue # Skip Day shift employees in Night job
            # --- SHIFT FILTERING END ---
            
            # Skip if employee already has an attendance record for this date
            # Check BOTH ID formats to prevent duplicates
            if emp_no_id in existing_employee_ids or emp_mongo_id in existing_employee_ids:
                continue
            
            # Determine status and notes
            status = None
            notes  = None
            leave_type_code    = None
            attendance_status  = None
            is_half_day        = False
            
            # --- PER-EMPLOYEE WEEKLY OFF CHECK ---
            # Each employee can have a custom weekly_off list (e.g., [5] = Saturday, [6] = Sunday)
            # Defaults to [6] (Sunday) to preserve backward-compatibility.
            emp_weekly_off = emp.get("weekly_off", [6])
            is_weekly_off = day_of_week in emp_weekly_off
            # --- END WEEKLY OFF CHECK ---

            leave_info = leave_map.get(emp_mongo_id) or leave_map.get(emp_no_id)

            if holiday_name:
                # Company-wide holiday
                status           = "Holiday"
                attendance_status = "Holiday"
                notes            = holiday_name
            elif is_weekly_off:
                # Employee's personal weekly off day
                day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
                off_day_name = day_names[day_of_week] if 0 <= day_of_week <= 6 else "Weekly Off"
                status           = "Holiday"
                attendance_status = "Holiday"
                notes            = off_day_name
            elif leave_info:
                # Employee on approved leave
                duration_type = leave_info.get("leave_duration_type", "Single")
                leave_type_code = leave_info.get("leave_type_code")

                if duration_type == "Half Day":
                    status           = "Leave"
                    attendance_status = "Half Day"
                    is_half_day      = True
                    notes            = leave_info.get("reason", "Half Day Leave")
                else:
                    status           = "Leave"
                    attendance_status = leave_type_code or "Leave"
                    notes            = leave_info.get("reason", "On Leave")
            else:
                # Employee was absent
                if preplanned_only:
                    # If we are only looking for pre-planned (Morning job), skip absences
                    continue
                else:
                    status           = "Absent"
                    attendance_status = "Absent"
                    notes            = "No attendance recorded"
            
            if status:
                # Create attendance record using MongoDB ObjectId as the standard employee_id
                attendance_data = {
                    "employee_id":       emp_mongo_id,
                    "date":              target_date,
                    "status":            status,
                    "attendance_status": attendance_status,
                    "leave_type_code":   leave_type_code,
                    "is_half_day":       is_half_day,
                    "notes":             notes,
                    "clock_in":          None,
                    "clock_out":         None,
                    "total_work_hours":  0.0,
                    "overtime_hours":    0.0,
                    "device_type":       "Auto Sync",
                    "created_at":        datetime.utcnow()
                }
                
                records_to_insert.append(attendance_data)

        
        # Bulk insert records
        if records_to_insert:
            result = await repo.attendance.insert_many(records_to_insert)
            records_created = len(result.inserted_ids)
            logger.info(f"Created {records_created} attendance records for {target_date}")
        else:
            logger.info(f"No new attendance records needed for {target_date}")
        
        return {
            "success": True,
            "date": target_date,
            "records_created": records_created,
            "message": f"Generated {records_created} attendance records for {target_date}"
        }
        
    except Exception as e:
        logger.error(f"Error generating attendance records: {str(e)}")
        return {
            "success": False,
            "message": f"Error: {str(e)}"
        }

async def generate_today_preplanned_records():
    """
    Morning job (12:05 AM IST) to generate Leave & Holiday records for the starting day.
    Does NOT generate 'Absent' records.
    """
    try:
        # Calculate current date in IST (UTC + 5:30)
        ist_now = datetime.utcnow() + timedelta(hours=5, minutes=30)
        today_str = ist_now.strftime("%Y-%m-%d")
        
        logger.info(f"Starting morning pre-planned attendance generation for {today_str} (IST)")
        return await generate_attendance_for_date(today_str, preplanned_only=True)
    except Exception as e:
        logger.error(f"Morning pre-planned generation failed: {str(e)}")
        return {"success": False, "message": str(e)}

async def generate_daily_attendance_records():
    """
    Night job (11:57 PM IST) to generate Missing records for DAY SHIFT employees.
    """
    try:
        ist_now = datetime.utcnow() + timedelta(hours=5, minutes=30)
        today_str = ist_now.strftime("%Y-%m-%d")
        
        logger.info(f"Starting Day Shift attendance generation for {today_str}")
        return await generate_attendance_for_date(today_str, preplanned_only=False, shift_type_filter="Day")
    except Exception as e:
        logger.error(f"Daily Day Shift job failed: {str(e)}")
        return {"success": False, "message": str(e)}

async def generate_night_shift_attendance_records():
    """
    Morning job (08:00 AM IST) to generate Missing records for NIGHT SHIFT employees (for Previous Day).
    """
    try:
        ist_now = datetime.utcnow() + timedelta(hours=5, minutes=30)
        # For Night Shift, "Absent" is determined the NEXT morning.
        # So we are looking for records from YESTERDAY.
        yesterday_dt = ist_now - timedelta(days=1)
        yesterday_str = yesterday_dt.strftime("%Y-%m-%d")
        
        logger.info(f"Starting Night Shift attendance generation for {yesterday_str}")
        return await generate_attendance_for_date(yesterday_str, preplanned_only=False, shift_type_filter="Night")
    except Exception as e:
        logger.error(f"Daily Night Shift job failed: {str(e)}")
        return {"success": False, "message": str(e)}

async def process_uncompensated_permissions():
    """
    Job to convert Approved, Uncompensated "Permission" records to Half-Day LOP.
    This should typically run at the end of the month or beginning of the next month.
    """
    try:
        logger.info("Starting uncompensated permissions processing.")
        
        # Find all Approved Permission requests that are not compensated
        uncompensated_permissions = await repo.leave_requests.find({
            "status": "Approved",
            "leave_duration_type": "Permission",
            "is_compensated": {"$ne": True},
            "start_date": {"$lt": datetime.utcnow().strftime("%Y-%m-%d")} # Process past permissions
        }).to_list(length=None)
        
        lop_type = await repo.leave_types.find_one({"code": "LOP"})
        if not lop_type:
            logger.error("LOP leave type not found. Cannot convert permissions.")
            return {"success": False, "message": "LOP leave type not found"}
            
        lop_type_id = str(lop_type["_id"])
        converted_count = 0
        
        for perm in uncompensated_permissions:
            perm_id = perm["_id"]
            emp_id = perm.get("employee_id")
            date = perm.get("start_date")
            
            update_data = {
                "leave_type_id": lop_type_id,
                "leave_duration_type": "Half Day",
                "half_day_session": "First Half",
                "total_days": 0.5,
                "reason": perm.get("reason", "") + " (Converted from uncompensated permission)",
                "is_compensated": True
            }
            
            await repo.leave_requests.update_one(
                {"_id": perm_id},
                {"$set": update_data}
            )
            
            emp = await repo.employees.find_one({"_id": ObjectId(emp_id)})
            if emp:
                await repo.attendance.update_one(
                    {"employee_id": str(emp.get("_id")), "date": date},
                    {"$set": {
                        "attendance_status": "Half Day",
                        "is_half_day": True,
                        "leave_type_code": "LOP",
                        "notes": "Uncompensated permission converted to Half-Day LOP",
                        "updated_at": datetime.utcnow()
                    }}
                )
            converted_count += 1
            
        logger.info(f"Successfully converted {converted_count} uncompensated permissions to Half-Day LOP.")
        return {"success": True, "converted_count": converted_count}
    except Exception as e:
        logger.error(f"Error processing uncompensated permissions: {str(e)}")
        return {"success": False, "message": str(e)}

async def process_unauthorized_absences():
    """
    Daily job to check for 2 consecutive days of unauthorized absence and mark them as LOP.
    """
    try:
        ist_now = datetime.utcnow() + timedelta(hours=5, minutes=30)
        yesterday_dt = ist_now - timedelta(days=1)
        day_before_dt = ist_now - timedelta(days=2)
        
        yesterday_str = yesterday_dt.strftime("%Y-%m-%d")
        day_before_str = day_before_dt.strftime("%Y-%m-%d")
        
        logger.info(f"Evaluating unauthorized absences for {day_before_str} and {yesterday_str}")
        
        # Find employees who were absent yesterday
        yesterday_absences = await repo.attendance.find({
            "date": yesterday_str,
            "status": "Absent"
        }).to_list(length=None)
        
        if not yesterday_absences:
            logger.info(f"No unauthorized absences found for {yesterday_str}")
            return {"success": True, "message": "No absences found yesterday"}
            
        lop_type = await repo.leave_types.find_one({"code": "LOP"})
        if not lop_type:
            logger.error("LOP leave type not found.")
            return {"success": False, "message": "LOP leave type not found"}
            
        converted_count = 0
        
        for absence in yesterday_absences:
            emp_id = absence.get("employee_id")
            
            # Find the MOST RECENT record before yesterday that is NOT a Holiday
            # This identifies the "Previous Working Day"
            prev_record = await repo.attendance.find_one({
                "employee_id": emp_id,
                "date": {"$lt": yesterday_str},
                "status": {"$ne": "Holiday"}
            }, sort=[("date", -1)])
            
            # If the previous working day was also an unauthorized absence (Absent or auto-converted LOP)
            if prev_record and (
                prev_record.get("status") == "Absent" or 
                (prev_record.get("status") == "Leave" and prev_record.get("attendance_status") == "LOP")
            ):
                # Mark YESTERDAY as LOP
                await repo.attendance.update_one(
                    {"_id": absence["_id"]},
                    {"$set": {
                        "status": "Leave",
                        "attendance_status": "LOP",
                        "leave_type_code": "LOP",
                        "notes": "Auto-converted to LOP due to consecutive unauthorized absence (2+ working days)",
                        "updated_at": datetime.utcnow()
                    }}
                )
                
                # If the PREVIOUS record was still marked as "Absent", update it to "LOP" too
                # (This happens the first time we identify a 2-day consecutive block)
                if prev_record.get("status") == "Absent":
                    await repo.attendance.update_one(
                        {"_id": prev_record["_id"]},
                        {"$set": {
                            "status": "Leave",
                            "attendance_status": "LOP",
                            "leave_type_code": "LOP",
                            "notes": "Auto-converted to LOP due to consecutive unauthorized absence (2+ working days)",
                            "updated_at": datetime.utcnow()
                        }}
                    )
                
                converted_count += 1
                
        logger.info(f"Processed {len(yesterday_absences)} absences. Converted {converted_count} instances to LOP for consecutive absences.")
        return {"success": True, "converted_count": converted_count}
        
    except Exception as e:
        logger.error(f"Error processing unauthorized absences: {str(e)}")
        return {"success": False, "message": str(e)}
