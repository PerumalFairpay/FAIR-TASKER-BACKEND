from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from bson import ObjectId
from app.database import leave_types_collection
from app.models import LeaveTypeCreate, LeaveTypeUpdate
from app.utils import normalize
import traceback


class LeaveTypeService:

    @staticmethod
    async def create(leave_type_in: LeaveTypeCreate) -> Tuple[Optional[dict], Optional[str]]:
        try:
            data = leave_type_in.dict()
            data["is_deleted"] = False
            data["deleted_at"] = None
            data["created_at"] = datetime.utcnow()
            result = await leave_types_collection.insert_one(data)
            data["id"] = str(result.inserted_id)
            return normalize(data), None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def list(status: Optional[str] = None) -> Tuple[Optional[List[dict]], Optional[str]]:
        try:
            query = {"is_deleted": {"$ne": True}}
            if status:
                query["status"] = status

            leave_types = await leave_types_collection.find(query).to_list(length=None)
            return [normalize(lt) for lt in leave_types], None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def get(leave_type_id: str) -> Tuple[Optional[dict], Optional[str]]:
        try:
            if not ObjectId.is_valid(leave_type_id):
                return None, "Invalid leave type ID"

            leave_type = await leave_types_collection.find_one({
                "_id": ObjectId(leave_type_id),
                "is_deleted": {"$ne": True}
            })
            if not leave_type:
                return None, "Leave type not found"

            return normalize(leave_type), None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def update(leave_type_id: str, leave_type_in: LeaveTypeUpdate) -> Tuple[Optional[dict], Optional[str]]:
        try:
            if not ObjectId.is_valid(leave_type_id):
                return None, "Invalid leave type ID"

            update_data = {k: v for k, v in leave_type_in.dict().items() if v is not None}
            if update_data:
                update_data["updated_at"] = datetime.utcnow()
                result = await leave_types_collection.update_one(
                    {"_id": ObjectId(leave_type_id), "is_deleted": {"$ne": True}},
                    {"$set": update_data}
                )
                if result.matched_count == 0:
                    return None, "Leave type not found"

            return await LeaveTypeService.get(leave_type_id)
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def delete(leave_type_id: str) -> Tuple[bool, Optional[str]]:
        try:
            if not ObjectId.is_valid(leave_type_id):
                return False, "Invalid leave type ID"

            result = await leave_types_collection.update_one(
                {"_id": ObjectId(leave_type_id), "is_deleted": {"$ne": True}},
                {"$set": {"is_deleted": True, "deleted_at": datetime.utcnow()}}
            )
            if result.matched_count == 0:
                return False, "Leave type not found"

            return True, None
        except Exception as e:
            traceback.print_exc()
            return False, str(e)
