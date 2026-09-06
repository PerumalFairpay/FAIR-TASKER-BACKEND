from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from bson import ObjectId
from app.database import roles_collection, permissions_collection
from app.models import RoleCreate, RoleUpdate, RoleResponse, PermissionShortRef
import traceback


class RoleService:

    @staticmethod
    async def _get_permissions_map() -> Dict[str, str]:
        """Returns a dictionary mapping permission ID (str) to permission Name."""
        perm_map = {}
        async for perm in permissions_collection.find({"is_deleted": {"$ne": True}}):
            perm_map[str(perm["_id"])] = perm["name"]
        return perm_map

    @staticmethod
    def _enrich_role(role_doc: dict, perm_map: Dict[str, str]) -> dict:
        permission_ids = role_doc.get("permissions", [])
        enriched_permissions = []
        for pid in permission_ids:
            pid_str = str(pid)
            if pid_str in perm_map:
                enriched_permissions.append(PermissionShortRef(id=pid_str, name=perm_map[pid_str]))

        return RoleResponse(
            id=str(role_doc["_id"]),
            name=role_doc["name"],
            description=role_doc.get("description"),
            permissions=enriched_permissions
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

            perm_map = await RoleService._get_permissions_map()
            return RoleService._enrich_role(created_role, perm_map), None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def list() -> Tuple[Optional[List[dict]], Optional[str]]:
        try:
            perm_map = await RoleService._get_permissions_map()
            roles = []
            async for role in roles_collection.find({"is_deleted": {"$ne": True}}):
                roles.append(RoleService._enrich_role(role, perm_map))
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

            perm_map = await RoleService._get_permissions_map()
            return RoleService._enrich_role(role, perm_map), None
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

            perm_map = await RoleService._get_permissions_map()
            return RoleService._enrich_role(updated_role, perm_map), None
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
