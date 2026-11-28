from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from bson import ObjectId
from app.database import tasks_collection, eod_reports_collection, projects_collection, users_collection, employees_collection
from app.models import TaskCreate, TaskUpdate
from app.utils import normalize, get_employee_basic_details
import traceback


class TaskService:

    @staticmethod
    def _validate_task_dates(
        start_date: Optional[str],
        end_date: Optional[str],
        start_time: Optional[str],
        end_time: Optional[str],
    ) -> Optional[str]:
        if start_date and end_date:
            try:
                start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
                end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
            except ValueError:
                return "Invalid date format. Expected YYYY-MM-DD"

            if end_dt < start_dt:
                return "End date cannot be before start date"

            if end_dt == start_dt and start_time and end_time:
                if end_time <= start_time:
                    return "End time must be after start time"

        return None

    @staticmethod
    def _build_project_summary(project_doc: dict) -> dict:
        return {
            "id": str(project_doc["_id"]),
            "name": project_doc.get("name"),
            "logo": project_doc.get("logo"),
            "status": project_doc.get("status"),
            "priority": project_doc.get("priority"),
        }

    @staticmethod
    def _build_user_summary(user_doc: dict) -> dict:
        return {
            "id": str(user_doc["_id"]),
            "name": user_doc.get("username") or user_doc.get("name") or user_doc.get("email"),
            "email": user_doc.get("email"),
        }

    @staticmethod
    async def _get_assignee_map(assignee_ids: List[str]) -> Dict[str, dict]:
        oids = [ObjectId(aid) for aid in set(assignee_ids) if aid and ObjectId.is_valid(aid)]
        if not oids:
            return {}

        assignee_map: Dict[str, dict] = {}
        employees = await employees_collection.find({"_id": {"$in": oids}}).to_list(length=None)
        for emp in employees:
            assignee_map[str(emp["_id"])] = get_employee_basic_details(emp)

        missing_oids = [oid for oid in oids if str(oid) not in assignee_map]
        if missing_oids:
            users = await users_collection.find(
                {"_id": {"$in": missing_oids}},
                {"username": 1, "name": 1, "email": 1},
            ).to_list(length=None)
            for u in users:
                assignee_map[str(u["_id"])] = TaskService._build_user_summary(u)

        return assignee_map

    @staticmethod
    async def create(task_in: TaskCreate) -> Tuple[Optional[dict], Optional[str]]:
        try:
            validation_error = TaskService._validate_task_dates(
                task_in.start_date,
                task_in.end_date,
                task_in.start_time,
                task_in.end_time,
            )
            if validation_error:
                return None, validation_error

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

            tasks = await tasks_collection.find(query, {"eod_history": 0}).to_list(length=None)

            project_oids = [
                ObjectId(pid)
                for pid in {t.get("project_id") for t in tasks if t.get("project_id")}
                if ObjectId.is_valid(pid)
            ]
            project_map: Dict[str, dict] = {}
            if project_oids:
                projects = await projects_collection.find(
                    {"_id": {"$in": project_oids}},
                    {"name": 1, "logo": 1, "status": 1, "priority": 1},
                ).to_list(length=None)
                for p in projects:
                    project_map[str(p["_id"])] = TaskService._build_project_summary(p)

            assigned_by_oids = [
                ObjectId(uid)
                for uid in {t.get("assigned_by") for t in tasks if t.get("assigned_by")}
                if ObjectId.is_valid(uid)
            ]
            user_map: Dict[str, dict] = {}
            if assigned_by_oids:
                users = await users_collection.find(
                    {"_id": {"$in": assigned_by_oids}},
                    {"username": 1, "name": 1, "email": 1},
                ).to_list(length=None)
                for u in users:
                    user_map[str(u["_id"])] = TaskService._build_user_summary(u)

            all_assignee_ids = [aid for t in tasks for aid in (t.get("assigned_to") or [])]
            assignee_map = await TaskService._get_assignee_map(all_assignee_ids)

            results = []
            for t in tasks:
                norm_task = normalize(t)
                proj = project_map.get(norm_task.get("project_id", ""))
                if proj:
                    norm_task["project"] = proj

                assigner = user_map.get(norm_task.get("assigned_by", ""))
                if assigner:
                    norm_task["assigned_by_details"] = assigner

                norm_task["assigned_to_details"] = [
                    assignee_map[aid]
                    for aid in (norm_task.get("assigned_to") or [])
                    if aid in assignee_map
                ]

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
            pid = norm_task.get("project_id")
            if pid and ObjectId.is_valid(pid):
                project_doc = await projects_collection.find_one(
                    {"_id": ObjectId(pid)},
                    {"name": 1, "logo": 1, "status": 1, "priority": 1},
                )
                if project_doc:
                    proj = TaskService._build_project_summary(project_doc)
                    norm_task["project"] = proj

            assigned_by_id = norm_task.get("assigned_by")
            if assigned_by_id and ObjectId.is_valid(assigned_by_id):
                user_doc = await users_collection.find_one(
                    {"_id": ObjectId(assigned_by_id)},
                    {"username": 1, "name": 1, "email": 1},
                )
                if user_doc:
                    assigner = TaskService._build_user_summary(user_doc)
                    norm_task["assigned_by_details"] = assigner

            assignee_ids = norm_task.get("assigned_to") or []
            assignee_map = await TaskService._get_assignee_map(assignee_ids)
            norm_task["assigned_to_details"] = [
                assignee_map[aid] for aid in assignee_ids if aid in assignee_map
            ]

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
                validation_error = TaskService._validate_task_dates(
                    update_data.get("start_date", existing.get("start_date")),
                    update_data.get("end_date", existing.get("end_date")),
                    update_data.get("start_time", existing.get("start_time")),
                    update_data.get("end_time", existing.get("end_time")),
                )
                if validation_error:
                    return None, validation_error

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
