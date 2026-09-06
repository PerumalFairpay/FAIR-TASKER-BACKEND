from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from bson import ObjectId
from fastapi import UploadFile
from app.database import clients_collection
from app.models import ClientCreate, ClientUpdate
from app.helper.file_handler import file_handler
from app.utils import normalize
import traceback


class ClientService:

    @staticmethod
    async def create(
        company_name: str,
        contact_name: str,
        contact_email: str,
        contact_mobile: str,
        contact_person_designation: Optional[str] = None,
        contact_address: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[str] = "Active",
        logo: Optional[UploadFile] = None
    ) -> Tuple[Optional[dict], Optional[str]]:
        try:
            logo_path = None
            if logo and logo.filename:
                uploaded = await file_handler.upload_file(logo, subfolder="clients")
                logo_path = uploaded["url"]

            client_data = ClientCreate(
                company_name=company_name,
                contact_name=contact_name,
                contact_email=contact_email,
                contact_mobile=contact_mobile,
                contact_person_designation=contact_person_designation,
                contact_address=contact_address,
                description=description,
                status=status
            )

            data = client_data.dict()
            if logo_path:
                data["logo"] = logo_path

            data["is_deleted"] = False
            data["deleted_at"] = None
            data["created_at"] = datetime.utcnow()

            result = await clients_collection.insert_one(data)
            data["id"] = str(result.inserted_id)

            return normalize(data), None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def list() -> Tuple[Optional[List[dict]], Optional[str]]:
        try:
            clients = await clients_collection.find(
                {"is_deleted": {"$ne": True}}
            ).to_list(length=None)
            return [normalize(c) for c in clients], None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def get(client_id: str) -> Tuple[Optional[dict], Optional[str]]:
        try:
            if not ObjectId.is_valid(client_id):
                return None, "Invalid client ID"

            client = await clients_collection.find_one({
                "_id": ObjectId(client_id),
                "is_deleted": {"$ne": True}
            })
            if not client:
                return None, "Client not found"

            return normalize(client), None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def update(
        client_id: str,
        company_name: Optional[str] = None,
        contact_name: Optional[str] = None,
        contact_email: Optional[str] = None,
        contact_mobile: Optional[str] = None,
        contact_person_designation: Optional[str] = None,
        contact_address: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[str] = None,
        logo: Optional[UploadFile] = None
    ) -> Tuple[Optional[dict], Optional[str]]:
        try:
            if not ObjectId.is_valid(client_id):
                return None, "Invalid client ID"

            logo_path = None
            if logo and logo.filename:
                uploaded = await file_handler.upload_file(logo, subfolder="clients")
                logo_path = uploaded["url"]

            client_update_data = ClientUpdate(
                company_name=company_name,
                contact_name=contact_name,
                contact_email=contact_email,
                contact_mobile=contact_mobile,
                contact_person_designation=contact_person_designation,
                contact_address=contact_address,
                description=description,
                status=status
            )

            update_data = {k: v for k, v in client_update_data.dict().items() if v is not None}
            if logo_path:
                update_data["logo"] = logo_path

            if update_data:
                update_data["updated_at"] = datetime.utcnow()
                result = await clients_collection.update_one(
                    {"_id": ObjectId(client_id), "is_deleted": {"$ne": True}},
                    {"$set": update_data}
                )
                if result.matched_count == 0:
                    return None, "Client not found"

            return await ClientService.get(client_id)
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def delete(client_id: str) -> Tuple[bool, Optional[str]]:
        try:
            if not ObjectId.is_valid(client_id):
                return False, "Invalid client ID"

            result = await clients_collection.update_one(
                {"_id": ObjectId(client_id), "is_deleted": {"$ne": True}},
                {"$set": {"is_deleted": True, "deleted_at": datetime.utcnow()}}
            )
            if result.matched_count == 0:
                return False, "Client not found"

            return True, None
        except Exception as e:
            traceback.print_exc()
            return False, str(e)
