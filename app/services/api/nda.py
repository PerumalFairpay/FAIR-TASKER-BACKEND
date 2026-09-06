from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
import uuid
from bson import ObjectId
from app.database import nda_requests_collection
from app.models import NDARequestCreate, NDARegenerateRequest, NDARequestUpdate
from app.utils import normalize
import traceback


class NDAService:

    @staticmethod
    def format_nda_response(nda: dict) -> dict:
        if not nda:
            return nda

        result = {k: v for k, v in nda.items() if k not in (
            "perma_door_no", "perma_care_of_type", "perma_care_of_name",
            "perma_street", "perma_city", "perma_state", "perma_pincode",
            "res_door_no", "res_care_of_type", "res_care_of_name",
            "res_street", "res_city", "res_state", "res_pincode",
        )}

        result["address"] = {
            "permanent_address": nda.get("address"),
            "perma_door_no": nda.get("perma_door_no"),
            "perma_care_of_type": nda.get("perma_care_of_type"),
            "perma_care_of_name": nda.get("perma_care_of_name"),
            "perma_street": nda.get("perma_street"),
            "perma_city": nda.get("perma_city"),
            "perma_state": nda.get("perma_state"),
            "perma_pincode": nda.get("perma_pincode"),
        }

        result["residential_address"] = {
            "residential_address": nda.get("residential_address"),
            "res_door_no": nda.get("res_door_no"),
            "res_care_of_type": nda.get("res_care_of_type"),
            "res_care_of_name": nda.get("res_care_of_name"),
            "res_street": nda.get("res_street"),
            "res_city": nda.get("res_city"),
            "res_state": nda.get("res_state"),
            "res_pincode": nda.get("res_pincode"),
        }

        return result

    @staticmethod
    async def create(nda_request: NDARequestCreate) -> Tuple[Optional[dict], Optional[str], Optional[str]]:
        """Returns (nda_data, token, error)"""
        try:
            existing_nda = await nda_requests_collection.find_one({
                "email": nda_request.email,
                "is_deleted": {"$ne": True}
            })
            if existing_nda:
                return None, None, f"NDA request already exists for email {nda_request.email}"

            token = str(uuid.uuid4())
            expiry_hours = nda_request.expires_in_hours if nda_request.expires_in_hours else 1
            expires_at = datetime.utcnow() + timedelta(hours=expiry_hours)

            nda_data = nda_request.dict()
            nda_data["token"] = token
            nda_data["status"] = "Pending"
            nda_data["expires_at"] = expires_at
            nda_data["created_at"] = datetime.utcnow()
            nda_data["documents"] = []
            nda_data["signature"] = None
            nda_data["is_deleted"] = False
            nda_data["deleted_at"] = None

            result = await nda_requests_collection.insert_one(nda_data)
            nda_data["id"] = str(result.inserted_id)

            return normalize(nda_data), token, None
        except Exception as e:
            traceback.print_exc()
            return None, None, str(e)

    @staticmethod
    async def regenerate_token(nda_id: str, request_in: NDARegenerateRequest) -> Tuple[Optional[dict], Optional[str], Optional[str]]:
        """Returns (updated_nda, new_token, error)"""
        try:
            if not ObjectId.is_valid(nda_id):
                return None, None, "Invalid NDA request ID"

            existing = await nda_requests_collection.find_one({"_id": ObjectId(nda_id), "is_deleted": {"$ne": True}})
            if not existing:
                return None, None, "NDA request not found"

            new_token = str(uuid.uuid4())
            expiry_hours = request_in.expires_in_hours if request_in.expires_in_hours else 1
            expires_at = datetime.utcnow() + timedelta(hours=expiry_hours)

            update_data = {k: v for k, v in request_in.dict().items() if v is not None and k != "expires_in_hours"}
            update_data["token"] = new_token
            update_data["expires_at"] = expires_at
            update_data["status"] = "Pending"
            update_data["updated_at"] = datetime.utcnow()
            update_data["documents"] = []
            update_data["signature"] = None
            update_data["signed_pdf_path"] = None

            await nda_requests_collection.update_one(
                {"_id": ObjectId(nda_id)},
                {"$set": update_data}
            )

            updated_doc = await nda_requests_collection.find_one({"_id": ObjectId(nda_id)})
            return normalize(updated_doc), new_token, None
        except Exception as e:
            traceback.print_exc()
            return None, None, str(e)

    @staticmethod
    async def list(
        page: int = 1,
        limit: int = 10,
        search: Optional[str] = None,
        status: Optional[str] = None
    ) -> Tuple[Optional[List[dict]], int, Optional[str]]:
        try:
            query = {"is_deleted": {"$ne": True}}
            if status and status != "All":
                query["status"] = status

            if search:
                regex_pattern = {"$regex": search, "$options": "i"}
                query["$or"] = [
                    {"first_name": regex_pattern},
                    {"last_name": regex_pattern},
                    {"email": regex_pattern},
                    {"token": regex_pattern},
                ]

            skip = (page - 1) * limit
            total_items = await nda_requests_collection.count_documents(query)

            nda_cursor = (
                await nda_requests_collection.find(query)
                .sort("created_at", -1)
                .skip(skip)
                .limit(limit)
                .to_list(length=limit)
            )

            normalized_requests = []
            for req in nda_cursor:
                if "first_name" not in req and "employee_name" in req:
                    parts = req["employee_name"].split(" ", 1)
                    req["first_name"] = parts[0]
                    req["last_name"] = parts[1] if len(parts) > 1 else ""
                normalized_requests.append(normalize(req))

            return normalized_requests, total_items, None
        except Exception as e:
            traceback.print_exc()
            return None, 0, str(e)

    @staticmethod
    async def get_approved() -> Tuple[Optional[List[dict]], Optional[str]]:
        try:
            query = {"status": "Approved", "is_deleted": {"$ne": True}}
            projection = {
                "first_name": 1,
                "last_name": 1,
                "email": 1,
                "mobile": 1,
                "address": 1,
                "residential_address": 1,
                "designation": 1,
                "department": 1,
                "status": 1,
                "documents": 1,
                "signed_pdf_path": 1
            }
            cursor = nda_requests_collection.find(query, projection).sort("created_at", -1)
            results = await cursor.to_list(length=None)
            return [normalize(res) for res in results], None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def get_by_token(token: str) -> Tuple[Optional[dict], Optional[str]]:
        try:
            nda_request = await nda_requests_collection.find_one({"token": token, "is_deleted": {"$ne": True}})
            if not nda_request:
                return None, "NDA request not found"

            if "first_name" not in nda_request and "employee_name" in nda_request:
                parts = nda_request["employee_name"].split(" ", 1)
                nda_request["first_name"] = parts[0]
                nda_request["last_name"] = parts[1] if len(parts) > 1 else ""

            return normalize(nda_request), None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def update_by_token(token: str, update_data: dict) -> Tuple[Optional[dict], Optional[str]]:
        try:
            if update_data:
                update_data["updated_at"] = datetime.utcnow()
                await nda_requests_collection.update_one(
                    {"token": token}, {"$set": update_data}
                )
            return await NDAService.get_by_token(token)
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def update_status_by_id(nda_id: str, status: str, rejection_reason: Optional[str] = None) -> Tuple[Optional[dict], Optional[str]]:
        try:
            if not ObjectId.is_valid(nda_id):
                return None, "Invalid NDA request ID"

            update_data = {
                "status": status,
                "rejection_reason": rejection_reason,
                "updated_at": datetime.utcnow()
            }
            await nda_requests_collection.update_one(
                {"_id": ObjectId(nda_id)}, {"$set": update_data}
            )
            updated_doc = await nda_requests_collection.find_one({"_id": ObjectId(nda_id)})
            if not updated_doc:
                return None, "NDA request not found"

            return normalize(updated_doc), None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def delete(nda_id: str) -> Tuple[bool, Optional[str]]:
        try:
            if not ObjectId.is_valid(nda_id):
                return False, "Invalid NDA request ID"

            result = await nda_requests_collection.update_one(
                {"_id": ObjectId(nda_id), "is_deleted": {"$ne": True}},
                {"$set": {"is_deleted": True, "deleted_at": datetime.utcnow()}}
            )
            if result.matched_count == 0:
                return False, "NDA request not found"

            return True, None
        except Exception as e:
            traceback.print_exc()
            return False, str(e)
