from typing import Dict, Any, List, Optional, Tuple
from app.database import users_collection, employees_collection
from app.models import UserLogin
from app.utils import verify_password
from app.auth import create_access_token
import traceback


class AuthService:

    @staticmethod
    async def login(user_in: UserLogin) -> Tuple[Optional[dict], Optional[str], Optional[str]]:
        """Returns (user_data, token, error)"""
        try:
            user_record = await users_collection.find_one({"email": user_in.email, "is_deleted": {"$ne": True}})
            if not user_record or not verify_password(user_in.password, user_record.get("hashed_password", "")):
                return None, None, "We couldn't log you in. Please check your credentials or contact support if your account is inactive."

            token = create_access_token(user_record)

            business_id = user_record.get("employee_no_id")
            db_employee_id = None
            employee_no_id = business_id
            gender = None

            if business_id:
                employee = await employees_collection.find_one({"employee_no_id": business_id, "is_deleted": {"$ne": True}})
                if employee:
                    db_employee_id = str(employee["_id"])
                    employee_no_id = employee.get("employee_no_id")
                    gender = employee.get("gender")

            user_data = {
                "id": str(user_record["_id"]),
                "employee_id": db_employee_id,
                "employee_no_id": employee_no_id,
                "name": user_record.get("name"),
                "email": user_record.get("email"),
                "mobile": user_record.get("mobile"),
                "address": user_record.get("address"),
                "gender": gender,
                "role": user_record.get("role", "employee"),
            }
            return user_data, token, None
        except Exception as e:
            traceback.print_exc()
            return None, None, str(e)

    @staticmethod
    async def get_me(current_user: dict) -> Tuple[Optional[dict], Optional[str]]:
        try:
            user_copy = dict(current_user)
            user_copy.pop("hashed_password", None)

            if "employee_no_id" in user_copy and user_copy["employee_no_id"]:
                business_id = user_copy["employee_no_id"]
                employee = await employees_collection.find_one({"employee_no_id": business_id, "is_deleted": {"$ne": True}})
                if employee:
                    user_copy["profile_picture"] = employee.get("profile_picture")
                    user_copy["work_mode"] = employee.get("work_mode")
                    user_copy["gender"] = employee.get("gender")
                    user_copy["weekly_off"] = employee.get("weekly_off")
                    user_copy["lop_rule_01"] = employee.get("lop_rule_01", False)
                    user_copy["employee_id"] = str(employee["_id"])
                    user_copy["employee_no_id"] = employee.get("employee_no_id")
                    user_copy.pop("biometric_id", None)

            return user_copy, None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)
