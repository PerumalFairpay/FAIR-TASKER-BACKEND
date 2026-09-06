from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from bson import ObjectId
from app.database import expense_categories_collection
from app.models import ExpenseCategoryCreate, ExpenseCategoryUpdate
from app.utils import normalize
import traceback


class ExpenseCategoryService:

    @staticmethod
    async def create(category_in: ExpenseCategoryCreate) -> Tuple[Optional[dict], Optional[str]]:
        try:
            data = category_in.dict()
            data["is_deleted"] = False
            data["deleted_at"] = None
            data["created_at"] = datetime.utcnow()
            result = await expense_categories_collection.insert_one(data)
            data["id"] = str(result.inserted_id)
            return normalize(data), None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def list() -> Tuple[Optional[List[dict]], Optional[str]]:
        try:
            items = await expense_categories_collection.find(
                {"is_deleted": {"$ne": True}}
            ).to_list(length=None)
            return [normalize(c) for c in items], None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def get(category_id: str) -> Tuple[Optional[dict], Optional[str]]:
        try:
            if not ObjectId.is_valid(category_id):
                return None, "Invalid expense category ID"

            category = await expense_categories_collection.find_one({
                "_id": ObjectId(category_id),
                "is_deleted": {"$ne": True}
            })
            if not category:
                return None, "Expense category not found"

            return normalize(category), None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def update(category_id: str, category_in: ExpenseCategoryUpdate) -> Tuple[Optional[dict], Optional[str]]:
        try:
            if not ObjectId.is_valid(category_id):
                return None, "Invalid expense category ID"

            update_data = {k: v for k, v in category_in.dict().items() if v is not None}
            if update_data:
                update_data["updated_at"] = datetime.utcnow()
                result = await expense_categories_collection.update_one(
                    {"_id": ObjectId(category_id), "is_deleted": {"$ne": True}},
                    {"$set": update_data}
                )
                if result.matched_count == 0:
                    return None, "Expense category not found"

            return await ExpenseCategoryService.get(category_id)
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def delete(category_id: str) -> Tuple[bool, Optional[str]]:
        try:
            if not ObjectId.is_valid(category_id):
                return False, "Invalid expense category ID"

            result = await expense_categories_collection.update_one(
                {"_id": ObjectId(category_id), "is_deleted": {"$ne": True}},
                {"$set": {"is_deleted": True, "deleted_at": datetime.utcnow()}}
            )
            if result.matched_count == 0:
                return False, "Expense category not found"

            return True, None
        except Exception as e:
            traceback.print_exc()
            return False, str(e)
