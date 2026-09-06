from datetime import datetime, timedelta
from typing import Optional
import logging
from bson import ObjectId
from zoneinfo import ZoneInfo

from app.database import (
    system_configurations_collection,
    employees_collection,
    shifts_collection,
    attendance_collection,
    holidays_collection,
    leave_requests_collection,
    leave_types_collection,
)

logger = logging.getLogger(__name__)


async def get_company_now() -> datetime:
    try:
        config = await system_configurations_collection.find_one({"key": "company_timezone"})
        tz_name = config.get("value", "UTC") if config else "UTC"
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("UTC")
    return datetime.now(tz)


async def generate_attendance_for_date(target_date: str = None, preplanned_only: bool = False, shift_type_filter: str = None) -> dict:
    """
    Generate attendance records for a specific date.
    Creates Absent, Holiday, or Leave records for employees who didn't clock in.
    """
    try:
        today_str = datetime.utcnow().strftime("%Y-%m-%d")

        if not target_date:
            if preplanned_only:
                target_date = today_str
            else:
                yesterday = datetime.utcnow() - timedelta(days=1)
                target_date = yesterday.strftime("%Y-%m-%d")
        
        if target_date > today_str:
            logger.info(f"Skipping future date: {target_date}")
            return {"success": False, "message": "Cannot generate records for future dates"}
        
        logger.info(f"Generating attendance for {target_date} (Preplanned: {preplanned_only}, Shift: {shift_type_filter})")
        
        employees = await employees_collection.find().to_list(length=None)
        shifts = await shifts_collection.find().to_list(length=None)
        shift_map = {str(s["_id"]): s for s in shifts}
        
        existing_records = await attendance_collection.find({"date": target_date}).to_list(length=None)
        existing_employee_ids = set()
        for r in existing_records:
            if r.get("employee_id"):
                existing_employee_ids.add(str(r.get("employee_id")))
        
        holiday = await holidays_collection.find_one({"date": target_date})
        holiday_name = holiday.get("name") if holiday else None
        
        sandwich_setting = await system_configurations_collection.find_one({"key": "sandwich_rule"})
        apply_sandwich_rule = sandwich_setting.get("value", False) if sandwich_setting else False
        
        approved_leaves = await leave_requests_collection.find({
            "status": "Approved",
            "start_date": {"$lte": target_date},
            "end_date": {"$gte": target_date}
        }).to_list(length=None)
        
        leave_map = {}
        for leave in approved_leaves:
            emp_id_str = str(leave.get("employee_id"))
            leave_type_code = None
            leave_type_id = leave.get("leave_type_id")
            if leave_type_id:
                try:
                    from bson import ObjectId as _ObjId
                    lt = await leave_types_collection.find_one({"_id": _ObjId(leave_type_id)})
                    if lt:
                        leave_type_code = lt.get("code")
                except Exception:
                    pass

            leave_map[emp_id_str] = {
                "reason": leave.get("reason", "On Leave"),
                "leave_type_code": leave_type_code,
                "leave_duration_type": leave.get("leave_duration_type", "Single"),
                "half_day_session": leave.get("half_day_session"),
            }

        dt_parsed = datetime.strptime(target_date, "%Y-%m-%d")
        day_of_week = dt_parsed.weekday()

        records_created = 0
        records_to_insert = []
        
        for emp in employees:
            emp_no_id = str(emp.get("employee_no_id"))
            emp_mongo_id = str(emp.get("_id"))
            
            if shift_type_filter:
                emp_shift_id = emp.get("shift_id")
                is_night_shift = False
                
                if emp_shift_id and emp_shift_id in shift_map:
                    is_night_shift = shift_map[emp_shift_id].get("is_night_shift", False)
                elif emp.get("department"):
                    pass 

                if shift_type_filter == "Day" and is_night_shift:
                    continue
                
                if shift_type_filter == "Night" and not is_night_shift:
                    continue
            
            if emp_no_id in existing_employee_ids or emp_mongo_id in existing_employee_ids:
                continue
            
            status = None
            notes = None
            leave_type_code = None
            attendance_status = None
            is_half_day = False
            
            emp_weekly_off = emp.get("weekly_off", [6])
            is_weekly_off = day_of_week in emp_weekly_off

            leave_info = leave_map.get(emp_mongo_id) or leave_map.get(emp_no_id)

            if holiday_name or is_weekly_off:
                sandwiched = False
                if apply_sandwich_rule and leave_info:
                    sandwiched = True

                if sandwiched:
                    status = "Leave"
                    attendance_status = leave_info.get("leave_type_code") or "Leave"
                    leave_type_code = leave_info.get("leave_type_code")
                    notes = "Leave (Sandwich Rule)"
                    is_half_day = False
                elif holiday_name:
                    status = "Holiday"
                    attendance_status = "Holiday"
                    notes = holiday_name
                else:
                    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
                    off_day_name = day_names[day_of_week] if 0 <= day_of_week <= 6 else "Weekly Off"
                    status = "Holiday"
                    attendance_status = "Holiday"
                    notes = off_day_name
            elif leave_info:
                duration_type = leave_info.get("leave_duration_type", "Single")
                leave_type_code = leave_info.get("leave_type_code")

                if duration_type == "Half Day":
                    status = "Leave"
                    attendance_status = "Half Day"
                    is_half_day = True
                    notes = leave_info.get("reason", "Half Day Leave")
                else:
                    status = "Leave"
                    attendance_status = leave_type_code or "Leave"
                    notes = leave_info.get("reason", "On Leave")
            else:
                if preplanned_only:
                    continue
                else:
                    status = "Absent"
                    attendance_status = "Absent"
                    notes = "No attendance recorded"
            
            if status:
                attendance_data = {
                    "employee_id": emp_mongo_id,
                    "date": target_date,
                    "status": status,
                    "attendance_status": attendance_status,
                    "leave_type_code": leave_type_code,
                    "is_half_day": is_half_day,
                    "notes": notes,
                    "clock_in": None,
                    "clock_out": None,
                    "total_work_hours": 0.0,
                    "overtime_hours": 0.0,
                    "device_type": "Auto Sync",
                    "created_at": datetime.utcnow()
                }
                records_to_insert.append(attendance_data)

        if records_to_insert:
            result = await attendance_collection.insert_many(records_to_insert)
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
    try:
        company_now = await get_company_now()
        today_str = company_now.strftime("%Y-%m-%d")
        logger.info(f"Starting morning pre-planned attendance generation for {today_str} (Local)")
        return await generate_attendance_for_date(today_str, preplanned_only=True)
    except Exception as e:
        logger.error(f"Morning pre-planned generation failed: {str(e)}")
        return {"success": False, "message": str(e)}


