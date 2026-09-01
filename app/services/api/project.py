from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from bson import ObjectId
from app.database import projects_collection, clients_collection, employees_collection
from app.models import ProjectCreate, ProjectUpdate
from app.utils import normalize
import traceback


class ProjectService:

    @staticmethod
    def _sanitize_employee(employee_doc: dict) -> dict:
        emp_norm = normalize(employee_doc)
        emp_norm.pop("hashed_password", None)
        emp_norm.pop("password", None)
        return emp_norm

    @staticmethod
    async def create(project_data: ProjectCreate, logo_path: Optional[str] = None) -> Tuple[Optional[dict], Optional[str]]:
        try:
            data = project_data.dict()
            if logo_path:
                data["logo"] = logo_path
            data["is_deleted"] = False
            data["deleted_at"] = None
            data["created_at"] = datetime.utcnow()
            result = await projects_collection.insert_one(data)
            data["id"] = str(result.inserted_id)
            return normalize(data), None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def get_summary() -> Tuple[Optional[List[dict]], Optional[str]]:
        try:
            projection = {
                "name": 1,
                "status": 1,
                "logo": 1
            }
            projects = await projects_collection.find(
                {"is_deleted": {"$ne": True}},
                projection
            ).to_list(length=None)
            return [normalize(p) for p in projects], None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def list() -> Tuple[Optional[List[dict]], Optional[str]]:
        try:
            projects = await projects_collection.find(
                {"is_deleted": {"$ne": True}}
            ).to_list(length=None)

            # Fetch clients and employees for hydration
            clients = await clients_collection.find().to_list(length=None)
            employees = await employees_collection.find().to_list(length=None)

            client_map = {str(c["_id"]): normalize(c) for c in clients}
            employee_map = {str(e["_id"]): ProjectService._sanitize_employee(e) for e in employees}

            result = []
            for p in projects:
                p_norm = normalize(p)
                p_norm["client"] = client_map.get(str(p_norm.get("client_id")))

                # Populate project manager, team leader, and member details
                p_norm["project_managers"] = [
                    employee_map[eid]
                    for eid in p_norm.get("project_manager_ids", [])
                    if eid in employee_map
                ]
                p_norm["team_leaders"] = [
                    employee_map[eid]
                    for eid in p_norm.get("team_leader_ids", [])
                    if eid in employee_map
                ]
                p_norm["team_members"] = [
                    employee_map[eid]
                    for eid in p_norm.get("team_member_ids", [])
                    if eid in employee_map
                ]

                result.append(p_norm)

            return result, None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def get(project_id: str) -> Tuple[Optional[dict], Optional[str]]:
        try:
            if not ObjectId.is_valid(project_id):
                return None, "Invalid project ID"

            project = await projects_collection.find_one({
                "_id": ObjectId(project_id),
                "is_deleted": {"$ne": True}
            })
            if not project:
                return None, "Project not found"

            p_norm = normalize(project)

            # Client details
            client_id = p_norm.get("client_id")
            if client_id and ObjectId.is_valid(str(client_id)):
                client = await clients_collection.find_one({"_id": ObjectId(client_id)})
                p_norm["client"] = normalize(client) if client else None
            else:
                p_norm["client"] = None

            # Collect employee IDs
            all_emp_ids = set()
            all_emp_ids.update(p_norm.get("project_manager_ids", []))
            all_emp_ids.update(p_norm.get("team_leader_ids", []))
            all_emp_ids.update(p_norm.get("team_member_ids", []))

            obj_ids = [ObjectId(eid) for eid in all_emp_ids if ObjectId.is_valid(eid)]
            employees = await employees_collection.find({"_id": {"$in": obj_ids}}).to_list(length=None)
            employee_map = {str(e["_id"]): ProjectService._sanitize_employee(e) for e in employees}

            p_norm["project_managers"] = [
                employee_map[eid]
                for eid in p_norm.get("project_manager_ids", [])
                if eid in employee_map
            ]
            p_norm["team_leaders"] = [
                employee_map[eid]
                for eid in p_norm.get("team_leader_ids", [])
                if eid in employee_map
            ]
            p_norm["team_members"] = [
                employee_map[eid]
                for eid in p_norm.get("team_member_ids", [])
                if eid in employee_map
            ]

            return p_norm, None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def update(project_id: str, project_data: ProjectUpdate, logo_path: Optional[str] = None) -> Tuple[Optional[dict], Optional[str]]:
        try:
            if not ObjectId.is_valid(project_id):
                return None, "Invalid project ID"

            update_data = {k: v for k, v in project_data.dict().items() if v is not None}
            if logo_path:
                update_data["logo"] = logo_path

            if update_data:
                update_data["updated_at"] = datetime.utcnow()
                result = await projects_collection.update_one(
                    {"_id": ObjectId(project_id), "is_deleted": {"$ne": True}},
                    {"$set": update_data}
                )
                if result.matched_count == 0:
                    return None, "Project not found"

            return await ProjectService.get(project_id)
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def delete(project_id: str) -> Tuple[bool, Optional[str]]:
        try:
            if not ObjectId.is_valid(project_id):
                return False, "Invalid project ID"

            result = await projects_collection.update_one(
                {"_id": ObjectId(project_id), "is_deleted": {"$ne": True}},
                {"$set": {"is_deleted": True, "deleted_at": datetime.utcnow()}}
            )
            if result.matched_count == 0:
                return False, "Project not found"
            return True, None
        except Exception as e:
            traceback.print_exc()
            return False, str(e)
