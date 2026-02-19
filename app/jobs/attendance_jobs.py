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
        existing_employee_ids = {str(r.get("employee_id")) for r in existing_records}
        
        # Check if this date is a holiday
        holiday = await repo.holidays.find_one({"date": target_date})
        holiday_name = holiday.get("name") if holiday else None
        
        # Fetch all approved leaves that overlap with this date
        approved_leaves = await repo.leave_requests.find({
            "status": "Approved",
            "start_date": {"$lte": target_date},
            "end_date": {"$gte": target_date}
        }).to_list(length=None)
        
        # Create a map of employee_id -> leave reason
        leave_map = {}
        for leave in approved_leaves:
            emp_id = str(leave.get("employee_id"))
            leave_map[emp_id] = leave.get("reason", "On Leave")
        
        # Parse date to check if it's a weekend
        dt_parsed = datetime.strptime(target_date, "%Y-%m-%d")
        is_sunday = dt_parsed.weekday() == 6
        
        records_created = 0
        records_to_insert = []
        
        for emp in employees:
            emp_no_id = str(emp.get("employee_no_id"))
            emp_id = str(emp.get("_id"))
            
            # --- SHIFT FILTERING START ---
            if shift_type_filter:
                emp_shift_id = emp.get("shift_id")
                is_night_shift = False # Default to Day
                
                # Check assigned shift
                if emp_shift_id and emp_shift_id in shift_map:
                    is_night_shift = shift_map[emp_shift_id].get("is_night_shift", False)
                elif emp.get("department"):
                     # Fallback to Dept Default
                     # We assume department logic handled elsewhere or pre-fetched, 
                     # but for batch job, let's keep it simple: 
                     # If no personal shift, check if we can infer from department default?
                     # Fetching department for every employee is slow.
                     # Optimisation: We could fetch departments once.
                     pass 

                # Filter Logic
                if shift_type_filter == "Day" and is_night_shift:
                    continue # Skip Night shift employees in Day job
                
                if shift_type_filter == "Night" and not is_night_shift:
                    continue # Skip Day shift employees in Night job
            # --- SHIFT FILTERING END ---
            
            # Skip if employee already has an attendance record for this date
            if emp_no_id in existing_employee_ids:
                continue
            
            # Determine status and notes
            status = None
            notes = None
            
            if holiday_name:
                # Company-wide holiday
                status = "Holiday"
                notes = holiday_name
            elif is_sunday:
                # Sunday (weekend)
                status = "Holiday"
                notes = "Sunday"
            elif emp_id in leave_map:
                # Employee on approved leave
                status = "Leave"
                notes = leave_map[emp_id]
            else:
                # Employee was absent
                if preplanned_only:
                    # If we are only looking for pre-planned (Morning job), skip absences
                    continue
                else:
                    status = "Absent"
                    notes = "No attendance recorded"
            
            if status:
                # Create attendance record
                attendance_data = {
                    "employee_id": emp_no_id,
                    "date": target_date,
                    "status": status,
                    "notes": notes,
                    "clock_in": None,
                    "clock_out": None,
                    "total_work_hours": 0.0,
                    "overtime_hours": 0.0,
                    "device_type": "Auto Sync",
                    "created_at": datetime.utcnow()
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
