import asyncio
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from bson import ObjectId
from fastapi import UploadFile
from app.database import documents_collection
from app.models import DocumentCreate, DocumentUpdate
from app.helper.file_handler import file_handler
from app.services.vector_store import vector_store_service
from app.utils import normalize
import traceback


class DocumentService:

    @staticmethod
    async def create(
        name: str,
        document_category_id: str,
        document_subcategory_id: Optional[str] = None,
        description: Optional[str] = None,
        expiry_date: Optional[str] = None,
        status: Optional[str] = "Active",
        file: Optional[UploadFile] = None
    ) -> Tuple[Optional[dict], Optional[str]]:
        try:
            file_path = None
            file_type = None
            if file and file.filename:
                uploaded = await file_handler.upload_file(file, subfolder="documents")
                file_path = uploaded["url"]
                file_type = file.content_type

            document_data = DocumentCreate(
                name=name,
                document_category_id=document_category_id,
                document_subcategory_id=document_subcategory_id,
                description=description,
                expiry_date=expiry_date,
                status=status,
                file_type=file_type
            )

            data = document_data.dict()
            if file_path:
                data["file_path"] = file_path

            data["is_deleted"] = False
            data["deleted_at"] = None
            data["created_at"] = datetime.utcnow()
            result = await documents_collection.insert_one(data)
            data["id"] = str(result.inserted_id)

            # Index document in vector store for AI analysis
            if file_path:
                asyncio.create_task(
                    vector_store_service.index_document(
                        file_url=file_path,
                        metadata={
                            "document_id": data["id"],
                            "name": data["name"],
                            "category_id": data.get("document_category_id"),
                        },
                        file_type=data.get("file_type")
                    )
                )

            return normalize(data), None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def list(
        status: Optional[str] = None,
        search: Optional[str] = None
    ) -> Tuple[Optional[List[dict]], Optional[str]]:
        try:
            query = {"is_deleted": {"$ne": True}}
            if status:
                query["status"] = status
            if search:
                query["name"] = {"$regex": search, "$options": "i"}

            documents = await documents_collection.find(query).to_list(length=None)
            return [normalize(doc) for doc in documents], None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def get(document_id: str) -> Tuple[Optional[dict], Optional[str]]:
        try:
            if not ObjectId.is_valid(document_id):
                return None, "Invalid document ID"

            document = await documents_collection.find_one({
                "_id": ObjectId(document_id),
                "is_deleted": {"$ne": True}
            })
            if not document:
                return None, "Document not found"

            return normalize(document), None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def update(
        document_id: str,
        name: Optional[str] = None,
        document_category_id: Optional[str] = None,
        document_subcategory_id: Optional[str] = None,
        description: Optional[str] = None,
        expiry_date: Optional[str] = None,
        status: Optional[str] = None,
        file: Optional[UploadFile] = None
    ) -> Tuple[Optional[dict], Optional[str]]:
        try:
            if not ObjectId.is_valid(document_id):
                return None, "Invalid document ID"

            file_path = None
            file_type = None
            if file and file.filename:
                uploaded = await file_handler.upload_file(file, subfolder="documents")
                file_path = uploaded["url"]
                file_type = file.content_type

            document_update_data = DocumentUpdate(
                name=name,
                document_category_id=document_category_id,
                document_subcategory_id=document_subcategory_id,
                description=description,
                expiry_date=expiry_date,
                status=status,
                file_type=file_type
            )

            update_data = {k: v for k, v in document_update_data.dict().items() if v is not None}
            if file_path:
                update_data["file_path"] = file_path

            if update_data:
                update_data["updated_at"] = datetime.utcnow()
                result = await documents_collection.update_one(
                    {"_id": ObjectId(document_id), "is_deleted": {"$ne": True}},
                    {"$set": update_data}
                )
                if result.matched_count == 0:
                    return None, "Document not found"

                # Re-index if file changed
                if file_path:
                    # Clean up old vectors first
                    asyncio.create_task(vector_store_service.delete_document(document_id))
                    # Index new content
                    asyncio.create_task(
                        vector_store_service.index_document(
                            file_url=file_path,
                            metadata={
                                "document_id": document_id,
                                "name": update_data.get("name") or name,
                                "category_id": update_data.get("document_category_id") or document_category_id,
                            },
                            file_type=update_data.get("file_type") or file_type
                        )
                    )

            return await DocumentService.get(document_id)
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def update_status(document_id: str, status: str) -> Tuple[Optional[dict], Optional[str]]:
        try:
            if not ObjectId.is_valid(document_id):
                return None, "Invalid document ID"

            result = await documents_collection.update_one(
                {"_id": ObjectId(document_id), "is_deleted": {"$ne": True}},
                {"$set": {"status": status, "updated_at": datetime.utcnow()}}
            )
            if result.matched_count == 0:
                return None, "Document not found"

            return await DocumentService.get(document_id)
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def delete(document_id: str) -> Tuple[bool, Optional[str]]:
        try:
            if not ObjectId.is_valid(document_id):
                return False, "Invalid document ID"

            result = await documents_collection.update_one(
                {"_id": ObjectId(document_id), "is_deleted": {"$ne": True}},
                {"$set": {"is_deleted": True, "deleted_at": datetime.utcnow()}}
            )

            if result.matched_count == 0:
                return False, "Document not found"

            # Clean up vectors
            asyncio.create_task(vector_store_service.delete_document(document_id))

            return True, None
        except Exception as e:
            traceback.print_exc()
            return False, str(e)
