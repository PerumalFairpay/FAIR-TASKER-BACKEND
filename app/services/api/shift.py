from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from bson import ObjectId
from app.database import shifts_collection
from app.models import ShiftCreate, ShiftUpdate
from app.utils import normalize
import traceback


class ShiftService:

    @staticmethod
    async def create(shift_in: ShiftCreate) -> Tuple[Optional[dict], Optional[str]]:
        try:
            data = shift_in.dict()
            data["is_deleted"] = False
            data["deleted_at"] = None
            data["created_at"] = datetime.utcnow()
            result = await shifts_collection.insert_one(data)
            data["id"] = str(result.inserted_id)
            return normalize(data), None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def list() -> Tuple[Optional[List[dict]], Optional[str]]:
        try:
            shifts = await shifts_collection.find(
                {"is_deleted": {"$ne": True}}
            ).to_list(length=None)
            return [normalize(s) for s in shifts], None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def get(shift_id: str) -> Tuple[Optional[dict], Optional[str]]:
        try:
            if not ObjectId.is_valid(shift_id):
                return None, "Invalid shift ID"

            shift = await shifts_collection.find_one({
                "_id": ObjectId(shift_id),
                "is_deleted": {"$ne": True}
            })
            if not shift:
                return None, "Shift not found"

            return normalize(shift), None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def update(shift_id: str, shift_in: ShiftUpdate) -> Tuple[Optional[dict], Optional[str]]:
        try:
            if not ObjectId.is_valid(shift_id):
                return None, "Invalid shift ID"

            update_data = {k: v for k, v in shift_in.dict().items() if v is not None}
            if update_data:
                update_data["updated_at"] = datetime.utcnow()
                result = await shifts_collection.update_one(
                    {"_id": ObjectId(shift_id), "is_deleted": {"$ne": True}},
                    {"$set": update_data}
                )
                if result.matched_count == 0:
                    return None, "Shift not found"

            return await ShiftService.get(shift_id)
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def delete(shift_id: str) -> Tuple[bool, Optional[str]]:
        try:
            if not ObjectId.is_valid(shift_id):
                return False, "Invalid shift ID"

            result = await shifts_collection.update_one(
                {"_id": ObjectId(shift_id), "is_deleted": {"$ne": True}},
                {"$set": {"is_deleted": True, "deleted_at": datetime.utcnow()}}
            )
            if result.matched_count == 0:
                return False, "Shift not found"

            return True, None
        except Exception as e:
            traceback.print_exc()
            return False, str(e)
