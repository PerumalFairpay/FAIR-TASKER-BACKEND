from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from bson import ObjectId
from app.database import (
    leave_requests_collection,
    leave_types_collection,
    employees_collection,
    holidays_collection,
    attendance_collection
)
from app.models import LeaveRequestCreate, LeaveRequestUpdate
from app.utils import normalize, get_employee_basic_details
import traceback


class LeaveRequestService:

    @staticmethod
    async def get_employee_leave_balances(employee_id: str) -> List[dict]:
        try:
            if not ObjectId.is_valid(employee_id):
                return []

            employee = await employees_collection.find_one({
                "_id": ObjectId(employee_id),
                "is_deleted": {"$ne": True}
            })
            if not employee:
                return []

            leave_types = await leave_types_collection.find({
                "status": "Active",
                "is_deleted": {"$ne": True}
            }).to_list(length=None)
            current_year = str(datetime.utcnow().year)

            # Use both Approved and Pending to calculate used balance so employees don't overbook
            requests = await leave_requests_collection.find(
                {
                    "employee_id": employee_id,
                    "status": {"$in": ["Approved", "Pending"]},
                    "start_date": {"$regex": f"^{current_year}"},
                    "is_deleted": {"$ne": True}
                }
            ).to_list(length=None)

            # Calculate Tenure
            doj_str = employee.get("date_of_joining")
            months_of_service = 12
            days_of_service = 365
            if doj_str:
                try:
                    doj = datetime.strptime(doj_str[:10], "%Y-%m-%d")
                    delta = datetime.utcnow() - doj
                    days_of_service = delta.days
                    months_of_service = max(0, days_of_service // 30)

                    # If joining in current year, calculate prorated months for this year
                    if doj.year == datetime.utcnow().year:
                        months_in_current_year = 12 - doj.month + 1
                    else:
                        months_in_current_year = 12
                except Exception:
                    months_in_current_year = 12
            else:
                months_in_current_year = 12

            balances = []
            for lt in leave_types:
                lt_id = str(lt["_id"])
                code = lt.get("code")
                base_allowed = lt.get("number_of_days", 0)

                if code == "PER":
                    # Count instances, not days, for Permissions. Track monthly total.
                    used = sum([
                        1 for r in requests
                        if r.get("leave_type_id") == lt_id and r.get("start_date", "").startswith(f"{datetime.utcnow().year}-{datetime.utcnow().month:02d}")
                    ])
                    total_allowed = lt.get("monthly_allowed", 2)
                    monthly_cap_remaining = total_allowed - used
                else:
                    used = sum([
                        float(r.get("total_days", 0))
                        for r in requests
                        if r.get("leave_type_id") == lt_id
                    ])
                    total_allowed = base_allowed

                    # Handle monthly cap if specified
                    monthly_allowed = lt.get("monthly_allowed", 0)
                    if monthly_allowed > 0:
                        monthly_used = sum([
                            float(r.get("total_days", 0))
                            for r in requests
                            if r.get("leave_type_id") == lt_id and r.get("start_date", "").startswith(f"{datetime.utcnow().year}-{datetime.utcnow().month:02d}")
                        ])
                        monthly_cap_remaining = monthly_allowed - monthly_used
                    else:
                        monthly_cap_remaining = 999  # No monthly cap

                probation_months = lt.get("probation_period_months", 0)
                min_service_days = lt.get("min_service_days", 0)

                if probation_months > 0 and months_of_service < probation_months:
                    total_allowed = 0
                elif min_service_days > 0 and days_of_service < min_service_days:
                    total_allowed = 0
                elif code == "EL" and total_allowed > 0:
                    # 0.5 days per month of service max 6
                    total_allowed = min(6, months_in_current_year * 0.5)
                elif code == "CL_SL" and total_allowed > 0:
                    # Prorated based on service months in current year (1 day/month)
                    total_allowed = min(12, months_in_current_year * 1)

                available = max(0, total_allowed - used)
                if code != "PER":
                    available = max(0, min(available, monthly_cap_remaining))

                balances.append(
                    {
                        "leave_type": lt.get("name"),
                        "code": code,
                        "total_allowed": total_allowed,
                        "used": used,
                        "available": available,
                        "allowed_hours": lt.get("allowed_hours", 0),
                        "monthly_allowed": lt.get("monthly_allowed", 0),
                    }
                )
            return balances
        except Exception as e:
            traceback.print_exc()
            return []

    @staticmethod
    async def cleanup_leave_attendance_records(leave_req: dict):
        try:
            start_date = leave_req.get("start_date")
            end_date = leave_req.get("end_date")
            emp_mongo_id = leave_req.get("employee_id")

            if not emp_mongo_id or not ObjectId.is_valid(emp_mongo_id):
                return

            employee = await employees_collection.find_one({"_id": ObjectId(emp_mongo_id)})
            if not employee:
                return

            emp_no_id = str(employee.get("_id"))

            # 1. Remove "Leave" records for this employee in the date range if clock_in is None
            await attendance_collection.delete_many(
                {
                    "employee_id": emp_no_id,
                    "date": {"$gte": start_date, "$lte": end_date},
                    "status": "Leave",
                    "clock_in": None,
                }
            )

            # 2. Revert "Permission" and "Half Day" detailed status back to "Present"
            await attendance_collection.update_many(
                {
                    "employee_id": emp_no_id,
                    "date": {"$gte": start_date, "$lte": end_date},
                    "status": "Present",
                    "attendance_status": {"$in": ["Permission", "Half Day"]}
                },
                {
                    "$set": {
                        "attendance_status": "Present",
                        "is_half_day": False,
                        "notes": "",
                        "updated_at": datetime.utcnow()
                    }
                }
            )

            # 3. Revert "Leave" records back to "Present" if they have a clock-in
            await attendance_collection.update_many(
                {
                    "employee_id": emp_no_id,
                    "date": {"$gte": start_date, "$lte": end_date},
                    "status": "Leave",
                    "clock_in": {"$ne": None},
                },
                {
                    "$set": {
                        "status": "Present",
                        "attendance_status": "Present",
                        "notes": "Reverted Leave to Present after leave rejection",
                        "updated_at": datetime.utcnow()
                    }
                }
            )
        except Exception as e:
            traceback.print_exc()

    @staticmethod
    async def handle_approved_leave_impact(leave_req: dict):
        try:
            start_date = leave_req.get("start_date")
            end_date = leave_req.get("end_date")
            emp_mongo_id = leave_req.get("employee_id")
            reason = leave_req.get("reason", "On Leave")

            today = datetime.utcnow().strftime("%Y-%m-%d")

            if start_date <= today <= end_date:
                duration_type = leave_req.get("leave_duration_type")

                leave_type_code = None
                lt_id = leave_req.get("leave_type_id")
                if lt_id and ObjectId.is_valid(lt_id):
                    lt = await leave_types_collection.find_one({"_id": ObjectId(lt_id)})
                    if lt:
                        leave_type_code = lt.get("code")

                attendance_status = leave_type_code or "Leave"
                is_half_day = False
                if duration_type == "Half Day":
                    attendance_status = "Half Day"
                    is_half_day = True
                elif duration_type == "Permission":
                    attendance_status = "Permission"

                if not emp_mongo_id or not ObjectId.is_valid(emp_mongo_id):
                    return

                employee = await employees_collection.find_one({"_id": ObjectId(emp_mongo_id)})
                if not employee:
                    return

                emp_standard_id = str(employee.get("_id"))
                existing = await attendance_collection.find_one({"employee_id": emp_standard_id, "date": today})

                if not existing:
                    if duration_type == "Permission":
                        return

                    await attendance_collection.insert_one(
                        {
                            "employee_id": emp_standard_id,
                            "date": today,
                            "status": "Leave",
                            "attendance_status": attendance_status,
                            "is_half_day": is_half_day,
                            "leave_type_code": leave_type_code,
                            "notes": reason,
                            "clock_in": None,
                            "clock_out": None,
                            "total_work_hours": 0.0,
                            "overtime_hours": 0.0,
                            "device_type": "Auto Sync",
                            "created_at": datetime.utcnow(),
                        }
                    )
                else:
                    current_status = existing.get("status")
                    update_fields = {
                        "device_type": "Auto Sync",
                        "updated_at": datetime.utcnow()
                    }

                    if current_status == "Absent":
                        if duration_type != "Permission":
                            update_fields["status"] = "Leave"

                    if duration_type == "Permission":
                        update_fields["attendance_status"] = "Permission"
                        update_fields["notes"] = f"Approved Permission: {reason}"
                    elif duration_type == "Half Day":
                        update_fields["is_half_day"] = True
                        update_fields["attendance_status"] = "Half Day"
                        update_fields["notes"] = f"Approved Half Day: {reason}"
                    else:
                        update_fields["status"] = "Leave"
                        update_fields["attendance_status"] = attendance_status
                        update_fields["is_half_day"] = False
                        update_fields["leave_type_code"] = leave_type_code
                        update_fields["notes"] = f"Approved Leave: {reason}"

                    await attendance_collection.update_one(
                        {"_id": existing["_id"]},
                        {"$set": update_fields}
                    )
        except Exception as e:
            traceback.print_exc()

    @staticmethod
    async def create(
        leave_request: LeaveRequestCreate,
        attachment_path: Optional[str] = None
    ) -> Tuple[Optional[dict], Optional[str]]:
        try:
            leave_request_data = leave_request.dict()

            # Check for overlapping leave requests
            existing_leave = await leave_requests_collection.find_one(
                {
                    "employee_id": leave_request.employee_id,
                    "status": {"$in": ["Approved", "Pending"]},
                    "is_deleted": {"$ne": True},
                    "$or": [
                        {
                            "start_date": {"$lte": leave_request.end_date},
                            "end_date": {"$gte": leave_request.start_date},
                        }
                    ],
                }
            )

            if existing_leave:
                return None, f"A leave request already exists for the selected dates (Status: {existing_leave.get('status')})"

            # Rule: Casual Leave cannot be combined with other types
            if not ObjectId.is_valid(leave_request.leave_type_id):
                return None, "Invalid leave type ID"

            requested_type = await leave_types_collection.find_one({
                "_id": ObjectId(leave_request.leave_type_id),
                "is_deleted": {"$ne": True}
            })
            if not requested_type:
                return None, "Invalid leave type selected"

            requested_code = requested_type.get("code")

            try:
                start_dt = datetime.strptime(leave_request.start_date, "%Y-%m-%d")
                end_dt = datetime.strptime(leave_request.end_date, "%Y-%m-%d")
            except ValueError:
                return None, "Invalid date format. Use YYYY-MM-DD."

            prev_day = (start_dt - timedelta(days=1)).strftime("%Y-%m-%d")
            next_day = (end_dt + timedelta(days=1)).strftime("%Y-%m-%d")

            adjacent_leaves = await leave_requests_collection.find({
                "employee_id": leave_request.employee_id,
                "status": {"$in": ["Approved", "Pending"]},
                "is_deleted": {"$ne": True},
                "$or": [
                    {"end_date": prev_day},
                    {"start_date": next_day}
                ]
            }).to_list(length=None)

            for adj in adjacent_leaves:
                adj_type = await leave_types_collection.find_one({"_id": ObjectId(adj.get("leave_type_id"))})
                adj_code = adj_type.get("code") if adj_type else None

                if adj_code and adj_code != "PER" and requested_code != "PER":
                    if (requested_code in ["CL", "SL", "CL_SL"] or adj_code in ["CL", "SL", "CL_SL"]):
                        if requested_code != adj_code:
                            return None, (
                                f"{requested_type.get('name')} cannot be combined with {adj_type.get('name')}. "
                                f"Please maintain a working day between these leave types."
                            )

            # Rule: Only one active permission allowed
            if requested_code == "PER":
                uncompensated_permission = await leave_requests_collection.find_one({
                    "employee_id": leave_request.employee_id,
                    "leave_type_id": str(requested_type["_id"]),
                    "status": {"$in": ["Approved", "Pending"]},
                    "is_compensated": False,
                    "is_deleted": {"$ne": True}
                })

                if uncompensated_permission:
                    return None, (
                        "You already have an active permission that has not been compensated yet. "
                        "Please compensate your previous permission before applying for a new one."
                    )

            # Rule: Notice Period validation
            notice_period = requested_type.get("notice_period_days", 0)
            if notice_period > 0:
                today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
                if (start_dt - today).days < notice_period:
                    return None, (
                        f"Prior approval of {notice_period} days is required for {requested_type.get('name')}. "
                        f"Earliest possible start date is {(today + timedelta(days=notice_period)).strftime('%Y-%m-%d')}."
                    )

            # Server-Side Day Recalculation
            calculated_days = 0.0
            if leave_request.leave_duration_type == "Single":
                calculated_days = 1.0
            elif leave_request.leave_duration_type == "Half Day":
                calculated_days = 0.5
            elif leave_request.leave_duration_type == "Permission":
                calculated_days = 0.0
            elif leave_request.leave_duration_type == "Multiple":
                employee = await employees_collection.find_one({"_id": ObjectId(leave_request.employee_id)})
                weekly_off = employee.get("weekly_off", [6]) if employee else [6]

                holidays_cursor = await holidays_collection.find({"status": "Active", "is_deleted": {"$ne": True}}).to_list(length=None)
                holiday_dates = [h.get("date") for h in holidays_cursor if h.get("date")]

                current_dt = start_dt
                total = 0.0
                while current_dt <= end_dt:
                    is_holiday = current_dt.strftime("%Y-%m-%d") in holiday_dates
                    is_weekly_off = current_dt.weekday() in weekly_off

                    if not is_holiday and not is_weekly_off:
                        total += 1.0

                    current_dt += timedelta(days=1)

                if leave_request.start_session == "Second Half":
                    total -= 0.5
                if leave_request.end_session == "First Half":
                    total -= 0.5

                calculated_days = max(0.0, total)

            leave_request_data["total_days"] = calculated_days
            requested_days = calculated_days

            if requested_code != "LOP":
                balances = await LeaveRequestService.get_employee_leave_balances(leave_request.employee_id)
                balance_info = next((b for b in balances if b["code"] == requested_code), None)

                if not balance_info:
                    return None, f"Eligibility not met for {requested_type.get('name')}."

                if requested_code == "PER":
                    if balance_info["available"] < 1:
                        return None, (
                            f"Monthly limit for {requested_type.get('name')} reached. "
                            f"Allowed: {balance_info['monthly_allowed']}, Used: {balance_info['used']}."
                        )
                else:
                    if balance_info["available"] < requested_days:
                        return None, (
                            f"Insufficient leave balance. Available: {balance_info['available']} days, "
                            f"Requested: {requested_days} days. Please select Loss of Pay (LOP) if you wish to proceed."
                        )

            if attachment_path:
                leave_request_data["attachment"] = attachment_path

            leave_request_data["is_deleted"] = False
            leave_request_data["deleted_at"] = None
            leave_request_data["created_at"] = datetime.utcnow()

            result = await leave_requests_collection.insert_one(leave_request_data)
            leave_request_id = str(result.inserted_id)

            return await LeaveRequestService.get(leave_request_id)
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def list(
        employee_id: Optional[str] = None,
        status: Optional[str] = None,
        date: Optional[str] = None
    ) -> Tuple[Optional[List[dict]], Optional[str]]:
        try:
            query = {"is_deleted": {"$ne": True}}
            if employee_id:
                query["employee_id"] = employee_id
            if status and status != "All":
                query["status"] = status

            if date:
                query["$and"] = [
                    {"start_date": {"$lte": date}},
                    {"end_date": {"$gte": date}}
                ]

            requests = await leave_requests_collection.find(query).sort("created_at", -1).to_list(length=None)

            employees = await employees_collection.find({"is_deleted": {"$ne": True}}).to_list(length=None)
            leave_types = await leave_types_collection.find({"is_deleted": {"$ne": True}}).to_list(length=None)

            emp_map = {str(e["_id"]): normalize(e) for e in employees}
            lt_map = {str(lt["_id"]): normalize(lt) for lt in leave_types}

            result = []
            for r in requests:
                r_norm = normalize(r)
                emp_norm = emp_map.get(str(r_norm.get("employee_id")))
                r_norm["employee_details"] = get_employee_basic_details(emp_norm) if emp_norm else None
                r_norm["leave_type_details"] = lt_map.get(str(r_norm.get("leave_type_id")))
                result.append(r_norm)

            return result, None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def get(leave_request_id: str) -> Tuple[Optional[dict], Optional[str]]:
        try:
            if not ObjectId.is_valid(leave_request_id):
                return None, "Invalid leave request ID"

            request = await leave_requests_collection.find_one({
                "_id": ObjectId(leave_request_id),
                "is_deleted": {"$ne": True}
            })
            if not request:
                return None, "Leave request not found"

            r_norm = normalize(request)

            emp_id = r_norm.get("employee_id")
            if emp_id and ObjectId.is_valid(emp_id):
                employee = await employees_collection.find_one({"_id": ObjectId(emp_id)})
                r_norm["employee_details"] = get_employee_basic_details(normalize(employee)) if employee else None
            else:
                r_norm["employee_details"] = None

            lt_id = r_norm.get("leave_type_id")
            if lt_id and ObjectId.is_valid(lt_id):
                leave_type = await leave_types_collection.find_one({"_id": ObjectId(lt_id)})
                r_norm["leave_type_details"] = normalize(leave_type) if leave_type else None
            else:
                r_norm["leave_type_details"] = None

            return r_norm, None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def update(
        leave_request_id: str,
        leave_request: LeaveRequestUpdate,
        attachment_path: Optional[str] = None
    ) -> Tuple[Optional[dict], Optional[str]]:
        try:
            if not ObjectId.is_valid(leave_request_id):
                return None, "Invalid leave request ID"

            old_req, _ = await LeaveRequestService.get(leave_request_id)
            if not old_req:
                return None, "Leave request not found"

            update_data = {k: v for k, v in leave_request.dict().items() if v is not None}
            if attachment_path:
                update_data["attachment"] = attachment_path

            # Date checks
            if "start_date" in update_data:
                try:
                    start_dt = datetime.strptime(update_data["start_date"], "%Y-%m-%d").date()
                except ValueError:
                    start_dt = datetime.fromisoformat(update_data["start_date"]).date()
                if start_dt < datetime.now().date():
                    return None, "Cannot set start date to a past date."

            if "start_date" in update_data or "end_date" in update_data:
                new_start = update_data.get("start_date") or old_req.get("start_date")
                new_end = update_data.get("end_date") or old_req.get("end_date")
                emp_id = update_data.get("employee_id") or old_req.get("employee_id")

                existing_leave = await leave_requests_collection.find_one(
                    {
                        "_id": {"$ne": ObjectId(leave_request_id)},
                        "employee_id": emp_id,
                        "status": {"$in": ["Approved", "Pending"]},
                        "is_deleted": {"$ne": True},
                        "$or": [
                            {
                                "start_date": {"$lte": new_end},
                                "end_date": {"$gte": new_start},
                            }
                        ],
                    }
                )
                if existing_leave:
                    return None, f"A leave request already exists for the selected dates (Status: {existing_leave.get('status')})"

            # Recalculate total_days if dates changed
            if "start_date" in update_data and "end_date" in update_data and "leave_duration_type" in update_data:
                dur_type = update_data["leave_duration_type"]
                calculated_days = 0.0

                if dur_type == "Single":
                    calculated_days = 1.0
                elif dur_type == "Half Day":
                    calculated_days = 0.5
                elif dur_type == "Permission":
                    calculated_days = 0.0
                elif dur_type == "Multiple":
                    start_dt = datetime.strptime(update_data["start_date"], "%Y-%m-%d")
                    end_dt = datetime.strptime(update_data["end_date"], "%Y-%m-%d")

                    emp_id = update_data.get("employee_id") or old_req.get("employee_id")
                    employee = await employees_collection.find_one({"_id": ObjectId(emp_id)})
                    weekly_off = employee.get("weekly_off", [6]) if employee else [6]

                    holidays_cursor = await holidays_collection.find({"status": "Active", "is_deleted": {"$ne": True}}).to_list(length=None)
                    holiday_dates = [h.get("date") for h in holidays_cursor if h.get("date")]

                    current_dt = start_dt
                    total = 0.0
                    while current_dt <= end_dt:
                        is_holiday = current_dt.strftime("%Y-%m-%d") in holiday_dates
                        is_weekly_off = current_dt.weekday() in weekly_off

                        if not is_holiday and not is_weekly_off:
                            total += 1.0

                        current_dt += timedelta(days=1)

                    start_sess = update_data.get("start_session") or old_req.get("start_session")
                    end_sess = update_data.get("end_session") or old_req.get("end_session")

                    if start_sess == "Second Half":
                        total -= 0.5
                    if end_sess == "First Half":
                        total -= 0.5

                    calculated_days = max(0.0, total)

                update_data["total_days"] = calculated_days

            if update_data:
                update_data["updated_at"] = datetime.utcnow()
                await leave_requests_collection.update_one(
                    {"_id": ObjectId(leave_request_id)},
                    {"$set": update_data}
                )

            updated_req, _ = await LeaveRequestService.get(leave_request_id)
            if not updated_req:
                return None, "Failed to retrieve updated leave request"

            old_status = old_req.get("status")
            new_status = updated_req.get("status")

            if new_status == "Approved" and old_status != "Approved":
                await LeaveRequestService.handle_approved_leave_impact(updated_req)
            elif old_status == "Approved" and new_status != "Approved":
                await LeaveRequestService.cleanup_leave_attendance_records(old_req)

            return updated_req, None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def delete(leave_request_id: str) -> Tuple[bool, Optional[str]]:
        try:
            if not ObjectId.is_valid(leave_request_id):
                return False, "Invalid leave request ID"

            leave_req, _ = await LeaveRequestService.get(leave_request_id)
            if not leave_req:
                return False, "Leave request not found"

            result = await leave_requests_collection.update_one(
                {"_id": ObjectId(leave_request_id), "is_deleted": {"$ne": True}},
                {"$set": {"is_deleted": True, "deleted_at": datetime.utcnow()}}
            )
            if result.matched_count == 0:
                return False, "Leave request not found"

            if leave_req.get("status") == "Approved":
                await LeaveRequestService.cleanup_leave_attendance_records(leave_req)

            return True, None
        except Exception as e:
            traceback.print_exc()
            return False, str(e)
