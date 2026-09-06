from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from bson import ObjectId
from fastapi import UploadFile
from app.database import assets_collection, asset_categories_collection, employees_collection
from app.models import AssetCreate, AssetUpdate
from app.helper.file_handler import file_handler
from app.utils import normalize
import traceback


class AssetService:

    @staticmethod
    async def create(
        asset_name: str,
        asset_unique_id: str,
        asset_category_id: str,
        asset_subcategory_id: Optional[str] = None,
        manufacturer: Optional[str] = None,
        supplier: Optional[str] = None,
        purchase_from: Optional[str] = None,
        model_no: Optional[str] = None,
        serial_no: Optional[str] = None,
        purchase_date: Optional[str] = None,
        purchase_cost: Optional[float] = 0.0,
        warranty_expiry: Optional[str] = None,
        condition: Optional[str] = None,
        status: Optional[str] = "Available",
        assigned_to: Optional[str] = None,
        description: Optional[str] = None,
        images: Optional[List[UploadFile]] = None
    ) -> Tuple[Optional[dict], Optional[str]]:
        try:
            # Check unique asset id
            if asset_unique_id:
                existing = await assets_collection.find_one({
                    "asset_unique_id": asset_unique_id,
                    "is_deleted": {"$ne": True}
                })
                if existing:
                    return None, f"Asset Unique ID '{asset_unique_id}' is already in use"

            image_paths = []
            file_type = None
            if images:
                for image in images:
                    if image and image.filename:
                        uploaded_file = await file_handler.upload_file(image, subfolder="assets")
                        image_paths.append(uploaded_file["url"])
                        if not file_type:
                            file_type = image.content_type

            asset_data = AssetCreate(
                asset_name=asset_name,
                asset_unique_id=asset_unique_id,
                asset_category_id=asset_category_id,
                asset_subcategory_id=asset_subcategory_id,
                manufacturer=manufacturer,
                supplier=supplier,
                purchase_from=purchase_from,
                model_no=model_no,
                serial_no=serial_no,
                purchase_date=purchase_date,
                purchase_cost=purchase_cost,
                warranty_expiry=warranty_expiry,
                condition=condition,
                status=status,
                assigned_to=assigned_to,
                description=description,
                images=image_paths,
                file_type=file_type
            )

            data = asset_data.dict()
            if image_paths:
                data["images"] = image_paths

            data["is_deleted"] = False
            data["deleted_at"] = None
            data["created_at"] = datetime.utcnow()
            result = await assets_collection.insert_one(data)
            data["id"] = str(result.inserted_id)

            return normalize(data), None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def list() -> Tuple[Optional[List[dict]], Optional[str]]:
        try:
            assets = (
                await assets_collection.find({"is_deleted": {"$ne": True}})
                .sort("created_at", -1)
                .to_list(length=None)
            )

            categories = await asset_categories_collection.find({"is_deleted": {"$ne": True}}).to_list(length=None)
            employees = await employees_collection.find({"is_deleted": {"$ne": True}}).to_list(length=None)

            cat_map = {str(c["_id"]): normalize(c) for c in categories}
            emp_map = {str(e["_id"]): normalize(e) for e in employees}

            result = []
            for a in assets:
                a_norm = normalize(a)
                a_norm["category"] = cat_map.get(str(a_norm.get("asset_category_id")))
                a_norm["assigned_to_details"] = emp_map.get(str(a_norm.get("assigned_to")))
                result.append(a_norm)

            return result, None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def get(asset_id: str) -> Tuple[Optional[dict], Optional[str]]:
        try:
            if not ObjectId.is_valid(asset_id):
                return None, "Invalid asset ID"

            asset = await assets_collection.find_one({
                "_id": ObjectId(asset_id),
                "is_deleted": {"$ne": True}
            })
            if not asset:
                return None, "Asset not found"

            a_norm = normalize(asset)

            # Category hydration
            category_id = a_norm.get("asset_category_id")
            if category_id and ObjectId.is_valid(str(category_id)):
                category = await asset_categories_collection.find_one({"_id": ObjectId(category_id)})
                a_norm["category"] = normalize(category) if category else None
            else:
                a_norm["category"] = None

            # Employee hydration
            assigned_to = a_norm.get("assigned_to")
            if assigned_to and ObjectId.is_valid(str(assigned_to)):
                employee = await employees_collection.find_one({"_id": ObjectId(assigned_to)})
                a_norm["assigned_to_details"] = normalize(employee) if employee else None
            else:
                a_norm["assigned_to_details"] = None

            return a_norm, None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def update(
        asset_id: str,
        asset_name: Optional[str] = None,
        asset_unique_id: Optional[str] = None,
        asset_category_id: Optional[str] = None,
        asset_subcategory_id: Optional[str] = None,
        manufacturer: Optional[str] = None,
        supplier: Optional[str] = None,
        purchase_from: Optional[str] = None,
        model_no: Optional[str] = None,
        serial_no: Optional[str] = None,
        purchase_date: Optional[str] = None,
        purchase_cost: Optional[float] = None,
        warranty_expiry: Optional[str] = None,
        condition: Optional[str] = None,
        status: Optional[str] = None,
        assigned_to: Optional[str] = None,
        description: Optional[str] = None,
        images: Optional[List[UploadFile]] = None
    ) -> Tuple[Optional[dict], Optional[str]]:
        try:
            if not ObjectId.is_valid(asset_id):
                return None, "Invalid asset ID"

            image_paths = []
            file_type = None
            if images:
                for image in images:
                    if image and image.filename:
                        uploaded_file = await file_handler.upload_file(image, subfolder="assets")
                        image_paths.append(uploaded_file["url"])
                        if not file_type:
                            file_type = image.content_type

            update_data = AssetUpdate(
                asset_name=asset_name,
                asset_unique_id=asset_unique_id,
                asset_category_id=asset_category_id,
                asset_subcategory_id=asset_subcategory_id,
                manufacturer=manufacturer,
                supplier=supplier,
                purchase_from=purchase_from,
                model_no=model_no,
                serial_no=serial_no,
                purchase_date=purchase_date,
                purchase_cost=purchase_cost,
                warranty_expiry=warranty_expiry,
                condition=condition,
                status=status,
                assigned_to=assigned_to,
                description=description,
                images=image_paths if image_paths else None,
                file_type=file_type
            )

            raw_update = {k: v for k, v in update_data.dict().items() if v is not None}
            if image_paths:
                raw_update["images"] = image_paths

            if raw_update:
                if "asset_unique_id" in raw_update and raw_update["asset_unique_id"]:
                    existing = await assets_collection.find_one({
                        "asset_unique_id": raw_update["asset_unique_id"],
                        "_id": {"$ne": ObjectId(asset_id)},
                        "is_deleted": {"$ne": True}
                    })
                    if existing:
                        return None, f"Asset Unique ID '{raw_update['asset_unique_id']}' is already in use"

                raw_update["updated_at"] = datetime.utcnow()
                result = await assets_collection.update_one(
                    {"_id": ObjectId(asset_id), "is_deleted": {"$ne": True}},
                    {"$set": raw_update}
                )
                if result.matched_count == 0:
                    return None, "Asset not found"

            return await AssetService.get(asset_id)
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def delete(asset_id: str) -> Tuple[bool, Optional[str]]:
        try:
            if not ObjectId.is_valid(asset_id):
                return False, "Invalid asset ID"

            result = await assets_collection.update_one(
                {"_id": ObjectId(asset_id), "is_deleted": {"$ne": True}},
                {"$set": {"is_deleted": True, "deleted_at": datetime.utcnow()}}
            )
            if result.matched_count == 0:
                return False, "Asset not found"

            return True, None
        except Exception as e:
            traceback.print_exc()
            return False, str(e)

    @staticmethod
    async def manage_assignment(asset_id: str, employee_id: Optional[str] = None) -> Tuple[Optional[dict], Optional[str]]:
        try:
            if not ObjectId.is_valid(asset_id):
                return None, "Invalid asset ID"

            asset = await assets_collection.find_one({
                "_id": ObjectId(asset_id),
                "is_deleted": {"$ne": True}
            })
            if not asset:
                return None, "Asset not found"

            update_data = {}
            if employee_id:
                if not ObjectId.is_valid(employee_id):
                    return None, "Invalid employee ID"
                employee = await employees_collection.find_one({
                    "_id": ObjectId(employee_id),
                    "is_deleted": {"$ne": True}
                })
                if not employee:
                    return None, "Employee not found"

                update_data["assigned_to"] = employee_id
                update_data["status"] = "Assigned"
            else:
                update_data["assigned_to"] = None
                update_data["status"] = "Available"

            update_data["updated_at"] = datetime.utcnow()
            await assets_collection.update_one(
                {"_id": ObjectId(asset_id), "is_deleted": {"$ne": True}},
                {"$set": update_data}
            )

            return await AssetService.get(asset_id)
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def get_by_employee(employee_id: str) -> Tuple[Optional[List[dict]], Optional[str]]:
        try:
            if not ObjectId.is_valid(employee_id):
                return None, "Invalid employee ID"

            employee = await employees_collection.find_one({
                "_id": ObjectId(employee_id),
                "is_deleted": {"$ne": True}
            })
            if not employee:
                return None, "Employee not found"

            assets = await assets_collection.find({
                "assigned_to": employee_id,
                "is_deleted": {"$ne": True}
            }).to_list(length=None)

            categories = await asset_categories_collection.find({"is_deleted": {"$ne": True}}).to_list(length=None)
            cat_map = {str(c["_id"]): normalize(c) for c in categories}

            result = []
            for a in assets:
                a_norm = normalize(a)
                a_norm["category"] = cat_map.get(str(a_norm.get("asset_category_id")))
                result.append(a_norm)

            return result, None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)
