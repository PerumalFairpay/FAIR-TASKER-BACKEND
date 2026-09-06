from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from bson import ObjectId
from app.database import users_collection, employees_collection
from app.utils import normalize
import traceback


class UserService:

    @staticmethod
    async def list(
        page: int = 1,
        limit: int = 10,
        search: Optional[str] = None,
        role: Optional[str] = None
    ) -> Tuple[Optional[List[dict]], Optional[dict], Optional[str]]:
        try:
            query = {"is_deleted": {"$ne": True}}

            if role:
                query["role"] = role

            if search:
                regex_pattern = {"$regex": search, "$options": "i"}
                query["$or"] = [
                    {"name": regex_pattern},
                    {"email": regex_pattern},
                    {"employee_no_id": regex_pattern},
                    {"mobile": regex_pattern},
                ]

            skip = (page - 1) * limit
            total_items = await users_collection.count_documents(query)

            users_list = (
                await users_collection.find(query)
                .skip(skip)
                .limit(limit)
                .to_list(length=limit)
            )

            sanitized = []
            for u in users_list:
                u_norm = normalize(u)
                u_norm.pop("hashed_password", None)
                u_norm.pop("password", None)
                sanitized.append(u_norm)

            total_pages = (total_items + limit - 1) // limit if limit > 0 else 0
            meta = {
                "current_page": page,
                "total_pages": total_pages,
                "total_items": total_items,
                "limit": limit
            }

            return sanitized, meta, None
        except Exception as e:
            traceback.print_exc()
            return None, None, str(e)

    @staticmethod
    async def get(user_id: str) -> Tuple[Optional[dict], Optional[str]]:
        try:
            if not ObjectId.is_valid(user_id):
                return None, "Invalid user ID"

            user = await users_collection.find_one({
                "_id": ObjectId(user_id),
                "is_deleted": {"$ne": True}
            })
            if not user:
                return None, "User not found"

            user_norm = normalize(user)
            user_norm.pop("hashed_password", None)
            user_norm.pop("password", None)
            return user_norm, None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def delete(user_id: str) -> Tuple[bool, Optional[str]]:
        try:
            if not ObjectId.is_valid(user_id):
                return False, "Invalid user ID"

            user = await users_collection.find_one({
                "_id": ObjectId(user_id),
                "is_deleted": {"$ne": True}
            })
            if not user:
                return False, "User not found"

            deleted_at = datetime.utcnow()
            result = await users_collection.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {"is_deleted": True, "deleted_at": deleted_at}}
            )

            if result.modified_count > 0:
                if "employee_no_id" in user:
                    await employees_collection.update_one(
                        {"employee_no_id": user["employee_no_id"]},
                        {"$set": {"is_deleted": True, "deleted_at": deleted_at}}
                    )

            return True, None
        except Exception as e:
            traceback.print_exc()
            return False, str(e)
