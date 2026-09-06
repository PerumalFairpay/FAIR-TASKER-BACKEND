from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from bson import ObjectId
from app.database import users_collection, employees_collection, employee_documents_collection
from app.models import EmployeeUpdate
from app.utils import normalize, verify_password, get_password_hash
import traceback


class ProfileService:

    @staticmethod
    async def get_profile(current_user: dict) -> Tuple[Optional[dict], Optional[str]]:
        try:
            employee_id = current_user.get("employee_no_id")
            if not employee_id:
                # If no employee_no_id link, return user data as fallback
                user_copy = dict(current_user)
                user_copy.pop("hashed_password", None)
                return user_copy, None

            # Find employee by employee_no_id (the logical link)
            employee = await employees_collection.find_one({
                "employee_no_id": employee_id,
                "is_deleted": {"$ne": True}
            })
            if not employee:
                user_copy = dict(current_user)
                user_copy.pop("hashed_password", None)
                return user_copy, None

            full_profile = normalize(employee)
            # Ensure sensitive fields are removed
            full_profile.pop("hashed_password", None)
            full_profile.pop("password", None)

            # Fetch documents from separate collection (only for admins)
            if current_user.get("role") in ["admin", "super_admin"]:
                employee_id_str = str(employee["_id"])
                documents = await employee_documents_collection.find({"employee_id": employee_id_str}).to_list(length=None)
                full_profile["documents"] = [normalize(doc) for doc in documents]
            else:
                full_profile["documents"] = []

            # Add permissions and user ID from the user database record
            full_profile["permissions"] = current_user.get("permissions", [])
            full_profile["user_id"] = current_user.get("id")

            return full_profile, None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def update_profile(
        current_user: dict,
        update_data: EmployeeUpdate,
        profile_picture_path: Optional[str] = None
    ) -> Tuple[Optional[dict], Optional[str]]:
        try:
            employee_id = current_user.get("employee_no_id")
            if not employee_id:
                return None, "Employee record not found for this user"

            # Find employee by employee_no_id
            employee = await employees_collection.find_one({
                "employee_no_id": employee_id,
                "is_deleted": {"$ne": True}
            })
            if not employee:
                return None, "Employee record not found"

            db_id = str(employee["_id"])
            update_dict = {k: v for k, v in update_data.dict().items() if v is not None}
            if profile_picture_path:
                update_dict["profile_picture"] = profile_picture_path

            # Check if email is being updated to a new value and if it is already taken by another active user
            if "email" in update_dict and update_dict["email"] and update_dict["email"] != employee.get("email"):
                existing_email = await users_collection.find_one({
                    "is_deleted": {"$ne": True},
                    "email": update_dict["email"]
                })
                if existing_email:
                    return None, f"User with email {update_dict['email']} already exists"

            if "personal_email" in update_dict and update_dict["personal_email"]:
                existing_personal = await employees_collection.find_one({
                    "is_deleted": {"$ne": True},
                    "personal_email": update_dict["personal_email"],
                    "_id": {"$ne": ObjectId(db_id)}
                })
                if existing_personal:
                    return None, f"User with personal email {update_dict['personal_email']} already exists"

            documents_to_sync = update_dict.pop("documents", None)

            if update_dict:
                update_dict["updated_at"] = datetime.utcnow()
                await employees_collection.update_one(
                    {"_id": ObjectId(db_id)},
                    {"$set": update_dict}
                )

            # Sync Documents if provided
            if documents_to_sync is not None:
                current_docs = await employee_documents_collection.find({"employee_id": db_id}).to_list(length=None)
                current_proofs = {d.get("document_proof") for d in current_docs}

                for doc in documents_to_sync:
                    doc_dict = doc if isinstance(doc, dict) else doc.dict()
                    if doc_dict.get("document_proof") not in current_proofs:
                        doc_dict["employee_id"] = db_id
                        doc_dict["created_at"] = datetime.utcnow()
                        doc_dict["updated_at"] = datetime.utcnow()
                        await employee_documents_collection.insert_one(doc_dict)
                    else:
                        await employee_documents_collection.update_one(
                            {"employee_id": db_id, "document_proof": doc_dict["document_proof"]},
                            {"$set": {
                                "document_name": doc_dict.get("document_name"),
                                "file_type": doc_dict.get("file_type"),
                                "updated_at": datetime.utcnow()
                            }}
                        )

            # Update User if critical fields changed
            user_update = {}
            if "email" in update_dict:
                user_update["email"] = update_dict["email"]
            if "name" in update_dict:
                user_update["name"] = update_dict["name"]
            if "mobile" in update_dict:
                user_update["mobile"] = update_dict["mobile"]
            if "address" in update_dict:
                user_update["address"] = update_dict["address"]

            if user_update and "email" in employee:
                await users_collection.update_one(
                    {"email": employee["email"]},
                    {"$set": user_update}
                )

            # Fetch updated employee
            updated_emp = await employees_collection.find_one({"_id": ObjectId(db_id), "is_deleted": {"$ne": True}})
            if updated_emp:
                if "hashed_password" in updated_emp:
                    del updated_emp["hashed_password"]
                docs = await employee_documents_collection.find({"employee_id": db_id}).to_list(length=None)
                updated_emp["documents"] = [normalize(d) for d in docs]
                return normalize(updated_emp), None

            return None, "Failed to fetch updated employee profile"
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def change_password(current_user: dict, current_password: str, new_password: str) -> Tuple[bool, Optional[str]]:
        try:
            user_id = current_user.get("id")
            if not user_id or not ObjectId.is_valid(user_id):
                return False, "Invalid user ID"

            # Verify current password
            user_record = await users_collection.find_one({"_id": ObjectId(user_id), "is_deleted": {"$ne": True}})
            if not user_record or not verify_password(current_password, user_record.get("hashed_password", "")):
                return False, "Invalid current password"

            # Hash new password
            hashed_password = get_password_hash(new_password)

            # Update User table
            await users_collection.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {"hashed_password": hashed_password, "updated_at": datetime.utcnow()}}
            )

            # Update Employee table if employee_no_id exists
            employee_id = current_user.get("employee_no_id")
            if employee_id:
                await employees_collection.update_one(
                    {"employee_no_id": employee_id},
                    {"$set": {"hashed_password": hashed_password, "updated_at": datetime.utcnow()}}
                )

            return True, None
        except Exception as e:
            traceback.print_exc()
            return False, str(e)
