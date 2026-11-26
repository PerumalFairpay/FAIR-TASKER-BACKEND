from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from bson import ObjectId
from app.database import tasks_collection, eod_reports_collection
from app.models import TaskCreate, TaskUpdate
from app.utils import normalize
import traceback


class TaskService:

    @staticmethod
    async def create(task_in: TaskCreate) -> Tuple[Optional[dict], Optional[str]]:
        try:
            task_data = task_in.dict()
            task_data["is_deleted"] = False
            task_data["deleted_at"] = None
            task_data["created_at"] = datetime.utcnow()
            task_data["eod_history"] = []
            result = await tasks_collection.insert_one(task_data)
            task_data["id"] = str(result.inserted_id)
            return normalize(task_data), None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def list(
        project_id: Optional[str] = None,
        assigned_to: Optional[str] = None,
        start_date: Optional[str] = None,
        date: Optional[str] = None,
        status: Optional[str] = None,
        priority: Optional[str] = None,
    ) -> Tuple[Optional[List[dict]], Optional[str]]:
        try:
            query = {"is_deleted": {"$ne": True}}
            if project_id:
                query["project_id"] = project_id
            if assigned_to:
                # Matches if employee ID is in the list
                query["assigned_to"] = assigned_to
            if status:
                query["status"] = status
            if priority:
                query["priority"] = priority

            if date:
                # Determine the cutoff date for overdue calculation.
                today_str = datetime.utcnow().strftime("%Y-%m-%d")
                overdue_cutoff = date if date < today_str else today_str

                # Active tasks on this specific date OR Overdue tasks
                query["$or"] = [
                    # 1. Active on date: start_date <= date AND (end_date >= date OR end_date is None)
                    {
                        "$and": [
                            {"start_date": {"$lte": date}},
                            {
                                "$or": [
                                    {"end_date": {"$gte": date}},
                                    {"end_date": None},
                                    {"end_date": ""},
                                    {"end_date": {"$exists": False}},
                                ]
                            },
                        ]
                    },
                    # 2. Overdue: end_date < overdue_cutoff AND status != Completed
                    {
                        "$and": [
                            {"end_date": {"$lt": overdue_cutoff}},
                            {"status": {"$ne": "Completed"}},
                            {"end_date": {"$ne": None}},
                            {"end_date": {"$ne": ""}},
                        ]
                    },
                ]
            elif start_date:
                # Fallback to exact start date match if no specific 'date' view requested
                query["start_date"] = start_date

            tasks = await tasks_collection.find(query).to_list(length=None)
            task_ids = [str(t["_id"]) for t in tasks]
            eod_by_task: Dict[str, List[dict]] = {}
            if task_ids:
                eod_docs = await eod_reports_collection.find({
                    "task_id": {"$in": task_ids},
                    "is_deleted": {"$ne": True},
                }).sort("timestamp", 1).to_list(length=None)
                for doc in eod_docs:
                    norm_doc = normalize(doc)
                    eod_by_task.setdefault(norm_doc["task_id"], []).append(norm_doc)

            results = []
            for t in tasks:
                norm_task = normalize(t)
                # Prefer dedicated eod_reports collection; fall back to embedded eod_history if any
                if norm_task["id"] in eod_by_task:
                    norm_task["eod_history"] = eod_by_task[norm_task["id"]]

                # Calculate is_overdue flag
                is_overdue = False
                if (
                    date
                    and norm_task.get("end_date")
                    and norm_task.get("status") != "Completed"
                ):
                    today_str = datetime.utcnow().strftime("%Y-%m-%d")
                    cutoff = date if date < today_str else today_str

                    if norm_task["end_date"] < cutoff:
                        is_overdue = True

                norm_task["is_overdue"] = is_overdue
                results.append(norm_task)

            return results, None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def get(task_id: str) -> Tuple[Optional[dict], Optional[str]]:
        try:
            if not ObjectId.is_valid(task_id):
                return None, "Invalid task ID"

            task = await tasks_collection.find_one({
                "_id": ObjectId(task_id),
                "is_deleted": {"$ne": True}
            })
            if not task:
                return None, "Task not found"

            norm_task = normalize(task)
            eod_docs = await eod_reports_collection.find({
                "task_id": task_id,
                "is_deleted": {"$ne": True},
            }).sort("timestamp", 1).to_list(length=None)
            if eod_docs:
                norm_task["eod_history"] = [normalize(doc) for doc in eod_docs]

            return norm_task, None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def update(task_id: str, task_in: TaskUpdate) -> Tuple[Optional[dict], Optional[str]]:
        try:
            if not ObjectId.is_valid(task_id):
                return None, "Invalid task ID"

            existing = await tasks_collection.find_one({
                "_id": ObjectId(task_id),
                "is_deleted": {"$ne": True}
            })
            if not existing:
                return None, "Task not found"

            update_data = {k: v for k, v in task_in.dict().items() if v is not None}
            if update_data:
                update_data["updated_at"] = datetime.utcnow()
                await tasks_collection.update_one(
                    {"_id": ObjectId(task_id)},
                    {"$set": update_data}
                )

            updated_task = await tasks_collection.find_one({"_id": ObjectId(task_id)})
            return normalize(updated_task), None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def delete(task_id: str) -> Tuple[bool, Optional[str]]:
        try:
            if not ObjectId.is_valid(task_id):
                return False, "Invalid task ID"

            result = await tasks_collection.update_one(
                {"_id": ObjectId(task_id), "is_deleted": {"$ne": True}},
                {"$set": {"is_deleted": True, "deleted_at": datetime.utcnow()}}
            )
            if result.matched_count == 0:
                return False, "Task not found"

            return True, None
        except Exception as e:
            traceback.print_exc()
            return False, str(e)
