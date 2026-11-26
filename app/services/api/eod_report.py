from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from bson import ObjectId
from app.database import (
    tasks_collection,
    employees_collection,
    projects_collection,
    eod_reports_collection,
)
from app.models import EODReportItem
from app.utils import normalize
import traceback


class EODReportService:

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
                    "is_deleted": {"$ne": True},
                })
                if not existing_task:
                    continue

                now = datetime.utcnow()
                report_status = "Moved" if item.move_to_tomorrow else item.status
                attachments_list = [a.dict() for a in item.new_attachments]

                eod_doc = {
                    "task_id": task_id,
                    "task_name": existing_task.get("task_name") or existing_task.get("name") or "Untitled Task",
                    "project_id": existing_task.get("project_id"),
                    "priority": existing_task.get("priority"),
                    "assigned_to": existing_task.get("assigned_to", []),
                    "date": now.strftime("%Y-%m-%d"),
                    "status": report_status,
                    "progress": item.progress,
                    "summary": item.eod_summary,
                    "attachments": attachments_list,
                    "move_to_tomorrow": item.move_to_tomorrow,
                    "timestamp": now,
                    "is_deleted": False,
                }
                insert_result = await eod_reports_collection.insert_one(eod_doc)
                eod_doc["_id"] = insert_result.inserted_id

                update_fields = {"progress": item.progress, "updated_at": now}

                if item.move_to_tomorrow:
                    today_str = now.strftime("%Y-%m-%d")
                    update_fields["last_rollover_date"] = today_str

                    tomorrow_dt = now + timedelta(days=1)
                    tomorrow_str = tomorrow_dt.strftime("%Y-%m-%d")

                    existing_end_date = existing_task.get("end_date")
                    if not existing_end_date or existing_end_date < tomorrow_str:
                        update_fields["end_date"] = tomorrow_str

                    update_fields["status"] = "In Progress"
                else:
                    update_fields["status"] = item.status

                await tasks_collection.update_one(
                    {"_id": ObjectId(task_id)},
                    {"$set": update_fields},
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
            query: Dict[str, Any] = {"is_deleted": {"$ne": True}}
            if project_id:
                query["project_id"] = project_id
            if assigned_to:
                query["assigned_to"] = assigned_to
            if priority:
                query["priority"] = priority
            if date:
                query["date"] = date

            report_docs = await eod_reports_collection.find(query).sort("timestamp", -1).to_list(length=None)

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
            for doc in report_docs:
                report_norm = normalize(doc)
                proj_name = proj_map.get(report_norm.get("project_id"), "Unknown Project")

                assigned_ids = report_norm.get("assigned_to", [])
                assigned_names = [
                    emp_map.get(eid) or id_to_name_map.get(eid) or eid
                    for eid in assigned_ids
                ]
                employee_display = ", ".join(filter(None, assigned_names))

                if search:
                    search_lower = search.lower()
                    task_name = (report_norm.get("task_name") or "").lower()
                    summary = (report_norm.get("summary") or "").lower()
                    emp_name = employee_display.lower()

                    if (
                        search_lower not in task_name
                        and search_lower not in summary
                        and search_lower not in emp_name
                    ):
                        continue

                report_norm["project_name"] = proj_name
                report_norm["employee_name"] = employee_display
                reports.append(report_norm)

            return reports, None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)
