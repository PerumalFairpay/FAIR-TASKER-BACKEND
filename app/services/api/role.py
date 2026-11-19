from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from bson import ObjectId
from app.database import roles_collection
from app.models import RoleCreate, RoleUpdate, RoleResponse
import traceback


class RoleService:

    @staticmethod
    def _format_role(role_doc: dict) -> dict:
        return RoleResponse(
            id=str(role_doc["_id"]),
            name=role_doc["name"],
            description=role_doc.get("description")
        ).dict()

    @staticmethod
    async def create(role_in: RoleCreate) -> Tuple[Optional[dict], Optional[str]]:
        try:
            existing_role = await roles_collection.find_one({
                "name": role_in.name,
                "is_deleted": {"$ne": True}
            })
            if existing_role:
                return None, "Role with this name already exists"

            role_dict = role_in.dict()
            role_dict["is_deleted"] = False
            role_dict["deleted_at"] = None
            role_dict["created_at"] = datetime.utcnow()

            result = await roles_collection.insert_one(role_dict)
            created_role = await roles_collection.find_one({"_id": result.inserted_id})
            if not created_role:
                return None, "Failed to retrieve created role"

            return RoleService._format_role(created_role), None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def list() -> Tuple[Optional[List[dict]], Optional[str]]:
        try:
            roles = []
            async for role in roles_collection.find({"is_deleted": {"$ne": True}}):
                roles.append(RoleService._format_role(role))
            return roles, None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def get(role_id: str) -> Tuple[Optional[dict], Optional[str]]:
        try:
            if not ObjectId.is_valid(role_id):
                return None, "Invalid role ID"

            role = await roles_collection.find_one({
                "_id": ObjectId(role_id),
                "is_deleted": {"$ne": True}
            })
            if not role:
                return None, "Role not found"

            return RoleService._format_role(role), None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def update(role_id: str, role_update: RoleUpdate) -> Tuple[Optional[dict], Optional[str]]:
        try:
            if not ObjectId.is_valid(role_id):
                return None, "Invalid role ID"

            update_data = {k: v for k, v in role_update.dict().items() if v is not None}
            if not update_data:
                return None, "No data to update"

            if "name" in update_data:
                existing_role = await roles_collection.find_one({
                    "name": update_data["name"],
                    "_id": {"$ne": ObjectId(role_id)},
                    "is_deleted": {"$ne": True}
                })
                if existing_role:
                    return None, "Role with this name already exists"

            update_data["updated_at"] = datetime.utcnow()
            result = await roles_collection.update_one(
                {"_id": ObjectId(role_id), "is_deleted": {"$ne": True}},
                {"$set": update_data}
            )
            if result.matched_count == 0:
                return None, "Role not found"

            updated_role = await roles_collection.find_one({"_id": ObjectId(role_id)})
            if not updated_role:
                return None, "Role not found"

            return RoleService._format_role(updated_role), None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def delete(role_id: str) -> Tuple[bool, Optional[str]]:
        try:
            if not ObjectId.is_valid(role_id):
                return False, "Invalid role ID"

            result = await roles_collection.update_one(
                {"_id": ObjectId(role_id), "is_deleted": {"$ne": True}},
                {"$set": {"is_deleted": True, "deleted_at": datetime.utcnow()}}
            )
            if result.matched_count == 0:
                return False, "Role not found"

            return True, None
        except Exception as e:
            traceback.print_exc()
            return False, str(e)
