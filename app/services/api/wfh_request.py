from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from bson import ObjectId
from app.database import (
    wfh_requests_collection,
    employees_collection
)
from app.models import WFHRequestCreate, WFHRequestUpdate, WFHRequestStatusUpdate
from app.utils import normalize, get_employee_basic_details
import traceback


class WFHRequestService:

    @staticmethod
    def _parse_date(date_str: str) -> Optional[datetime]:
        try:
            return datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            try:
                return datetime.fromisoformat(date_str)
            except Exception:
                return None

    @staticmethod
    async def create(request_data: WFHRequestCreate) -> Tuple[Optional[dict], Optional[str]]:
        try:
            if not ObjectId.is_valid(request_data.employee_id):
                return None, "Invalid employee ID"

            employee = await employees_collection.find_one({
                "_id": ObjectId(request_data.employee_id),
                "is_deleted": {"$ne": True}
            })
            if not employee:
                return None, "Employee not found"

            emp_mongo_id = str(employee["_id"])


            is_permanent = (request_data.request_type or "").strip().lower() == "permanent"

            start_dt = WFHRequestService._parse_date(request_data.start_date)
            if not start_dt:
                return None, "Invalid start date format. Use YYYY-MM-DD."

            if start_dt.date() < datetime.now().date():
                return None, "Cannot request Work From Home for past dates."

            end_date_val = None
            total_days = None

            if not is_permanent:
                if not request_data.end_date:
                    return None, "End date is required for Temporary WFH requests."
                end_dt = WFHRequestService._parse_date(request_data.end_date)
                if not end_dt:
                    return None, "Invalid end date format. Use YYYY-MM-DD."
                if end_dt.date() < start_dt.date():
                    return None, "End date cannot be earlier than start date."
                calc_days = float((end_dt.date() - start_dt.date()).days + 1)
                total_days = request_data.total_days or calc_days
                end_date_val = request_data.end_date
            else:
                end_date_val = None
                total_days = None

            # Overlap check for pending or approved requests
            overlap_query: Dict[str, Any] = {
                "employee_id": emp_mongo_id,
                "status": {"$in": ["Pending", "Approved"]},
                "is_deleted": {"$ne": True}
            }
            if is_permanent:
                # Permanent requests overlap with any future or active request on/after start_date
                overlap_query["$or"] = [
                    {"request_type": "Permanent"},
                    {"end_date": {"$gte": request_data.start_date}}
                ]
            else:
                overlap_query["$or"] = [
                    {"request_type": "Permanent", "start_date": {"$lte": end_date_val}},
                    {"start_date": {"$lte": end_date_val}, "end_date": {"$gte": request_data.start_date}}
                ]

            overlap = await wfh_requests_collection.find_one(overlap_query)
            if overlap:
                overlap_range = f"starting {overlap.get('start_date')}" if overlap.get('request_type') == "Permanent" else f"between {overlap.get('start_date')} and {overlap.get('end_date')}"
                return None, f"An active or pending WFH request already exists ({overlap_range}) with status '{overlap.get('status')}'."

            now_iso = datetime.utcnow().isoformat()
            doc = {
                "employee_id": emp_mongo_id,
                "start_date": request_data.start_date,
                "end_date": end_date_val,
                "total_days": total_days,
                "request_type": "Permanent" if is_permanent else "Temporary",
                "reason": request_data.reason,
                "status": "Pending",
                "rejection_reason": None,
                "reviewed_by": None,
                "reviewed_at": None,
                "is_deleted": False,
                "created_at": now_iso,
                "updated_at": now_iso
            }

            result = await wfh_requests_collection.insert_one(doc)
            inserted = await wfh_requests_collection.find_one({"_id": result.inserted_id})
            formatted = normalize(inserted)
            formatted["employee_details"] = get_employee_basic_details(employee)
            return formatted, None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def get_all(
        employee_id: Optional[str] = None,
        status: Optional[str] = None
    ) -> Tuple[Dict[str, Any], Optional[str]]:
        try:
            query: Dict[str, Any] = {"is_deleted": {"$ne": True}}

            if employee_id and ObjectId.is_valid(employee_id):
                query["employee_id"] = employee_id

            # Metrics
            total_query = dict(query)
            if "status" in total_query:
                del total_query["status"]

            total_count = await wfh_requests_collection.count_documents(total_query)
            pending_count = await wfh_requests_collection.count_documents({**total_query, "status": "Pending"})
            approved_count = await wfh_requests_collection.count_documents({**total_query, "status": "Approved"})
            rejected_count = await wfh_requests_collection.count_documents({**total_query, "status": "Rejected"})

            if status and status.lower() != "all":
                query["status"] = {"$regex": f"^{status}$", "$options": "i"}

            cursor = wfh_requests_collection.find(query).sort("created_at", -1)
            raw_docs = await cursor.to_list(length=None)

            # Bulk load employee details
            emp_ids = list({doc.get("employee_id") for doc in raw_docs if doc.get("employee_id") and ObjectId.is_valid(doc.get("employee_id"))})
            employees_map = {}
            if emp_ids:
                emp_list = await employees_collection.find({
                    "_id": {"$in": [ObjectId(eid) for eid in emp_ids]}
                }).to_list(length=None)
                for emp in emp_list:
                    employees_map[str(emp["_id"])] = get_employee_basic_details(emp)

            results = []
            for doc in raw_docs:
                norm = normalize(doc)
                norm["employee_details"] = employees_map.get(norm.get("employee_id"))
                results.append(norm)

            metrics = {
                "total": total_count,
                "pending": pending_count,
                "approved": approved_count,
                "rejected": rejected_count
            }

            return {"data": results, "metrics": metrics}, None
        except Exception as e:
            traceback.print_exc()
            return {"data": [], "metrics": {}}, str(e)

    @staticmethod
    async def get_by_id(wfh_id: str) -> Tuple[Optional[dict], Optional[str]]:
        try:
            if not ObjectId.is_valid(wfh_id):
                return None, "Invalid WFH request ID"
            doc = await wfh_requests_collection.find_one({"_id": ObjectId(wfh_id), "is_deleted": {"$ne": True}})
            if not doc:
                return None, "WFH request not found"
            norm = normalize(doc)
            if norm.get("employee_id") and ObjectId.is_valid(norm["employee_id"]):
                emp = await employees_collection.find_one({"_id": ObjectId(norm["employee_id"])})
                norm["employee_details"] = get_employee_basic_details(emp)
            return norm, None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def update_status(
        wfh_id: str,
        status_update: WFHRequestStatusUpdate,
        reviewed_by: Optional[str] = None
    ) -> Tuple[Optional[dict], Optional[str]]:
        try:
            if not ObjectId.is_valid(wfh_id):
                return None, "Invalid WFH request ID"

            existing = await wfh_requests_collection.find_one({
                "_id": ObjectId(wfh_id),
                "is_deleted": {"$ne": True}
            })
            if not existing:
                return None, "WFH request not found"

            valid_statuses = ["Approved", "Rejected"]
            if status_update.status not in valid_statuses:
                return None, f"Invalid status. Must be one of: {', '.join(valid_statuses)}"

            now_iso = datetime.utcnow().isoformat()
            update_fields: Dict[str, Any] = {
                "status": status_update.status,
                "reviewed_by": reviewed_by,
                "reviewed_at": now_iso,
                "updated_at": now_iso
            }

            if status_update.status == "Rejected":
                update_fields["rejection_reason"] = status_update.rejection_reason
            else:
                update_fields["rejection_reason"] = None

            # CRITICAL: If Approved, update Employee's work_mode to "Remote" (Work From Home)
            if status_update.status == "Approved":
                employee_id = existing.get("employee_id")
                if employee_id and ObjectId.is_valid(employee_id):
                    # Store previous work mode if available, then set to "Remote"
                    emp = await employees_collection.find_one({"_id": ObjectId(employee_id)})
                    if emp:
                        current_mode = emp.get("work_mode", "Office")
                        update_fields["previous_work_mode"] = current_mode
                        update_fields["reverted"] = False
                        await employees_collection.update_one(
                            {"_id": ObjectId(employee_id)},
                            {"$set": {"work_mode": "Remote", "updated_at": now_iso}}
                        )

            await wfh_requests_collection.update_one(
                {"_id": ObjectId(wfh_id)},
                {"$set": update_fields}
            )

            updated_doc = await wfh_requests_collection.find_one({"_id": ObjectId(wfh_id)})
            norm = normalize(updated_doc)
            if norm.get("employee_id") and ObjectId.is_valid(norm["employee_id"]):
                emp = await employees_collection.find_one({"_id": ObjectId(norm["employee_id"])})
                norm["employee_details"] = get_employee_basic_details(emp)
            return norm, None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def revert_expired_wfh_requests() -> int:
        """
        Scheduled job: Reverts temporary WFH employees whose end_date has passed
        back to their previous work_mode (default: Office).
        """
        try:
            today_str = datetime.now().date().isoformat()
            now_iso = datetime.utcnow().isoformat()

            # Find all Approved, Temporary requests where end_date < today and not yet reverted
            expired_requests = await wfh_requests_collection.find({
                "status": "Approved",
                "request_type": "Temporary",
                "end_date": {"$lt": today_str},
                "reverted": {"$ne": True},
                "is_deleted": {"$ne": True}
            }).to_list(length=None)

            reverted_count = 0
            for req in expired_requests:
                req_id = req["_id"]
                emp_id = req.get("employee_id")
                prev_mode = req.get("previous_work_mode") or "Office"

                if emp_id and ObjectId.is_valid(emp_id):
                    # Check if employee has an active/upcoming approved WFH request
                    active_wfh = await wfh_requests_collection.find_one({
                        "_id": {"$ne": req_id},
                        "employee_id": emp_id,
                        "status": "Approved",
                        "is_deleted": {"$ne": True},
                        "$or": [
                            {"request_type": "Permanent"},
                            {"start_date": {"$lte": today_str}, "end_date": {"$gte": today_str}}
                        ]
                    })

                    # If no other active WFH request, revert employee's work mode
                    if not active_wfh:
                        await employees_collection.update_one(
                            {"_id": ObjectId(emp_id)},
                            {"$set": {"work_mode": prev_mode, "updated_at": now_iso}}
                        )

                # Mark this request as reverted
                await wfh_requests_collection.update_one(
                    {"_id": req_id},
                    {"$set": {"reverted": True, "reverted_at": now_iso, "updated_at": now_iso}}
                )
                reverted_count += 1

            return reverted_count
        except Exception as e:
            traceback.print_exc()
            return 0

    @staticmethod
    async def delete(wfh_id: str, user_role: str = "", user_id: str = "") -> Tuple[bool, Optional[str]]:
        try:
            if not ObjectId.is_valid(wfh_id):
                return False, "Invalid WFH request ID"

            existing = await wfh_requests_collection.find_one({
                "_id": ObjectId(wfh_id),
                "is_deleted": {"$ne": True}
            })
            if not existing:
                return False, "WFH request not found"

            # Non-admins can only delete their own Pending requests
            if user_role not in ["admin", "super_admin", "hr"]:
                if existing.get("status") != "Pending":
                    return False, "You can only cancel pending WFH requests."

            await wfh_requests_collection.update_one(
                {"_id": ObjectId(wfh_id)},
                {"$set": {"is_deleted": True, "updated_at": datetime.utcnow().isoformat()}}
            )
            return True, None
        except Exception as e:
            traceback.print_exc()
            return False, str(e)
