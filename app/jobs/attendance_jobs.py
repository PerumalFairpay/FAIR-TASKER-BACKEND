from datetime import datetime, timedelta
from app.crud.repository import repository as repo
from typing import Optional
import logging

logger = logging.getLogger(__name__)

async def generate_attendance_for_date(target_date: str = None, preplanned_only: bool = False) -> dict:
    """
    Generate attendance records for a specific date.
    Creates Absent, Holiday, or Leave records for employees who didn't clock in.
    
    Args:
        target_date: Date in YYYY-MM-DD format. Defaults to yesterday.
        preplanned_only: If True, only generates Holiday and Leave records (skips Absent).
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
        
        logger.info(f"Generating attendance records for {target_date} (Preplanned Only: {preplanned_only})")
        
        # Fetch all employees
        employees = await repo.employees.find().to_list(length=None)
        
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
    Night job (11:57 PM IST) to generate ALL missing records for the ending day.
    This fills in 'Absent' records for anyone who didn't clock in.
    """
    try:
        # Calculate current date in IST (UTC + 5:30)
        ist_now = datetime.utcnow() + timedelta(hours=5, minutes=30)
        today_str = ist_now.strftime("%Y-%m-%d")
        
        logger.info(f"Starting end-of-day attendance generation for {today_str} (IST)")
        return await generate_attendance_for_date(today_str, preplanned_only=False)
    except Exception as e:
        logger.error(f"Daily attendance job failed: {str(e)}")
        return {"success": False, "message": str(e)}
