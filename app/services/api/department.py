from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from bson import ObjectId
from app.database import departments_collection
from app.models import DepartmentCreate, DepartmentUpdate
from app.utils import normalize
import traceback


class DepartmentService:

    @staticmethod
    async def create(department_in: DepartmentCreate) -> Tuple[Optional[dict], Optional[str]]:
        try:
            data = department_in.dict()
            data["is_deleted"] = False
            data["deleted_at"] = None
            data["created_at"] = datetime.utcnow()
            result = await departments_collection.insert_one(data)
            data["id"] = str(result.inserted_id)
            return normalize(data), None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def list() -> Tuple[Optional[List[dict]], Optional[str]]:
        try:
            items = await departments_collection.find(
                {"is_deleted": {"$ne": True}}
            ).to_list(length=None)
            return [normalize(d) for d in items], None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def get(department_id: str) -> Tuple[Optional[dict], Optional[str]]:
        try:
            if not ObjectId.is_valid(department_id):
                return None, "Invalid department ID"

            department = await departments_collection.find_one({
                "_id": ObjectId(department_id),
                "is_deleted": {"$ne": True}
            })
            if not department:
                return None, "Department not found"

            return normalize(department), None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def update(department_id: str, department_in: DepartmentUpdate) -> Tuple[Optional[dict], Optional[str]]:
        try:
            if not ObjectId.is_valid(department_id):
                return None, "Invalid department ID"

            update_data = {k: v for k, v in department_in.dict().items() if v is not None}
            if update_data:
                update_data["updated_at"] = datetime.utcnow()
                result = await departments_collection.update_one(
                    {"_id": ObjectId(department_id), "is_deleted": {"$ne": True}},
                    {"$set": update_data}
                )
                if result.matched_count == 0:
                    return None, "Department not found"

            return await DepartmentService.get(department_id)
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def delete(department_id: str) -> Tuple[bool, Optional[str]]:
        try:
            if not ObjectId.is_valid(department_id):
                return False, "Invalid department ID"

            result = await departments_collection.update_one(
                {"_id": ObjectId(department_id), "is_deleted": {"$ne": True}},
                {"$set": {"is_deleted": True, "deleted_at": datetime.utcnow()}}
            )
            if result.matched_count == 0:
                return False, "Department not found"

            return True, None
        except Exception as e:
            traceback.print_exc()
            return False, str(e)
