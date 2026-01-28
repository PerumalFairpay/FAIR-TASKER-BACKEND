from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import JSONResponse
from app.crud.repository import repository as repo
from app.models import DocumentCreate, DocumentUpdate
from app.helper.file_handler import file_handler
from typing import List, Optional
import json

from app.auth import verify_token, require_permission

router = APIRouter(prefix="/documents", tags=["documents"], dependencies=[Depends(verify_token)])

@router.post("/create", dependencies=[Depends(require_permission("document:submit"))])
async def create_document(
    name: str = Form(...),
    document_category_id: str = Form(...),
    description: Optional[str] = Form(None),
    expiry_date: Optional[str] = Form(None),
    status: Optional[str] = Form("Active"),
    file: UploadFile = File(None)
):
    try:
        file_path = None
        file_type = None
        if file:
            uploaded = await file_handler.upload_file(file)
            file_path = uploaded["url"]
            file_type = file.content_type

        document_data = DocumentCreate(
            name=name,
            document_category_id=document_category_id,
            description=description,
            expiry_date=expiry_date,
            status=status,
            file_type=file_type
        )

        new_document = await repo.create_document(document_data, file_path)
        return JSONResponse(
            status_code=201,
            content={"message": "Document created successfully", "success": True, "data": new_document}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to create document: {str(e)}", "success": False}
        )

@router.get("/all", dependencies=[Depends(require_permission("document:view"))])
async def get_documents():
    try:
        documents = await repo.get_documents()
        return JSONResponse(
            status_code=200,
            content={"message": "Documents fetched successfully", "success": True, "data": documents}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to fetch documents: {str(e)}", "success": False}
        )

@router.get("/{document_id}", dependencies=[Depends(require_permission("document:view"))])
async def get_document(document_id: str):
    try:
        document = await repo.get_document(document_id)
        if not document:
            return JSONResponse(
                status_code=404,
                content={"message": "Document not found", "success": False}
            )
        return JSONResponse(
            status_code=200,
            content={"message": "Document fetched successfully", "success": True, "data": document}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to fetch document: {str(e)}", "success": False}
        )

@router.put("/update/{document_id}", dependencies=[Depends(require_permission("document:submit"))])
async def update_document(
    document_id: str,
    name: Optional[str] = Form(None),
    document_category_id: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    expiry_date: Optional[str] = Form(None),
    status: Optional[str] = Form(None),
    file: UploadFile = File(None)
):
    try:
        file_path = None
        file_type = None
        if file:
            uploaded = await file_handler.upload_file(file)
            file_path = uploaded["url"]
            file_type = file.content_type

        document_update_data = DocumentUpdate(
            name=name,
            document_category_id=document_category_id,
            description=description,
            expiry_date=expiry_date,
            status=status,
            file_type=file_type
        )

        updated_document = await repo.update_document(document_id, document_update_data, file_path)
        if not updated_document:
            return JSONResponse(
                status_code=404,
                content={"message": "Document not found", "success": False}
            )
        return JSONResponse(
            status_code=200,
            content={"message": "Document updated successfully", "success": True, "data": updated_document}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to update document: {str(e)}", "success": False}
        )

@router.delete("/delete/{document_id}", dependencies=[Depends(require_permission("document:submit"))])
async def delete_document(document_id: str):
    try:
        success = await repo.delete_document(document_id)
        if not success:
            return JSONResponse(
                status_code=404,
                content={"message": "Document not found", "success": False}
            )
        return JSONResponse(
            status_code=200,
            content={"message": "Document deleted successfully", "success": True}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to delete document: {str(e)}", "success": False}
        )