async def generate_daily_attendance_records():
    try:
        company_now = await get_company_now()
        today_str = company_now.strftime("%Y-%m-%d")
        logger.info(f"Starting Day Shift attendance generation for {today_str}")
        return await generate_attendance_for_date(today_str, preplanned_only=False, shift_type_filter="Day")
    except Exception as e:
        logger.error(f"Daily Day Shift job failed: {str(e)}")
        return {"success": False, "message": str(e)}


async def generate_night_shift_attendance_records():
    try:
        company_now = await get_company_now()
        yesterday_dt = company_now - timedelta(days=1)
        yesterday_str = yesterday_dt.strftime("%Y-%m-%d")
        logger.info(f"Starting Night Shift attendance generation for {yesterday_str}")
        return await generate_attendance_for_date(yesterday_str, preplanned_only=False, shift_type_filter="Night")
    except Exception as e:
        logger.error(f"Daily Night Shift job failed: {str(e)}")
        return {"success": False, "message": str(e)}


async def process_uncompensated_permissions():
    try:
        logger.info("Starting uncompensated permissions processing.")
        uncompensated_permissions = await leave_requests_collection.find({
            "status": "Approved",
            "leave_duration_type": "Permission",
            "is_compensated": {"$ne": True},
            "start_date": {"$lt": datetime.utcnow().strftime("%Y-%m-%d")}
        }).to_list(length=None)
        
        lop_type = await leave_types_collection.find_one({"code": "LOP"})
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
            
            await leave_requests_collection.update_one(
                {"_id": perm_id},
                {"$set": update_data}
            )
            
            emp = await employees_collection.find_one({"_id": ObjectId(emp_id)})
            if emp:
                await attendance_collection.update_one(
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
    try:
        company_now = await get_company_now()
        yesterday_dt = company_now - timedelta(days=1)
        day_before_dt = company_now - timedelta(days=2)
        
        yesterday_str = yesterday_dt.strftime("%Y-%m-%d")
        day_before_str = day_before_dt.strftime("%Y-%m-%d")
        
        logger.info(f"Evaluating unauthorized absences for {day_before_str} and {yesterday_str}")
        
        yesterday_absences = await attendance_collection.find({
            "date": yesterday_str,
            "status": "Absent"
        }).to_list(length=None)
        
        if not yesterday_absences:
            logger.info(f"No unauthorized absences found for {yesterday_str}")
            return {"success": True, "message": "No absences found yesterday"}
            
        lop_type = await leave_types_collection.find_one({"code": "LOP"})
        if not lop_type:
            logger.error("LOP leave type not found.")
            return {"success": False, "message": "LOP leave type not found"}
            
        converted_count = 0
        
        for absence in yesterday_absences:
            emp_id = absence.get("employee_id")
            
            prev_record = await attendance_collection.find_one({
                "employee_id": emp_id,
                "date": {"$lt": yesterday_str},
                "status": {"$ne": "Holiday"}
            }, sort=[("date", -1)])
            
            if prev_record and (
                prev_record.get("status") == "Absent" or 
                (prev_record.get("status") == "Leave" and prev_record.get("attendance_status") == "LOP")
            ):
                await attendance_collection.update_one(
                    {"_id": absence["_id"]},
                    {"$set": {
                        "status": "Leave",
                        "attendance_status": "LOP",
                        "leave_type_code": "LOP",
                        "notes": "Auto-converted to LOP due to consecutive unauthorized absence (2+ working days)",
                        "updated_at": datetime.utcnow()
                    }}
                )
                
                if prev_record.get("status") == "Absent":
                    await attendance_collection.update_one(
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
