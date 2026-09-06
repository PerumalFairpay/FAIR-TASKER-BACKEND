from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from bson import ObjectId
from fastapi import UploadFile
from app.database import expenses_collection, expense_categories_collection
from app.models import ExpenseCreate, ExpenseUpdate
from app.helper.file_handler import file_handler
from app.utils import normalize
import traceback


class ExpenseService:

    @staticmethod
    async def create(
        expense_category_id: str,
        amount: float,
        purpose: str,
        payment_mode: str,
        date: str,
        expense_subcategory_id: Optional[str] = None,
        attachment: Optional[UploadFile] = None
    ) -> Tuple[Optional[dict], Optional[str]]:
        try:
            attachment_path = None
            file_type = None
            if attachment and attachment.filename:
                uploaded = await file_handler.upload_file(attachment, subfolder="expenses")
                attachment_path = uploaded["url"]
                file_type = attachment.content_type

            expense_data = ExpenseCreate(
                expense_category_id=expense_category_id,
                expense_subcategory_id=expense_subcategory_id,
                amount=amount,
                purpose=purpose,
                payment_mode=payment_mode,
                date=date,
                file_type=file_type
            )

            data = expense_data.dict()
            if attachment_path:
                data["attachment"] = attachment_path

            data["is_deleted"] = False
            data["deleted_at"] = None
            data["created_at"] = datetime.utcnow()

            result = await expenses_collection.insert_one(data)
            data["id"] = str(result.inserted_id)

            return await ExpenseService.get(data["id"])
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def list() -> Tuple[Optional[List[dict]], Optional[str]]:
        try:
            expenses = await expenses_collection.find(
                {"is_deleted": {"$ne": True}}
            ).to_list(length=None)

            categories = await expense_categories_collection.find(
                {"is_deleted": {"$ne": True}}
            ).to_list(length=None)
            category_map = {str(cat["_id"]): cat["name"] for cat in categories}

            result = []
            for exp in expenses:
                exp_norm = normalize(exp)
                exp_norm["category_name"] = category_map.get(
                    exp_norm.get("expense_category_id"), "Unknown"
                )
                exp_norm["subcategory_name"] = category_map.get(
                    exp_norm.get("expense_subcategory_id")
                )
                result.append(exp_norm)

            return result, None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def get(expense_id: str) -> Tuple[Optional[dict], Optional[str]]:
        try:
            if not ObjectId.is_valid(expense_id):
                return None, "Invalid expense ID"

            expense = await expenses_collection.find_one({
                "_id": ObjectId(expense_id),
                "is_deleted": {"$ne": True}
            })
            if not expense:
                return None, "Expense not found"

            exp_norm = normalize(expense)

            # Hydrate category names
            if exp_norm.get("expense_category_id") and ObjectId.is_valid(str(exp_norm.get("expense_category_id"))):
                cat = await expense_categories_collection.find_one(
                    {"_id": ObjectId(exp_norm["expense_category_id"])}
                )
                exp_norm["category_name"] = cat["name"] if cat else "Unknown"
            else:
                exp_norm["category_name"] = "Unknown"

            if exp_norm.get("expense_subcategory_id") and ObjectId.is_valid(str(exp_norm.get("expense_subcategory_id"))):
                subcat = await expense_categories_collection.find_one(
                    {"_id": ObjectId(exp_norm["expense_subcategory_id"])}
                )
                exp_norm["subcategory_name"] = subcat["name"] if subcat else None
            else:
                exp_norm["subcategory_name"] = None

            return exp_norm, None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def update(
        expense_id: str,
        expense_category_id: Optional[str] = None,
        expense_subcategory_id: Optional[str] = None,
        amount: Optional[float] = None,
        purpose: Optional[str] = None,
        payment_mode: Optional[str] = None,
        date: Optional[str] = None,
        attachment: Optional[UploadFile] = None
    ) -> Tuple[Optional[dict], Optional[str]]:
        try:
            if not ObjectId.is_valid(expense_id):
                return None, "Invalid expense ID"

            attachment_path = None
            file_type = None
            if attachment and attachment.filename:
                uploaded = await file_handler.upload_file(attachment, subfolder="expenses")
                attachment_path = uploaded["url"]
                file_type = attachment.content_type

            expense_update_data = ExpenseUpdate(
                expense_category_id=expense_category_id,
                expense_subcategory_id=expense_subcategory_id,
                amount=amount,
                purpose=purpose,
                payment_mode=payment_mode,
                date=date,
                file_type=file_type
            )

            update_data = {k: v for k, v in expense_update_data.dict().items() if v is not None}
            if attachment_path:
                update_data["attachment"] = attachment_path

            if update_data:
                update_data["updated_at"] = datetime.utcnow()
                result = await expenses_collection.update_one(
                    {"_id": ObjectId(expense_id), "is_deleted": {"$ne": True}},
                    {"$set": update_data}
                )
                if result.matched_count == 0:
                    return None, "Expense not found"

            return await ExpenseService.get(expense_id)
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def delete(expense_id: str) -> Tuple[bool, Optional[str]]:
        try:
            if not ObjectId.is_valid(expense_id):
                return False, "Invalid expense ID"

            result = await expenses_collection.update_one(
                {"_id": ObjectId(expense_id), "is_deleted": {"$ne": True}},
                {"$set": {"is_deleted": True, "deleted_at": datetime.utcnow()}}
            )
            if result.matched_count == 0:
                return False, "Expense not found"

            return True, None
        except Exception as e:
            traceback.print_exc()
            return False, str(e)
