from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta, time as _time
from zoneinfo import ZoneInfo
from bson import ObjectId
from pymongo import UpdateOne
import pandas as pd
import io
import traceback
from app.database import (
    attendance_collection,
    employees_collection,
    shifts_collection,
    departments_collection,
    system_configurations_collection,
    leave_requests_collection,
    leave_types_collection,
    pending_biometric_logs_collection
)
from app.models import (
    AttendanceCreate,
    AttendanceUpdate,
    AttendanceAdminEdit,
    BiometricLogItem
)
from app.utils import normalize, get_employee_basic_details


class AttendanceService:

    @staticmethod
    async def get_dashboard_metrics(employee_id: Optional[str] = None) -> dict:
        try:
            today = datetime.now().date()
            start_of_today = today.strftime("%Y-%m-%d")
            start_of_month = today.replace(day=1).strftime("%Y-%m-%d")
            start_of_year = today.replace(month=1, day=1).strftime("%Y-%m-%d")

            async def aggregate_stats(start_date: str, end_date: str = None):
                match_query = {"date": {"$gte": start_date}, "is_deleted": {"$ne": True}}
                if end_date:
                    match_query["date"]["$lte"] = end_date
                if employee_id:
                    match_query["employee_id"] = employee_id

                pipeline_status = [
                    {"$match": match_query},
                    {"$group": {"_id": "$status", "count": {"$sum": 1}}},
                ]
                pipeline_detail = [
                    {"$match": match_query},
                    {"$group": {"_id": "$attendance_status", "count": {"$sum": 1}}},
                ]

                status_cursor = await attendance_collection.aggregate(pipeline_status).to_list(length=None)
                detail_cursor = await attendance_collection.aggregate(pipeline_detail).to_list(length=None)

                present_total = 0
                absent = 0
                leave = 0
                holiday = 0

                for doc in status_cursor:
                    sk = str(doc["_id"] or "").lower()
                    count = doc["count"]
                    if sk == "present":
                        present_total = count
                    elif sk == "absent":
                        absent = count
                    elif sk == "leave":
                        leave = count
                    elif sk == "holiday":
                        holiday = count

                on_time = 0
                late = 0
                permission = 0
                half_day = 0

                for doc in detail_cursor:
                    sk = str(doc["_id"] or "").lower()
                    count = doc["count"]
                    if sk == "ontime":
                        on_time = count
                    elif sk == "late":
                        late = count
                    elif sk == "permission":
                        permission = count
                    elif sk == "half day":
                        half_day = count

                return {
                    "total_present": present_total,
                    "absent": absent,
                    "leave": leave,
                    "holiday": holiday,
                    "on_time": on_time,
                    "late": late,
                    "permission": permission,
                    "half_day": half_day,
                }

            today_stats = await aggregate_stats(start_of_today, start_of_today)
            month_stats = await aggregate_stats(start_of_month)
            year_stats = await aggregate_stats(start_of_year)

            return {"today": today_stats, "month": month_stats, "year": year_stats}
        except Exception as e:
            traceback.print_exc()
            return {}

    @staticmethod
    async def clock_in(attendance: AttendanceCreate, employee_id: str) -> Tuple[Optional[dict], Optional[dict], Optional[str]]:
        try:
            target_emp_id = employee_id
            emp = await employees_collection.find_one({
                "is_deleted": {"$ne": True},
                "$or": [
                    {"employee_no_id": employee_id},
                    {"_id": ObjectId(employee_id) if ObjectId.is_valid(employee_id) else "000000000000000000000000"}
                ]
            })
            if emp:
                target_emp_id = str(emp["_id"])

            existing = await attendance_collection.find_one({
                "employee_id": target_emp_id,
                "date": attendance.date,
                "is_deleted": {"$ne": True}
            })

            attendance_data = attendance.dict()
            attendance_data["employee_id"] = target_emp_id
            attendance_data["is_deleted"] = False
            attendance_data["deleted_at"] = None
            attendance_data["updated_at"] = datetime.utcnow()

            # Shift calculation
            shift = None
            shift_id = emp.get("shift_id") if emp else None
            if shift_id and ObjectId.is_valid(shift_id):
                shift = await shifts_collection.find_one({"_id": ObjectId(shift_id), "is_deleted": {"$ne": True}})

            if not shift and emp and emp.get("department"):
                dept = await departments_collection.find_one({"name": emp.get("department"), "is_deleted": {"$ne": True}})
                if dept and dept.get("default_shift_id") and ObjectId.is_valid(dept["default_shift_id"]):
                    shift = await shifts_collection.find_one({"_id": ObjectId(dept["default_shift_id"]), "is_deleted": {"$ne": True}})

            work_start_time = "09:00"
            work_end_time = "18:00"
            late_grace_period = 15

            if shift:
                work_start_time = shift.get("start_time", "09:00")
                work_end_time = shift.get("end_time", "18:00")
                late_grace_period = shift.get("late_threshold_minutes", 15)
            else:
                w_conf = await system_configurations_collection.find_one({"key": "work_start_time"})
                l_conf = await system_configurations_collection.find_one({"key": "late_grace_period_minutes"})
                if w_conf:
                    work_start_time = w_conf.get("value", "09:00")
                if l_conf:
                    late_grace_period = l_conf.get("value", 15)

            tz_conf = await system_configurations_collection.find_one({"key": "company_timezone"})
            timezone_name = tz_conf.get("value", "UTC") if tz_conf else "UTC"
            try:
                tz = ZoneInfo(timezone_name)
            except Exception:
                tz = ZoneInfo("UTC")

            clock_in_dt = datetime.fromisoformat(attendance.clock_in.replace("Z", "+00:00"))
            clock_in_local = clock_in_dt.astimezone(tz)
            clock_in_time = clock_in_local.time()

            def _parse_time(t_str, fallback="09:00"):
                for fmt in ("%H:%M", "%H:%M:%S"):
                    try:
                        return datetime.strptime(t_str, fmt).time()
                    except ValueError:
                        pass
                return datetime.strptime(fallback, "%H:%M").time()

            work_start = _parse_time(work_start_time, "09:00")
            work_end = _parse_time(work_end_time, "18:00")

            start_minutes = work_start.hour * 60 + work_start.minute
            end_minutes = work_end.hour * 60 + work_end.minute
            mid_minutes = start_minutes + (end_minutes - start_minutes) // 2
            mid_shift_hour, mid_shift_min = divmod(mid_minutes, 60)
            mid_shift_time = _time(mid_shift_hour, mid_shift_min)

            approved_leave = await leave_requests_collection.find_one({
                "employee_id": target_emp_id,
                "status": "Approved",
                "start_date": {"$lte": attendance.date},
                "end_date": {"$gte": attendance.date},
                "is_deleted": {"$ne": True}
            })

            leave_duration_type = approved_leave.get("leave_duration_type") if approved_leave else None
            half_day_session = approved_leave.get("half_day_session") if approved_leave else None

            leave_type_code = None
            if approved_leave and approved_leave.get("leave_type_id") and ObjectId.is_valid(approved_leave["leave_type_id"]):
                lt = await leave_types_collection.find_one({"_id": ObjectId(approved_leave["leave_type_id"])})
                if lt:
                    leave_type_code = lt.get("code")

            effective_start = work_start
            if leave_duration_type == "Half Day" and half_day_session == "First Half":
                effective_start = mid_shift_time

            is_late = False
            clock_in_minutes = clock_in_time.hour * 60 + clock_in_time.minute
            eff_start_minutes = effective_start.hour * 60 + effective_start.minute

            if clock_in_minutes > eff_start_minutes:
                minutes_late = clock_in_minutes - eff_start_minutes
                if minutes_late > late_grace_period:
                    is_late = True

            is_permission = False
            is_half_day = False

            if leave_duration_type == "Permission":
                is_permission = True
                status = "Present"
                attendance_status = "Permission"
            elif leave_duration_type == "Half Day":
                is_half_day = True
                status = "Present"
                attendance_status = "Half Day"
            elif is_late:
                status = "Late"
                attendance_status = "Late"
            else:
                status = "Present"
                attendance_status = "Ontime"

            attendance_data["status"] = status
            attendance_data["attendance_status"] = attendance_status
            attendance_data["is_late"] = is_late
            attendance_data["is_permission"] = is_permission
            attendance_data["is_half_day"] = is_half_day
            attendance_data["leave_type_code"] = leave_type_code

            if existing:
                if existing.get("status") in ["Present", "Late", "Overtime"]:
                    return None, None, "Already clocked in for this date"

                is_full_day_leave = (
                    existing.get("status") == "Leave"
                    and leave_duration_type not in ["Half Day", "Permission"]
                )

                if is_full_day_leave:
                    await attendance_collection.update_one(
                        {"_id": existing["_id"]},
                        {
                            "$set": {
                                "clock_in": attendance_data["clock_in"],
                                "device_type": attendance_data["device_type"],
                                "location": attendance_data.get("location"),
                                "is_late": is_late,
                                "notes": "Employee clocked in while on Full Day Leave – leave balance remains deducted",
                                "updated_at": datetime.utcnow(),
                            }
                        }
                    )
                else:
                    await attendance_collection.update_one(
                        {"_id": existing["_id"]},
                        {
                            "$set": {
                                "clock_in": attendance_data["clock_in"],
                                "device_type": attendance_data["device_type"],
                                "location": attendance_data.get("location"),
                                "status": status,
                                "attendance_status": attendance_status,
                                "is_late": is_late,
                                "is_permission": is_permission,
                                "is_half_day": is_half_day,
                                "leave_type_code": leave_type_code,
                                "notes": f"Overrode {existing.get('status')} - Employee clocked in ({attendance_status})",
                                "updated_at": datetime.utcnow(),
                            }
                        }
                    )
                attendance_data["id"] = str(existing["_id"])
                res = {**existing, **attendance_data}
                if emp:
                    res["employee_details"] = get_employee_basic_details(emp)
                metrics = await AttendanceService.get_dashboard_metrics(employee_id=target_emp_id)
                return normalize(res), metrics, None

            attendance_data["created_at"] = datetime.utcnow()
            result = await attendance_collection.insert_one(attendance_data)
            attendance_data["id"] = str(result.inserted_id)
            if emp:
                attendance_data["employee_details"] = get_employee_basic_details(emp)

            metrics = await AttendanceService.get_dashboard_metrics(employee_id=target_emp_id)
            return normalize(attendance_data), metrics, None
        except Exception as e:
            traceback.print_exc()
            return None, None, str(e)

    @staticmethod
    async def clock_out(attendance: AttendanceUpdate, employee_id: str, date: str) -> Tuple[Optional[dict], Optional[dict], Optional[str]]:
        try:
            target_emp_id = employee_id
            emp = await employees_collection.find_one({
                "is_deleted": {"$ne": True},
                "$or": [
                    {"employee_no_id": employee_id},
                    {"_id": ObjectId(employee_id) if ObjectId.is_valid(employee_id) else "000000000000000000000000"}
                ]
            })
            if emp:
                target_emp_id = str(emp["_id"])

            existing = await attendance_collection.find_one({
                "employee_id": target_emp_id,
                "date": date,
                "is_deleted": {"$ne": True}
            })
            if not existing:
                existing = await attendance_collection.find_one({
                    "employee_id": employee_id,
                    "date": date,
                    "is_deleted": {"$ne": True}
                })

            if not existing:
                return None, None, "No clock-in record found for this date"

            update_data = {k: v for k, v in attendance.dict().items() if v is not None}
            if attendance.location:
                update_data["location"] = attendance.location

            start_str = existing.get("clock_in")
            end_str = attendance.clock_out

            if start_str and end_str:
                try:
                    start_dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                    end_dt = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
                    duration = (end_dt - start_dt).total_seconds() / 3600
                    total_work_hours = round(duration, 2)
                    update_data["total_work_hours"] = total_work_hours

                    shift = None
                    if emp and emp.get("shift_id") and ObjectId.is_valid(emp["shift_id"]):
                        shift = await shifts_collection.find_one({"_id": ObjectId(emp["shift_id"])})

                    if not shift and emp and emp.get("department"):
                        dept = await departments_collection.find_one({"name": emp.get("department")})
                        if dept and dept.get("default_shift_id") and ObjectId.is_valid(dept["default_shift_id"]):
                            shift = await shifts_collection.find_one({"_id": ObjectId(dept["default_shift_id"])})

                    shift_duration = 9.00
                    if shift:
                        try:
                            s_start = datetime.strptime(shift.get("start_time", "09:00"), "%H:%M")
                            s_end = datetime.strptime(shift.get("end_time", "18:00"), "%H:%M")
                            if s_end < s_start:
                                s_end += timedelta(days=1)
                            shift_duration = (s_end - s_start).total_seconds() / 3600
                        except Exception:
                            shift_duration = 9.00

                    overtime = max(0.0, total_work_hours - shift_duration)
                    update_data["overtime_hours"] = round(overtime, 2)
                except Exception as e:
                    traceback.print_exc()

            update_data["updated_at"] = datetime.utcnow()
            await attendance_collection.update_one({"_id": existing["_id"]}, {"$set": update_data})

            updated_record = await attendance_collection.find_one({"_id": existing["_id"]})
            res = normalize(updated_record)
            if emp:
                res["employee_details"] = get_employee_basic_details(emp)

            metrics = await AttendanceService.get_dashboard_metrics(employee_id=target_emp_id)
            return res, metrics, None
        except Exception as e:
            traceback.print_exc()
            return None, None, str(e)

    @staticmethod
    async def list(
        date: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        employee_id: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
    ) -> Tuple[Optional[dict], Optional[str]]:
        try:
            query = {"is_deleted": {"$ne": True}}
            if date:
                query["date"] = date
            elif start_date and end_date:
                query["date"] = {"$gte": start_date, "$lte": end_date}
            elif start_date:
                query["date"] = {"$gte": start_date}

            if employee_id:
                emp = await employees_collection.find_one({
                    "$or": [
                        {"_id": ObjectId(employee_id) if ObjectId.is_valid(employee_id) else "000000000000000000000000"},
                        {"employee_no_id": employee_id},
                    ]
                })
                if emp:
                    emp_mongo_id = str(emp.get("_id"))
                    emp_bio_id = str(emp.get("employee_no_id"))
                    query["employee_id"] = {"$in": [emp_mongo_id, emp_bio_id]}
                else:
                    query["employee_id"] = employee_id

            if status:
                query["status"] = status

            skip = (page - 1) * limit
            total_count = await attendance_collection.count_documents(query)

            records = (
                await attendance_collection.find(query)
                .sort("date", -1)
                .skip(skip)
                .limit(limit)
                .to_list(length=limit)
            )

            employees = await employees_collection.find({"is_deleted": {"$ne": True}}).to_list(length=None)
            emp_map = {}
            for e in employees:
                e_norm = normalize(e)
                emp_map[str(e["_id"])] = e_norm
                if e_norm.get("employee_no_id"):
                    emp_map[str(e_norm["employee_no_id"])] = e_norm

            result = []
            for r in records:
                r_norm = normalize(r)
                emp_data = emp_map.get(str(r_norm.get("employee_id")))
                r_norm["employee_details"] = get_employee_basic_details(emp_data) if emp_data else None
                result.append(r_norm)

            metrics = await AttendanceService.get_dashboard_metrics(employee_id=employee_id)
            pagination = {
                "total_records": total_count,
                "current_page": page,
                "limit": limit,
                "total_pages": (total_count + limit - 1) // limit if limit > 0 else 0,
            }

            return {"data": result, "metrics": metrics, "pagination": pagination}, None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def get_employee_attendance(
        employee_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Tuple[Optional[dict], Optional[str]]:
        try:
            if not start_date or not end_date:
                now = datetime.utcnow()
                start_date = now.replace(day=1).strftime("%Y-%m-%d")
                if now.month == 12:
                    last_day = now.replace(year=now.year + 1, month=1, day=1) - timedelta(days=1)
                else:
                    last_day = now.replace(month=now.month + 1, day=1) - timedelta(days=1)
                end_date = last_day.strftime("%Y-%m-%d")

            return await AttendanceService.list(
                start_date=start_date, end_date=end_date, employee_id=employee_id, limit=1000
            )
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def edit_attendance_record(
        attendance_id: str,
        data: AttendanceAdminEdit
    ) -> Tuple[Optional[dict], Optional[str]]:
        try:
            if not ObjectId.is_valid(attendance_id):
                return None, "Invalid attendance ID"

            existing = await attendance_collection.find_one({"_id": ObjectId(attendance_id), "is_deleted": {"$ne": True}})
            if not existing:
                return None, "Attendance record not found"

            update_fields = {}
            if data.clock_in is not None:
                update_fields["clock_in"] = data.clock_in
            if data.clock_out is not None:
                update_fields["clock_out"] = data.clock_out
            if data.status is not None:
                update_fields["status"] = data.status
            if data.attendance_status is not None:
                update_fields["attendance_status"] = data.attendance_status
            if data.notes is not None:
                update_fields["notes"] = data.notes

            c_in = data.clock_in if data.clock_in is not None else existing.get("clock_in")
            c_out = data.clock_out if data.clock_out is not None else existing.get("clock_out")

            if c_in and c_out:
                try:
                    dt_in = datetime.fromisoformat(c_in.replace("Z", "+00:00"))
                    dt_out = datetime.fromisoformat(c_out.replace("Z", "+00:00"))
                    if dt_out >= dt_in:
                        duration_h = round((dt_out - dt_in).total_seconds() / 3600, 2)
                        update_fields["total_work_hours"] = duration_h

                        emp_rec = await employees_collection.find_one({
                            "$or": [
                                {"_id": ObjectId(existing["employee_id"]) if ObjectId.is_valid(existing["employee_id"]) else "000000000000000000000000"},
                                {"employee_no_id": existing["employee_id"]},
                            ]
                        })
                        shift_dur = 9.0
                        if emp_rec and emp_rec.get("shift_id") and ObjectId.is_valid(emp_rec["shift_id"]):
                            s_doc = await shifts_collection.find_one({"_id": ObjectId(emp_rec["shift_id"])})
                            if s_doc:
                                try:
                                    s1 = datetime.strptime(s_doc.get("start_time", "09:00"), "%H:%M")
                                    s2 = datetime.strptime(s_doc.get("end_time", "18:00"), "%H:%M")
                                    if s2 < s1:
                                        s2 += timedelta(days=1)
                                    shift_dur = (s2 - s1).total_seconds() / 3600
                                except Exception:
                                    pass
                        update_fields["overtime_hours"] = max(0.0, round(duration_h - shift_dur, 2))
                except Exception:
                    pass

            update_fields["updated_at"] = datetime.utcnow()
            await attendance_collection.update_one({"_id": ObjectId(attendance_id)}, {"$set": update_fields})

            updated = await attendance_collection.find_one({"_id": ObjectId(attendance_id)})
            r_norm = normalize(updated)

            emp_id = r_norm.get("employee_id")
            emp = None
            if emp_id:
                emp = await employees_collection.find_one({
                    "$or": [
                        {"_id": ObjectId(emp_id) if ObjectId.is_valid(emp_id) else "000000000000000000000000"},
                        {"employee_no_id": emp_id},
                    ]
                })
            r_norm["employee_details"] = get_employee_basic_details(normalize(emp)) if emp else None

            return r_norm, None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def bulk_sync_biometric_logs(logs: List[BiometricLogItem]) -> Tuple[Optional[dict], Optional[str]]:
        try:
            processed_count = 0
            errors = []
            sorted_logs = sorted(logs, key=lambda x: x.timestamp)

            for log in sorted_logs:
                try:
                    try:
                        log_time = datetime.fromisoformat(log.timestamp)
                    except Exception:
                        try:
                            log_time = datetime.strptime(log.timestamp, "%Y-%m-%d %H:%M:%S")
                        except Exception:
                            continue

                    date_str = log_time.strftime("%Y-%m-%d")
                    time_str = log_time.isoformat()
                    bio_id_str = str(log.user_id).strip()

                    employee = await employees_collection.find_one({"biometric_id": bio_id_str, "is_deleted": {"$ne": True}})
                    if not employee:
                        pending_log = {
                            "user_id": bio_id_str,
                            "timestamp": log.timestamp,
                            "status": log.status,
                            "punch": log.punch,
                            "created_at": datetime.utcnow()
                        }
                        exists = await pending_biometric_logs_collection.find_one({
                            "user_id": bio_id_str,
                            "timestamp": log.timestamp,
                            "punch": log.punch
                        })
                        if not exists:
                            await pending_biometric_logs_collection.insert_one(pending_log)
                        processed_count += 1
                        continue

                    employee_id = str(employee["_id"])
                    attendance = await attendance_collection.find_one({"employee_id": employee_id, "date": date_str})

                    punch_val = str(log.punch).strip() if log.punch is not None else None
                    is_in_event = (punch_val == "0")
                    is_out_event = (punch_val == "1")

                    if not is_in_event and not is_out_event:
                        is_in_event = not attendance or not attendance.get("clock_in")
                        is_out_event = not is_in_event

                    if is_in_event:
                        if attendance and attendance.get("clock_in"):
                            continue

                        shift = None
                        shift_id = employee.get("shift_id")
                        if shift_id and ObjectId.is_valid(shift_id):
                            shift = await shifts_collection.find_one({"_id": ObjectId(shift_id)})

                        if not shift and employee.get("department"):
                            dept = await departments_collection.find_one({"name": employee.get("department")})
                            if dept and dept.get("default_shift_id") and ObjectId.is_valid(dept["default_shift_id"]):
                                shift = await shifts_collection.find_one({"_id": ObjectId(dept["default_shift_id"])})

                        work_start_time = "09:00"
                        work_end_time = "18:00"
                        late_grace_period = 15

                        if shift:
                            work_start_time = shift.get("start_time", "09:00")
                            work_end_time = shift.get("end_time", "18:00")
                            late_grace_period = shift.get("late_threshold_minutes", 15)

                        def _bio_parse_time(t_str, fallback="09:00"):
                            for fmt in ("%H:%M", "%H:%M:%S"):
                                try:
                                    return datetime.strptime(t_str, fmt).time()
                                except ValueError:
                                    pass
                            return datetime.strptime(fallback, "%H:%M").time()

                        work_start = _bio_parse_time(work_start_time, "09:00")
                        work_end = _bio_parse_time(work_end_time, "18:00")

                        s_min = work_start.hour * 60 + work_start.minute
                        e_min = work_end.hour * 60 + work_end.minute
                        mid_min = s_min + (e_min - s_min) // 2
                        mid_h, mid_m = divmod(mid_min, 60)
                        mid_shift_time = _time(mid_h, mid_m)

                        clock_in_time = log_time.time()
                        approved_leave = await leave_requests_collection.find_one({
                            "employee_id": employee_id,
                            "status": "Approved",
                            "start_date": {"$lte": date_str},
                            "end_date": {"$gte": date_str},
                        })

                        leave_duration_type = approved_leave.get("leave_duration_type") if approved_leave else None
                        half_day_session = approved_leave.get("half_day_session") if approved_leave else None

                        leave_type_code = None
                        if approved_leave and approved_leave.get("leave_type_id") and ObjectId.is_valid(approved_leave["leave_type_id"]):
                            lt = await leave_types_collection.find_one({"_id": ObjectId(approved_leave["leave_type_id"])})
                            if lt:
                                leave_type_code = lt.get("code")

                        effective_start = work_start
                        if leave_duration_type == "Half Day" and half_day_session == "First Half":
                            effective_start = mid_shift_time

                        is_late = False
                        ci_min = clock_in_time.hour * 60 + clock_in_time.minute
                        es_min = effective_start.hour * 60 + effective_start.minute
                        if ci_min > es_min:
                            minutes_late = ci_min - es_min
                            if minutes_late > late_grace_period:
                                is_late = True

                        is_permission = False
                        is_half_day = False

                        if leave_duration_type == "Permission":
                            is_permission = True
                            attendance_status = "Permission"
                        elif leave_duration_type == "Half Day":
                            is_half_day = True
                            attendance_status = "Half Day"
                        elif is_late:
                            attendance_status = "Late"
                        else:
                            attendance_status = "Ontime"

                        if attendance:
                            is_full_day_leave_bio = (
                                attendance.get("status") == "Leave"
                                and leave_duration_type not in ["Half Day", "Permission"]
                            )
                            if is_full_day_leave_bio:
                                await attendance_collection.update_one(
                                    {"_id": attendance["_id"]},
                                    {
                                        "$set": {
                                            "clock_in": time_str,
                                            "device_type": "Biometric",
                                            "location": "At Office",
                                            "is_late": is_late,
                                            "notes": "Clocked in via Biometric while on Full Day Leave – balance preserved",
                                            "updated_at": datetime.utcnow(),
                                        }
                                    }
                                )
                            else:
                                await attendance_collection.update_one(
                                    {"_id": attendance["_id"]},
                                    {
                                        "$set": {
                                            "clock_in": time_str,
                                            "status": "Present",
                                            "attendance_status": attendance_status,
                                            "is_late": is_late,
                                            "is_permission": is_permission,
                                            "is_half_day": is_half_day,
                                            "leave_type_code": leave_type_code,
                                            "device_type": "Biometric",
                                            "location": "At Office",
                                            "updated_at": datetime.utcnow(),
                                        }
                                    }
                                )
                        else:
                            new_record = {
                                "employee_id": employee_id,
                                "date": date_str,
                                "clock_in": time_str,
                                "device_type": "Biometric",
                                "location": "At Office",
                                "status": "Present",
                                "attendance_status": attendance_status,
                                "is_late": is_late,
                                "is_permission": is_permission,
                                "is_half_day": is_half_day,
                                "leave_type_code": leave_type_code,
                                "is_deleted": False,
                                "deleted_at": None,
                                "created_at": datetime.utcnow(),
                            }
                            await attendance_collection.insert_one(new_record)

                        processed_count += 1

                    elif is_out_event:
                        if not attendance or not attendance.get("clock_in"):
                            continue

                        clock_in_time_dt = datetime.fromisoformat(attendance["clock_in"])
                        if log_time > clock_in_time_dt:
                            should_update = True
                            if attendance.get("clock_out"):
                                current_clock_out = datetime.fromisoformat(attendance["clock_out"])
                                if log_time <= current_clock_out:
                                    should_update = False

                            if should_update:
                                work_duration = log_time - clock_in_time_dt
                                total_hours = round(work_duration.total_seconds() / 3600, 2)
                                await attendance_collection.update_one(
                                    {"_id": attendance["_id"]},
                                    {
                                        "$set": {
                                            "clock_out": time_str,
                                            "total_work_hours": total_hours,
                                            "device_type": "Biometric",
                                            "location": "At Office",
                                            "updated_at": datetime.utcnow(),
                                        }
                                    }
                                )
                                processed_count += 1
                except Exception as e:
                    errors.append(f"Error processing log for {log.user_id}: {str(e)}")
                    continue

            return {
                "processed": processed_count,
                "total_received": len(logs),
                "errors": errors,
            }, None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def bulk_import_attendance(records: List[dict]) -> Tuple[Optional[dict], Optional[str]]:
        try:
            operations = []
            for rec in records:
                dt = rec.get("date")
                emp_id = rec.get("employee_id")
                if dt and emp_id:
                    rec["is_deleted"] = False
                    rec["deleted_at"] = None
                    operations.append(
                        UpdateOne(
                            {"employee_id": emp_id, "date": dt},
                            {"$set": {**rec, "updated_at": datetime.utcnow()}},
                            upsert=True,
                        )
                    )

            if operations:
                result = await attendance_collection.bulk_write(operations)
                return {
                    "success": True,
                    "matched": result.matched_count,
                    "upserted": result.upserted_count,
                    "modified": result.modified_count,
                }, None

            return {"success": True, "count": 0}, None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)
