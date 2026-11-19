from typing import Optional, List, Tuple
from datetime import datetime
from bson import ObjectId
from app.database import (
    permissions_collection,
    role_permissions_collection,
    user_permissions_collection,
    users_collection,
    roles_collection,
)
from app.models import (
    PermissionCreate,
    PermissionResponse,
    UserPermissionsDetailResponse,
)
import traceback


class PermissionService:

    @staticmethod
    async def list() -> List[dict]:
        try:
            perms_cursor = permissions_collection.find({
                "is_deleted": {"$ne": True}
            }).sort([("module", 1), ("name", 1)])
            
            perms = []
            async for p in perms_cursor:
                perms.append(PermissionResponse(
                    id=str(p["_id"]),
                    code=p.get("code", ""),
                    name=p.get("name", ""),
                    module=p.get("module", ""),
                    description=p.get("description"),
                    created_at=p.get("created_at"),
                    updated_at=p.get("updated_at"),
                ).dict())
            return perms
        except Exception:
            traceback.print_exc()
            return []

    @staticmethod
    async def get_user_permissions_detail(user_id: str) -> Tuple[Optional[dict], Optional[str]]:
        try:
            if not ObjectId.is_valid(user_id):
                return None, "Invalid user ID"

            user = await users_collection.find_one({
                "_id": ObjectId(user_id),
                "is_deleted": {"$ne": True}
            })
            if not user:
                return None, "User not found"

            # 1. Role permissions
            role_perms: List[PermissionResponse] = []
            role_id_str = user.get("role_id")
            role_name = None

            if role_id_str:
                if ObjectId.is_valid(role_id_str):
                    role_doc = await roles_collection.find_one({
                        "_id": ObjectId(role_id_str),
                        "is_deleted": {"$ne": True}
                    })
                    if role_doc:
                        role_name = role_doc.get("name")

                role_links = await role_permissions_collection.find({
                    "role_id": str(role_id_str),
                    "is_deleted": {"$ne": True}
                }).to_list(length=None)

                r_perm_ids = [ObjectId(l["permission_id"]) for l in role_links if ObjectId.is_valid(l.get("permission_id", ""))]
                if r_perm_ids:
                    r_perms_cursor = permissions_collection.find({
                        "_id": {"$in": r_perm_ids},
                        "is_deleted": {"$ne": True}
                    }).sort([("module", 1), ("name", 1)])
                    async for p in r_perms_cursor:
                        role_perms.append(PermissionResponse(
                            id=str(p["_id"]),
                            code=p.get("code", ""),
                            name=p.get("name", ""),
                            module=p.get("module", ""),
                            description=p.get("description"),
                            created_at=p.get("created_at"),
                            updated_at=p.get("updated_at"),
                        ))

            # 2. User direct permissions
            direct_perms: List[PermissionResponse] = []
            user_links = await user_permissions_collection.find({
                "user_id": str(user_id),
                "is_deleted": {"$ne": True}
            }).to_list(length=None)

            d_perm_ids = [ObjectId(l["permission_id"]) for l in user_links if ObjectId.is_valid(l.get("permission_id", ""))]
            if d_perm_ids:
                d_perms_cursor = permissions_collection.find({
                    "_id": {"$in": d_perm_ids},
                    "is_deleted": {"$ne": True}
                }).sort([("module", 1), ("name", 1)])
                async for p in d_perms_cursor:
                    direct_perms.append(PermissionResponse(
                        id=str(p["_id"]),
                        code=p.get("code", ""),
                        name=p.get("name", ""),
                        module=p.get("module", ""),
                        description=p.get("description"),
                        created_at=p.get("created_at"),
                        updated_at=p.get("updated_at"),
                    ))

            # 3. Effective permissions (Unique code union)
            effective_codes = list({p.code for p in role_perms} | {p.code for p in direct_perms})

            detail = UserPermissionsDetailResponse(
                user_id=str(user["_id"]),
                name=user.get("name"),
                email=user.get("email"),
                role_id=str(role_id_str) if role_id_str else None,
                role_name=role_name,
                role_permissions=role_perms,
                direct_permissions=direct_perms,
                effective_permissions=effective_codes,
            )
            return detail.dict(), None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def update_user_permissions(user_id: str, permission_ids: List[str]) -> Tuple[Optional[dict], Optional[str]]:
        try:
            if not ObjectId.is_valid(user_id):
                return None, "Invalid user ID"

            user = await users_collection.find_one({
                "_id": ObjectId(user_id),
                "is_deleted": {"$ne": True}
            })
            if not user:
                return None, "User not found"

            now = datetime.utcnow()

            # 1. Soft-delete existing user direct permissions
            await user_permissions_collection.update_many(
                {"user_id": str(user_id), "is_deleted": {"$ne": True}},
                {"$set": {"is_deleted": True, "deleted_at": now}}
            )

            # 2. Insert new user direct permissions
            new_pids = set(permission_ids or [])
            links = []
            for pid in new_pids:
                if ObjectId.is_valid(pid):
                    perm = await permissions_collection.find_one({
                        "_id": ObjectId(pid),
                        "is_deleted": {"$ne": True}
                    })
                    if perm:
                        links.append({
                            "user_id": str(user_id),
                            "permission_id": pid,
                            "is_deleted": False,
                            "deleted_at": None,
                            "created_at": now,
                            "updated_at": now,
                        })

            if links:
                await user_permissions_collection.insert_many(links)

            # Return updated detail
            return await PermissionService.get_user_permissions_detail(user_id)
        except Exception as e:
            traceback.print_exc()
            return None, str(e)
