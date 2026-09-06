from fastapi import APIRouter, Depends, UploadFile, File, Form
from app.models import DocumentStatusUpdate
from app.services.api.document import DocumentService
from app.helper.response_helper import success_response, error_response
from app.auth import verify_token, require_permission
from typing import Optional

router = APIRouter(prefix="/documents", tags=["documents"], dependencies=[Depends(verify_token)])

@router.post("/create", dependencies=[Depends(require_permission("document:submit"))])
async def create_document(
    name: str = Form(...),
    document_category_id: str = Form(...),
    document_subcategory_id: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    expiry_date: Optional[str] = Form(None),
    status: Optional[str] = Form("Active"),
    file: Optional[UploadFile] = File(None)
):
    data, error = await DocumentService.create(
        name=name,
        document_category_id=document_category_id,
        document_subcategory_id=document_subcategory_id,
        description=description,
        expiry_date=expiry_date,
        status=status,
        file=file
    )
    if error:
        return error_response(message=f"Failed to create document: {error}", status_code=500)
    return success_response(message="Document created successfully", data=data, status_code=201)

@router.get("/all", dependencies=[Depends(require_permission("document:view"))])
async def get_documents(
    status: Optional[str] = None,
    search: Optional[str] = None
):
    data, error = await DocumentService.list(status=status, search=search)
    if error:
        return error_response(message=f"Failed to fetch documents: {error}", status_code=500)
    return success_response(message="Documents fetched successfully", data=data)

@router.get("/{document_id}", dependencies=[Depends(require_permission("document:view"))])
async def get_document(document_id: str):
    data, error = await DocumentService.get(document_id)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(message="Document fetched successfully", data=data)

@router.put("/update/{document_id}", dependencies=[Depends(require_permission("document:submit"))])
async def update_document(
    document_id: str,
    name: Optional[str] = Form(None),
    document_category_id: Optional[str] = Form(None),
    document_subcategory_id: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    expiry_date: Optional[str] = Form(None),
    status: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None)
):
    data, error = await DocumentService.update(
        document_id=document_id,
        name=name,
        document_category_id=document_category_id,
        document_subcategory_id=document_subcategory_id,
        description=description,
        expiry_date=expiry_date,
        status=status,
        file=file
    )
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(message="Document updated successfully", data=data)

@router.patch("/update-status/{document_id}", dependencies=[Depends(require_permission("document:submit"))])
async def update_document_status(document_id: str, status_data: DocumentStatusUpdate):
    data, error = await DocumentService.update_status(document_id, status_data.status)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(message="Document status updated successfully", data=data)

@router.delete("/delete/{document_id}", dependencies=[Depends(require_permission("document:submit"))])
async def delete_document(document_id: str):
    success, error = await DocumentService.delete(document_id)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(message="Document deleted successfully", data=[])
