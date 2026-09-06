from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from bson import ObjectId
from app.database import checklist_templates_collection
from app.models import EmployeeChecklistTemplateCreate, EmployeeChecklistTemplateUpdate
from app.utils import normalize
import traceback


class ChecklistTemplateService:

    @staticmethod
    async def create(template_in: EmployeeChecklistTemplateCreate) -> Tuple[Optional[dict], Optional[str]]:
        try:
            data = template_in.dict()
            data["is_deleted"] = False
            data["deleted_at"] = None
            data["created_at"] = datetime.utcnow()
            result = await checklist_templates_collection.insert_one(data)
            data["id"] = str(result.inserted_id)
            return normalize(data), None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def list() -> Tuple[Optional[List[dict]], Optional[str]]:
        try:
            templates = await checklist_templates_collection.find(
                {"is_deleted": {"$ne": True}}
            ).to_list(length=None)
            return [normalize(t) for t in templates], None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def get(template_id: str) -> Tuple[Optional[dict], Optional[str]]:
        try:
            if not ObjectId.is_valid(template_id):
                return None, "Invalid template ID"

            template = await checklist_templates_collection.find_one({
                "_id": ObjectId(template_id),
                "is_deleted": {"$ne": True}
            })
            if not template:
                return None, "Template not found"

            return normalize(template), None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def update(template_id: str, template_in: EmployeeChecklistTemplateUpdate) -> Tuple[Optional[dict], Optional[str]]:
        try:
            if not ObjectId.is_valid(template_id):
                return None, "Invalid template ID"

            update_data = {k: v for k, v in template_in.dict().items() if v is not None}
            if update_data:
                update_data["updated_at"] = datetime.utcnow()
                result = await checklist_templates_collection.update_one(
                    {"_id": ObjectId(template_id), "is_deleted": {"$ne": True}},
                    {"$set": update_data}
                )
                if result.matched_count == 0:
                    return None, "Template not found"

            return await ChecklistTemplateService.get(template_id)
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def delete(template_id: str) -> Tuple[bool, Optional[str]]:
        try:
            if not ObjectId.is_valid(template_id):
                return False, "Invalid template ID"

            result = await checklist_templates_collection.update_one(
                {"_id": ObjectId(template_id), "is_deleted": {"$ne": True}},
                {"$set": {"is_deleted": True, "deleted_at": datetime.utcnow()}}
            )
            if result.matched_count == 0:
                return False, "Template not found"

            return True, None
        except Exception as e:
            traceback.print_exc()
            return False, str(e)
