from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from bson import ObjectId
from app.database import (
    roles_collection,
    permissions_collection,
    role_permissions_collection,
    user_permissions_collection,
    users_collection,
)
from app.models import (
    RoleCreate,
    RoleUpdate,
    RoleResponse,
    PermissionResponse,
)
import traceback


class RoleService:

    @staticmethod
    async def _role_to_response(role_doc: dict) -> RoleResponse:
        role_id_str = str(role_doc["_id"])
        
        # 1. Fetch active permission links for this role
        links = await role_permissions_collection.find({
            "role_id": role_id_str,
            "is_deleted": {"$ne": True}
        }).to_list(length=None)
        
        perm_ids = [l["permission_id"] for l in links if "permission_id" in l]
        valid_obj_ids = [ObjectId(pid) for pid in perm_ids if ObjectId.is_valid(pid)]
        
        # 2. Fetch permission details
        permissions: List[PermissionResponse] = []
        if valid_obj_ids:
            perms_cursor = permissions_collection.find({
                "_id": {"$in": valid_obj_ids},
                "is_deleted": {"$ne": True}
            }).sort([("module", 1), ("name", 1)])
            
            async for p in perms_cursor:
                permissions.append(PermissionResponse(
                    id=str(p["_id"]),
                    code=p.get("code", ""),
                    name=p.get("name", ""),
                    module=p.get("module", ""),
                    description=p.get("description"),
                    created_at=p.get("created_at"),
                    updated_at=p.get("updated_at"),
                ))

        return RoleResponse(
            id=role_id_str,
            name=role_doc.get("name", ""),
            description=role_doc.get("description"),
            permissions=permissions,
            created_at=role_doc.get("created_at"),
            updated_at=role_doc.get("updated_at"),
        )

    @staticmethod
    async def create(role_in: RoleCreate) -> Tuple[Optional[dict], Optional[str]]:
        try:
            existing_role = await roles_collection.find_one({
                "name": role_in.name,
                "is_deleted": {"$ne": True}
            })
            if existing_role:
                return None, "Role with this name already exists"

            now = datetime.utcnow()
            role_dict = {
                "name": role_in.name,
                "description": role_in.description,
                "is_deleted": False,
                "deleted_at": None,
                "created_at": now,
                "updated_at": now,
            }

            result = await roles_collection.insert_one(role_dict)
            role_id_str = str(result.inserted_id)

            # Insert role permissions
            if role_in.permission_ids:
                unique_pids = set(role_in.permission_ids)
                links = []
                for pid in unique_pids:
                    if ObjectId.is_valid(pid):
                        # Verify permission exists
                        perm = await permissions_collection.find_one({
                            "_id": ObjectId(pid),
                            "is_deleted": {"$ne": True}
                        })
                        if perm:
                            links.append({
                                "role_id": role_id_str,
                                "permission_id": pid,
                                "is_deleted": False,
                                "deleted_at": None,
                                "created_at": now,
                                "updated_at": now,
                            })
                if links:
                    await role_permissions_collection.insert_many(links)

            created_role = await roles_collection.find_one({"_id": result.inserted_id})
            if not created_role:
                return None, "Failed to retrieve created role"

            resp = await RoleService._role_to_response(created_role)
            return resp.dict(), None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def list() -> Tuple[Optional[List[dict]], Optional[str]]:
        try:
            roles = []
            async for role in roles_collection.find({"is_deleted": {"$ne": True}}).sort("created_at", -1):
                role_resp = await RoleService._role_to_response(role)
                roles.append(role_resp.dict())
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

            role_resp = await RoleService._role_to_response(role)
            return role_resp.dict(), None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def update(role_id: str, role_update: RoleUpdate) -> Tuple[Optional[dict], Optional[str]]:
        try:
            if not ObjectId.is_valid(role_id):
                return None, "Invalid role ID"

            update_data = {k: v for k, v in role_update.dict().items() if v is not None and k != "permission_ids"}

            if "name" in update_data:
                existing_role = await roles_collection.find_one({
                    "name": update_data["name"],
                    "_id": {"$ne": ObjectId(role_id)},
                    "is_deleted": {"$ne": True}
                })
                if existing_role:
                    return None, "Role with this name already exists"

            now = datetime.utcnow()
            update_data["updated_at"] = now

            result = await roles_collection.update_one(
                {"_id": ObjectId(role_id), "is_deleted": {"$ne": True}},
                {"$set": update_data}
            )
            if result.matched_count == 0:
                return None, "Role not found"

            # Sync permissions if permission_ids provided
            if role_update.permission_ids is not None:
                # 1. Soft-delete existing role_permissions
                await role_permissions_collection.update_many(
                    {"role_id": role_id, "is_deleted": {"$ne": True}},
                    {"$set": {"is_deleted": True, "deleted_at": now}}
                )

                # 2. Insert new role_permissions
                new_pids = set(role_update.permission_ids)
                links = []
                for pid in new_pids:
                    if ObjectId.is_valid(pid):
                        perm = await permissions_collection.find_one({
                            "_id": ObjectId(pid),
                            "is_deleted": {"$ne": True}
                        })
                        if perm:
                            links.append({
                                "role_id": role_id,
                                "permission_id": pid,
                                "is_deleted": False,
                                "deleted_at": None,
                                "created_at": now,
                                "updated_at": now,
                            })
                if links:
                    await role_permissions_collection.insert_many(links)

            updated_role = await roles_collection.find_one({"_id": ObjectId(role_id)})
            if not updated_role:
                return None, "Role not found"

            role_resp = await RoleService._role_to_response(updated_role)
            return role_resp.dict(), None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def delete(role_id: str) -> Tuple[bool, Optional[str]]:
        try:
            if not ObjectId.is_valid(role_id):
                return False, "Invalid role ID"

            now = datetime.utcnow()
            result = await roles_collection.update_one(
                {"_id": ObjectId(role_id), "is_deleted": {"$ne": True}},
                {"$set": {"is_deleted": True, "deleted_at": now}}
            )
            if result.matched_count == 0:
                return False, "Role not found"

            # Soft-delete related role_permissions
            await role_permissions_collection.update_many(
                {"role_id": role_id, "is_deleted": {"$ne": True}},
                {"$set": {"is_deleted": True, "deleted_at": now}}
            )

            return True, None
        except Exception as e:
            traceback.print_exc()
            return False, str(e)

    @staticmethod
    async def get_user_permissions(user_id: str) -> List[str]:
        """
        Computes effective permissions for a user:
        (Role Permissions) UNION (Direct User Permissions) -> List of permission codes.
        """
        try:
            if not ObjectId.is_valid(user_id):
                return []

            user = await users_collection.find_one({
                "_id": ObjectId(user_id),
                "is_deleted": {"$ne": True}
            })
            if not user:
                return []

            perm_ids = set()

            # 1. Role permissions (if user has role_id)
            role_id = user.get("role_id")
            if role_id:
                role_links = await role_permissions_collection.find({
                    "role_id": str(role_id),
                    "is_deleted": {"$ne": True}
                }).to_list(length=None)
                for l in role_links:
                    if "permission_id" in l:
                        perm_ids.add(l["permission_id"])

            # 2. User direct permissions
            user_links = await user_permissions_collection.find({
                "user_id": str(user_id),
                "is_deleted": {"$ne": True}
            }).to_list(length=None)
            for l in user_links:
                if "permission_id" in l:
                    perm_ids.add(l["permission_id"])

            if not perm_ids:
                return []

            valid_obj_ids = [ObjectId(pid) for pid in perm_ids if ObjectId.is_valid(pid)]
            if not valid_obj_ids:
                return []

            perms = await permissions_collection.find({
                "_id": {"$in": valid_obj_ids},
                "is_deleted": {"$ne": True}
            }).to_list(length=None)

            return [p.get("code") for p in perms if p.get("code")]
        except Exception:
            traceback.print_exc()
            return []
