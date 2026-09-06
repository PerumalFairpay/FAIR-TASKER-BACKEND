from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from bson import ObjectId
from app.database import feedbacks_collection, employees_collection
from app.models import FeedbackCreate, FeedbackUpdate
from app.utils import normalize
import traceback


class FeedbackService:

    @staticmethod
    async def get_feedback_metrics(employee_id: Optional[str] = None) -> Tuple[Optional[dict], Optional[str]]:
        try:
            metrics_query = {"is_deleted": {"$ne": True}}
            if employee_id:
                metrics_query["employee_id"] = employee_id

            all_feedbacks = await feedbacks_collection.find(metrics_query, {"type": 1, "status": 1}).to_list(length=None)

            type_counts = {"Bug": 0, "Feature Request": 0, "General": 0}
            status_counts = {"Open": 0, "In Review": 0, "Resolved": 0, "Closed": 0}

            for f in all_feedbacks:
                t = f.get("type", "General")
                s = f.get("status", "Open")
                if t in type_counts:
                    type_counts[t] += 1
                if s in status_counts:
                    status_counts[s] += 1

            return {
                "total": len(all_feedbacks),
                "by_type": type_counts,
                "by_status": status_counts,
            }, None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def create(feedback_in: FeedbackCreate) -> Tuple[Optional[dict], Optional[dict], Optional[str]]:
        """Returns (feedback_data, metrics, error)"""
        try:
            feedback_data = feedback_in.dict()
            feedback_data["is_deleted"] = False
            feedback_data["deleted_at"] = None
            feedback_data["created_at"] = datetime.utcnow()
            result = await feedbacks_collection.insert_one(feedback_data)
            feedback_id = str(result.inserted_id)

            new_feedback, err = await FeedbackService.get(feedback_id)
            if err:
                return None, None, err

            metrics, _ = await FeedbackService.get_feedback_metrics()
            return new_feedback, metrics, None
        except Exception as e:
            traceback.print_exc()
            return None, None, str(e)

    @staticmethod
    async def list(
        employee_id: Optional[str] = None,
        status: Optional[str] = None
    ) -> Tuple[Optional[List[dict]], Optional[dict], Optional[str]]:
        """Returns (feedbacks_list, metrics, error)"""
        try:
            query = {"is_deleted": {"$ne": True}}
            if employee_id:
                query["employee_id"] = employee_id
            if status:
                query["status"] = status

            feedbacks_raw = await feedbacks_collection.find(query).sort("created_at", -1).to_list(length=None)

            result = []
            for f in feedbacks_raw:
                feedback = normalize(f)
                emp_id = feedback.get("employee_id")
                if emp_id and ObjectId.is_valid(emp_id):
                    emp = await employees_collection.find_one({"_id": ObjectId(emp_id), "is_deleted": {"$ne": True}})
                    if emp:
                        feedback["employee"] = {
                            "id": str(emp["_id"]),
                            "name": emp.get("name", ""),
                            "profile_picture": emp.get("profile_picture"),
                            "designation": emp.get("designation"),
                            "department": emp.get("department"),
                            "employee_no_id": emp.get("employee_no_id"),
                            "email": emp.get("email"),
                        }
                result.append(feedback)

            metrics, _ = await FeedbackService.get_feedback_metrics(employee_id=employee_id)
            return result, metrics, None
        except Exception as e:
            traceback.print_exc()
            return None, None, str(e)

    @staticmethod
    async def get(feedback_id: str) -> Tuple[Optional[dict], Optional[str]]:
        try:
            if not ObjectId.is_valid(feedback_id):
                return None, "Invalid feedback ID"

            feedback_raw = await feedbacks_collection.find_one({
                "_id": ObjectId(feedback_id),
                "is_deleted": {"$ne": True}
            })
            if not feedback_raw:
                return None, "Feedback not found"

            feedback = normalize(feedback_raw)
            emp_id = feedback.get("employee_id")
            if emp_id and ObjectId.is_valid(emp_id):
                emp = await employees_collection.find_one({"_id": ObjectId(emp_id), "is_deleted": {"$ne": True}})
                if emp:
                    feedback["employee"] = {
                        "id": str(emp["_id"]),
                        "name": emp.get("name", ""),
                        "profile_picture": emp.get("profile_picture"),
                        "designation": emp.get("designation"),
                        "department": emp.get("department"),
                        "employee_no_id": emp.get("employee_no_id"),
                        "email": emp.get("email"),
                    }
            return feedback, None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def update(
        feedback_id: str,
        feedback_in: FeedbackUpdate
    ) -> Tuple[Optional[dict], Optional[dict], Optional[str]]:
        """Returns (feedback_data, metrics, error)"""
        try:
            if not ObjectId.is_valid(feedback_id):
                return None, None, "Invalid feedback ID"

            existing = await feedbacks_collection.find_one({
                "_id": ObjectId(feedback_id),
                "is_deleted": {"$ne": True}
            })
            if not existing:
                return None, None, "Feedback not found"

            update_data = {k: v for k, v in feedback_in.dict().items() if v is not None}
            if update_data:
                update_data["updated_at"] = datetime.utcnow()
                await feedbacks_collection.update_one(
                    {"_id": ObjectId(feedback_id)},
                    {"$set": update_data}
                )

            updated_feedback, err = await FeedbackService.get(feedback_id)
            if err:
                return None, None, err

            metrics, _ = await FeedbackService.get_feedback_metrics()
            return updated_feedback, metrics, None
        except Exception as e:
            traceback.print_exc()
            return None, None, str(e)

    @staticmethod
    async def delete(feedback_id: str) -> Tuple[bool, Optional[str]]:
        try:
            if not ObjectId.is_valid(feedback_id):
                return False, "Invalid feedback ID"

            result = await feedbacks_collection.update_one(
                {"_id": ObjectId(feedback_id), "is_deleted": {"$ne": True}},
                {"$set": {"is_deleted": True, "deleted_at": datetime.utcnow()}}
            )
            if result.matched_count == 0:
                return False, "Feedback not found"

            return True, None
        except Exception as e:
            traceback.print_exc()
            return False, str(e)
