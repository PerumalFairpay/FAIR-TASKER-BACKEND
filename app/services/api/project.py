import json
from typing import Dict, Any, List, Optional, Tuple, Union
from datetime import datetime
from bson import ObjectId
from fastapi import UploadFile
from app.database import projects_collection, clients_collection, employees_collection
from app.models import ProjectCreate, ProjectUpdate
from app.helper.file_handler import file_handler
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
    def _parse_json_list(val: Any) -> Optional[List[Any]]:
        if val is None:
            return None
        if isinstance(val, list):
            return val
        if isinstance(val, str):
            val = val.strip()
            if not val:
                return None
            try:
                parsed = json.loads(val)
                return parsed if isinstance(parsed, list) else None
            except Exception:
                return None
        return None

    @staticmethod
    async def create(
        name: str,
        client_id: str,
        description: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        status: Optional[str] = "Planned",
        priority: Optional[str] = "Medium",
        project_manager_ids: Optional[Union[str, List[str]]] = "[]",
        team_leader_ids: Optional[Union[str, List[str]]] = "[]",
        team_member_ids: Optional[Union[str, List[str]]] = "[]",
        budget: Optional[float] = 0.0,
        currency: Optional[str] = "USD",
        tags: Optional[Union[str, List[str]]] = "[]",
        technical_stacks: Optional[Union[str, List[str]]] = "[]",
        third_party_vendors: Optional[Union[str, List[dict]]] = "[]",
        logo: Optional[UploadFile] = None
    ) -> Tuple[Optional[dict], Optional[str]]:
        try:
            logo_path = None
            if logo and logo.filename:
                uploaded = await file_handler.upload_file(logo, subfolder="projects")
                logo_path = uploaded["url"]

            pm_ids = ProjectService._parse_json_list(project_manager_ids) or []
            tl_ids = ProjectService._parse_json_list(team_leader_ids) or []
            tm_ids = ProjectService._parse_json_list(team_member_ids) or []
            tags_list = ProjectService._parse_json_list(tags) or []
            tech_stacks = ProjectService._parse_json_list(technical_stacks) or []
            vendors = ProjectService._parse_json_list(third_party_vendors) or []

            project_data = ProjectCreate(
                name=name,
                client_id=client_id,
                description=description,
                start_date=start_date,
                end_date=end_date,
                status=status,
                priority=priority,
                project_manager_ids=pm_ids,
                team_leader_ids=tl_ids,
                team_member_ids=tm_ids,
                budget=budget,
                currency=currency,
                tags=tags_list,
                technical_stacks=tech_stacks,
                third_party_vendors=vendors,
                logo=logo_path
            )

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
    async def update(
        project_id: str,
        name: Optional[str] = None,
        client_id: Optional[str] = None,
        description: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        project_manager_ids: Optional[Union[str, List[str]]] = None,
        team_leader_ids: Optional[Union[str, List[str]]] = None,
        team_member_ids: Optional[Union[str, List[str]]] = None,
        budget: Optional[float] = None,
        currency: Optional[str] = None,
        tags: Optional[Union[str, List[str]]] = None,
        technical_stacks: Optional[Union[str, List[str]]] = None,
        third_party_vendors: Optional[Union[str, List[dict]]] = None,
        logo: Optional[UploadFile] = None
    ) -> Tuple[Optional[dict], Optional[str]]:
        try:
            if not ObjectId.is_valid(project_id):
                return None, "Invalid project ID"

            logo_path = None
            if logo and logo.filename:
                uploaded = await file_handler.upload_file(logo, subfolder="projects")
                logo_path = uploaded["url"]

            pm_ids = ProjectService._parse_json_list(project_manager_ids) if project_manager_ids is not None else None
            tl_ids = ProjectService._parse_json_list(team_leader_ids) if team_leader_ids is not None else None
            tm_ids = ProjectService._parse_json_list(team_member_ids) if team_member_ids is not None else None
            tags_list = ProjectService._parse_json_list(tags) if tags is not None else None
            tech_stacks = ProjectService._parse_json_list(technical_stacks) if technical_stacks is not None else None
            vendors = ProjectService._parse_json_list(third_party_vendors) if third_party_vendors is not None else None

            project_update = ProjectUpdate(
                name=name,
                client_id=client_id,
                description=description,
                start_date=start_date,
                end_date=end_date,
                status=status,
                priority=priority,
                project_manager_ids=pm_ids,
                team_leader_ids=tl_ids,
                team_member_ids=tm_ids,
                budget=budget,
                currency=currency,
                tags=tags_list,
                technical_stacks=tech_stacks,
                third_party_vendors=vendors,
                logo=logo_path
            )

            update_data = {k: v for k, v in project_update.dict().items() if v is not None}
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
