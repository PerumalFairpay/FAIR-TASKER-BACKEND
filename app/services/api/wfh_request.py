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

            start_dt = WFHRequestService._parse_date(request_data.start_date)
            end_dt = WFHRequestService._parse_date(request_data.end_date)
            if not start_dt or not end_dt:
                return None, "Invalid date format. Use YYYY-MM-DD."

            if end_dt.date() < start_dt.date():
                return None, "End date cannot be earlier than start date."

            if start_dt.date() < datetime.now().date():
                return None, "Cannot request Work From Home for past dates."

            # Calculate total days if not provided
            calc_days = float((end_dt.date() - start_dt.date()).days + 1)
            total_days = request_data.total_days or calc_days

            # Overlap check for pending or approved requests
            overlap = await wfh_requests_collection.find_one({
                "employee_id": request_data.employee_id,
                "status": {"$in": ["Pending", "Approved"]},
                "is_deleted": {"$ne": True},
                "$or": [
                    {"start_date": {"$lte": request_data.end_date}, "end_date": {"$gte": request_data.start_date}}
                ]
            })
            if overlap:
                return None, f"A WFH request already exists between {overlap.get('start_date')} and {overlap.get('end_date')} with status '{overlap.get('status')}'."

            now_iso = datetime.utcnow().isoformat()
            doc = {
                "employee_id": request_data.employee_id,
                "start_date": request_data.start_date,
                "end_date": request_data.end_date,
                "total_days": total_days,
                "request_type": request_data.request_type or "Temporary",
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
