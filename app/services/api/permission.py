from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from bson import ObjectId
from app.database import permissions_collection
from app.models import PermissionCreate, PermissionUpdate, PermissionResponse
import traceback


class PermissionService:

    @staticmethod
    async def create(perm_in: PermissionCreate) -> Tuple[Optional[dict], Optional[str]]:
        try:
            existing_perm = await permissions_collection.find_one({
                "slug": perm_in.slug,
                "is_deleted": {"$ne": True}
            })
            if existing_perm:
                return None, "Permission with this slug already exists"

            perm_dict = perm_in.dict()
            perm_dict["is_deleted"] = False
            perm_dict["deleted_at"] = None
            perm_dict["created_at"] = datetime.utcnow()

            result = await permissions_collection.insert_one(perm_dict)
            created_perm = await permissions_collection.find_one({"_id": result.inserted_id})
            if not created_perm:
                return None, "Failed to retrieve created permission"

            data = PermissionResponse(**created_perm, id=str(created_perm["_id"])).dict()
            return data, None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def list() -> Tuple[Optional[List[dict]], Optional[str]]:
        try:
            permissions = []
            async for perm in permissions_collection.find({"is_deleted": {"$ne": True}}):
                permissions.append(PermissionResponse(**perm, id=str(perm["_id"])).dict())
            return permissions, None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def get(permission_id: str) -> Tuple[Optional[dict], Optional[str]]:
        try:
            if not ObjectId.is_valid(permission_id):
                return None, "Invalid permission ID"

            perm = await permissions_collection.find_one({
                "_id": ObjectId(permission_id),
                "is_deleted": {"$ne": True}
            })
            if not perm:
                return None, "Permission not found"

            data = PermissionResponse(**perm, id=str(perm["_id"])).dict()
            return data, None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def update(permission_id: str, perm_update: PermissionUpdate) -> Tuple[Optional[dict], Optional[str]]:
        try:
            if not ObjectId.is_valid(permission_id):
                return None, "Invalid permission ID"

            update_data = {k: v for k, v in perm_update.dict().items() if v is not None}
            if not update_data:
                return None, "No data to update"

            if "slug" in update_data:
                existing_perm = await permissions_collection.find_one({
                    "slug": update_data["slug"],
                    "_id": {"$ne": ObjectId(permission_id)},
                    "is_deleted": {"$ne": True}
                })
                if existing_perm:
                    return None, "Permission with this slug already exists"

            update_data["updated_at"] = datetime.utcnow()
            result = await permissions_collection.update_one(
                {"_id": ObjectId(permission_id), "is_deleted": {"$ne": True}},
                {"$set": update_data}
            )
            if result.matched_count == 0:
                return None, "Permission not found"

            updated_perm = await permissions_collection.find_one({"_id": ObjectId(permission_id)})
            if not updated_perm:
                return None, "Permission not found"

            data = PermissionResponse(**updated_perm, id=str(updated_perm["_id"])).dict()
            return data, None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def delete(permission_id: str) -> Tuple[bool, Optional[str]]:
        try:
            if not ObjectId.is_valid(permission_id):
                return False, "Invalid permission ID"

            result = await permissions_collection.update_one(
                {"_id": ObjectId(permission_id), "is_deleted": {"$ne": True}},
                {"$set": {"is_deleted": True, "deleted_at": datetime.utcnow()}}
            )
            if result.matched_count == 0:
                return False, "Permission not found"

            return True, None
        except Exception as e:
            traceback.print_exc()
            return False, str(e)
