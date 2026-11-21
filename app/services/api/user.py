from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from bson import ObjectId
from app.database import users_collection, employees_collection, roles_collection
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

            # Batch fetch roles for efficiency
            role_ids = set()
            emp_no_ids = set()
            for u in users_list:
                r_id = u.get("role_id")
                if r_id and ObjectId.is_valid(str(r_id)):
                    role_ids.add(ObjectId(str(r_id)))
                emp_code = u.get("employee_no_id")
                if emp_code:
                    emp_no_ids.add(emp_code)

            roles_map = {}
            if role_ids:
                roles_docs = await roles_collection.find({"_id": {"$in": list(role_ids)}}).to_list(length=len(role_ids))
                for r in roles_docs:
                    roles_map[str(r["_id"])] = {
                        "id": str(r["_id"]),
                        "name": r.get("name", ""),
                        "description": r.get("description", "")
                    }

            employees_map = {}
            if emp_no_ids:
                emp_docs = await employees_collection.find(
                    {"employee_no_id": {"$in": list(emp_no_ids)}, "is_deleted": {"$ne": True}},
                    {"_id": 1, "employee_no_id": 1}
                ).to_list(length=len(emp_no_ids))
                for emp in emp_docs:
                    employees_map[str(emp["employee_no_id"])] = str(emp["_id"])

            sanitized = []
            for u in users_list:
                u_norm = normalize(u)
                u_norm.pop("hashed_password", None)
                u_norm.pop("password", None)

                # Attach employee table primary id
                emp_code = u_norm.get("employee_no_id")
                u_norm["employee_id"] = employees_map.get(str(emp_code)) if emp_code else None

                r_id = str(u_norm.get("role_id") or "")
                role_obj = roles_map.get(r_id)
                if not role_obj:
                    r_name = u_norm.get("role")
                    role_obj = {
                        "id": r_id,
                        "name": r_name if isinstance(r_name, str) else (r_name.get("name", "") if isinstance(r_name, dict) else "employee"),
                        "description": ""
                    }

                u_norm["role"] = role_obj
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

            # Attach employee table primary id
            emp_code = user_norm.get("employee_no_id")
            if emp_code:
                emp_doc = await employees_collection.find_one(
                    {"employee_no_id": emp_code, "is_deleted": {"$ne": True}},
                    {"_id": 1}
                )
                user_norm["employee_id"] = str(emp_doc["_id"]) if emp_doc else None
            else:
                user_norm["employee_id"] = None

            r_id = user_norm.get("role_id")
            role_data = None
            if r_id and ObjectId.is_valid(str(r_id)):
                role_data = await roles_collection.find_one({"_id": ObjectId(str(r_id))})

            role_obj = {
                "id": str(role_data["_id"]) if role_data else str(r_id or ""),
                "name": role_data.get("name", user_norm.get("role") or "employee") if role_data else (user_norm.get("role") or "employee"),
                "description": role_data.get("description", "") if role_data else ""
            }
            user_norm["role"] = role_obj
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
                # Soft delete corresponding employee strictly by employee_id (fallback to employee_no_id)
                emp_id = user.get("employee_id")
                emp_no_id = user.get("employee_no_id")
                
                emp_query = []
                if emp_id and ObjectId.is_valid(str(emp_id)):
                    emp_query.append({"_id": ObjectId(str(emp_id))})
                if emp_no_id:
                    emp_query.append({"employee_no_id": emp_no_id})

                if emp_query:
                    await employees_collection.update_many(
                        {"$or": emp_query},
                        {"$set": {"is_deleted": True, "deleted_at": deleted_at}}
                    )

            return True, None
        except Exception as e:
            traceback.print_exc()
            return False, str(e)
