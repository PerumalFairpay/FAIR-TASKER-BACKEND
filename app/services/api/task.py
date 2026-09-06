from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from bson import ObjectId
from app.database import tasks_collection, employees_collection, projects_collection
from app.models import TaskCreate, TaskUpdate, EODReportItem
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

            results = []
            for t in tasks:
                norm_task = normalize(t)

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

            return normalize(task), None
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
    async def process_eod_report(items: List[EODReportItem]) -> Tuple[Optional[List[dict]], Optional[str]]:
        try:
            results = []
            for item in items:
                task_id = item.task_id
                if not ObjectId.is_valid(task_id):
                    continue

                existing_task = await tasks_collection.find_one({
                    "_id": ObjectId(task_id),
                    "is_deleted": {"$ne": True}
                })
                if not existing_task:
                    continue

                # Update existing task history and status
                eod_entry = {
                    "date": datetime.utcnow().strftime("%Y-%m-%d"),
                    "status": "Moved" if item.move_to_tomorrow else item.status,
                    "progress": item.progress,
                    "summary": item.eod_summary,
                    "attachments": [a.dict() for a in item.new_attachments],
                    "timestamp": datetime.utcnow(),
                }

                update_fields = {"progress": item.progress, "updated_at": datetime.utcnow()}

                if item.move_to_tomorrow:
                    # Visual Rollover: Mark as rolled over today
                    today_str = datetime.utcnow().strftime("%Y-%m-%d")
                    update_fields["last_rollover_date"] = today_str

                    # Smart Rollover: Preserve future deadlines
                    tomorrow_dt = datetime.utcnow() + timedelta(days=1)
                    tomorrow_str = tomorrow_dt.strftime("%Y-%m-%d")

                    existing_end_date = existing_task.get("end_date")

                    # If no end date or end date is earlier than tomorrow, extend it to tomorrow
                    if not existing_end_date or existing_end_date < tomorrow_str:
                        update_fields["end_date"] = tomorrow_str

                    # Always keep status as "In Progress" for rollover
                    update_fields["status"] = "In Progress"
                else:
                    update_fields["status"] = item.status

                # Add to history and update fields
                await tasks_collection.update_one(
                    {"_id": ObjectId(task_id)},
                    {"$set": update_fields, "$push": {"eod_history": eod_entry}},
                )

                updated_task = await tasks_collection.find_one({"_id": ObjectId(task_id)})
                results.append(normalize(updated_task))

            return results, None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def get_eod_reports(
        project_id: Optional[str] = None,
        assigned_to: Optional[str] = None,
        date: Optional[str] = None,
        priority: Optional[str] = None,
        search: Optional[str] = None,
    ) -> Tuple[Optional[List[dict]], Optional[str]]:
        try:
            query = {
                "eod_history": {"$exists": True, "$not": {"$size": 0}},
                "is_deleted": {"$ne": True}
            }
            if project_id:
                query["project_id"] = project_id
            if assigned_to:
                query["assigned_to"] = assigned_to
            if priority:
                query["priority"] = priority

            tasks = await tasks_collection.find(query).to_list(length=None)

            # Fetch all employees and projects for naming
            employees = await employees_collection.find().to_list(length=None)
            projects = await projects_collection.find().to_list(length=None)

            emp_map = {
                str(e.get("employee_no_id")): e.get("name")
                for e in employees
                if e.get("employee_no_id")
            }
            id_to_name_map = {str(e.get("_id")): e.get("name") for e in employees}
            proj_map = {str(p.get("_id")): p.get("name") for p in projects}

            reports = []
            for task in tasks:
                task_norm = normalize(task)
                proj_name = proj_map.get(task_norm.get("project_id"), "Unknown Project")

                # assigned_to is a list of IDs. We'll take the first one or join them
                assigned_ids = task_norm.get("assigned_to", [])
                assigned_names = [
                    emp_map.get(eid) or id_to_name_map.get(eid) or eid
                    for eid in assigned_ids
                ]
                employee_display = ", ".join(filter(None, assigned_names))

                for entry in task_norm.get("eod_history", []):
                    if date and entry.get("date") != date:
                        continue

                    # Search Filtering
                    if search:
                        search_lower = search.lower()
                        task_name = (task_norm.get("task_name") or task_norm.get("name") or "").lower()
                        summary = (entry.get("summary") or "").lower()
                        emp_name = employee_display.lower()

                        if (
                            search_lower not in task_name
                            and search_lower not in summary
                            and search_lower not in emp_name
                        ):
                            continue

                    report_entry = {
                        "task_id": task_norm["id"],
                        "task_name": task_norm.get("task_name")
                        or task_norm.get("name")
                        or "Untitled Task",
                        "project_id": task_norm.get("project_id"),
                        "project_name": proj_name,
                        "assigned_to": task_norm.get("assigned_to", []),
                        "employee_name": employee_display,
                        **entry,
                    }
                    reports.append(report_entry)

            reports.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            return reports, None
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
