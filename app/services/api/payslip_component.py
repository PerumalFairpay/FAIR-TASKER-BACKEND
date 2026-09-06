from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from bson import ObjectId
from app.database import payslip_components_collection
from app.models import PayslipComponentCreate, PayslipComponentUpdate
from app.utils import normalize
import traceback


class PayslipComponentService:

    @staticmethod
    async def create(component_in: PayslipComponentCreate) -> Tuple[Optional[dict], Optional[str]]:
        try:
            data = component_in.dict()
            data["is_deleted"] = False
            data["deleted_at"] = None
            data["created_at"] = datetime.utcnow()
            result = await payslip_components_collection.insert_one(data)
            data["id"] = str(result.inserted_id)
            return normalize(data), None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def list(type: Optional[str] = None, is_active: Optional[bool] = None) -> Tuple[Optional[List[dict]], Optional[str]]:
        try:
            query = {"is_deleted": {"$ne": True}}
            if type:
                query["type"] = type
            if is_active is not None:
                query["is_active"] = is_active

            components = await payslip_components_collection.find(query).to_list(length=None)
            return [normalize(c) for c in components], None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def get(component_id: str) -> Tuple[Optional[dict], Optional[str]]:
        try:
            if not ObjectId.is_valid(component_id):
                return None, "Invalid payslip component ID"

            component = await payslip_components_collection.find_one({
                "_id": ObjectId(component_id),
                "is_deleted": {"$ne": True}
            })
            if not component:
                return None, "Payslip component not found"

            return normalize(component), None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def update(component_id: str, component_in: PayslipComponentUpdate) -> Tuple[Optional[dict], Optional[str]]:
        try:
            if not ObjectId.is_valid(component_id):
                return None, "Invalid payslip component ID"

            update_data = {k: v for k, v in component_in.dict().items() if v is not None}
            if update_data:
                update_data["updated_at"] = datetime.utcnow()
                result = await payslip_components_collection.update_one(
                    {"_id": ObjectId(component_id), "is_deleted": {"$ne": True}},
                    {"$set": update_data}
                )
                if result.matched_count == 0:
                    return None, "Payslip component not found"

            return await PayslipComponentService.get(component_id)
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def delete(component_id: str) -> Tuple[bool, Optional[str]]:
        try:
            if not ObjectId.is_valid(component_id):
                return False, "Invalid payslip component ID"

            result = await payslip_components_collection.update_one(
                {"_id": ObjectId(component_id), "is_deleted": {"$ne": True}},
                {"$set": {"is_deleted": True, "deleted_at": datetime.utcnow()}}
            )
            if result.matched_count == 0:
                return False, "Payslip component not found"

            return True, None
        except Exception as e:
            traceback.print_exc()
            return False, str(e)
