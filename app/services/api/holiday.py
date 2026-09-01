from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from bson import ObjectId
from app.database import holidays_collection
from app.models import HolidayCreate, HolidayUpdate
from app.utils import normalize
import traceback


class HolidayService:

    @staticmethod
    async def create(holiday_data: HolidayCreate) -> Tuple[Optional[dict], Optional[str]]:
        try:
            data = holiday_data.dict()
            data["is_deleted"] = False
            data["deleted_at"] = None
            data["created_at"] = datetime.utcnow()
            result = await holidays_collection.insert_one(data)
            data["id"] = str(result.inserted_id)
            return normalize(data), None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def list() -> Tuple[Optional[List[dict]], Optional[str]]:
        try:
            holidays = await holidays_collection.find(
                {"is_deleted": {"$ne": True}}
            ).to_list(length=None)
            return [normalize(h) for h in holidays], None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def get(holiday_id: str) -> Tuple[Optional[dict], Optional[str]]:
        try:
            if not ObjectId.is_valid(holiday_id):
                return None, "Invalid holiday ID"
            holiday = await holidays_collection.find_one({
                "_id": ObjectId(holiday_id),
                "is_deleted": {"$ne": True}
            })
            if not holiday:
                return None, "Holiday not found"
            return normalize(holiday), None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def update(holiday_id: str, holiday_data: HolidayUpdate) -> Tuple[Optional[dict], Optional[str]]:
        try:
            if not ObjectId.is_valid(holiday_id):
                return None, "Invalid holiday ID"

            update_data = {k: v for k, v in holiday_data.dict().items() if v is not None}
            if update_data:
                update_data["updated_at"] = datetime.utcnow()
                result = await holidays_collection.update_one(
                    {"_id": ObjectId(holiday_id), "is_deleted": {"$ne": True}},
                    {"$set": update_data}
                )
                if result.matched_count == 0:
                    return None, "Holiday not found"

            updated_holiday = await holidays_collection.find_one({
                "_id": ObjectId(holiday_id),
                "is_deleted": {"$ne": True}
            })
            if not updated_holiday:
                return None, "Holiday not found"
            return normalize(updated_holiday), None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def delete(holiday_id: str) -> Tuple[bool, Optional[str]]:
        try:
            if not ObjectId.is_valid(holiday_id):
                return False, "Invalid holiday ID"
            result = await holidays_collection.update_one(
                {"_id": ObjectId(holiday_id), "is_deleted": {"$ne": True}},
                {"$set": {"is_deleted": True, "deleted_at": datetime.utcnow()}}
            )
            if result.matched_count == 0:
                return False, "Holiday not found"
            return True, None
        except Exception as e:
            traceback.print_exc()
            return False, str(e)

