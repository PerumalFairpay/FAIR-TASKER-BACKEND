from fastapi import APIRouter, Depends
from app.models import DocumentCategoryCreate, DocumentCategoryUpdate
from app.services.api.document_category import DocumentCategoryService
from app.helper.response_helper import success_response, error_response
from app.auth import verify_token, require_permission

router = APIRouter(prefix="/document-categories", tags=["document-categories"], dependencies=[Depends(verify_token)])


@router.post("/create", dependencies=[Depends(require_permission("document:submit"))])
async def create_document_category(category: DocumentCategoryCreate):
    data, error = await DocumentCategoryService.create(category)
    if error:
        return error_response(message=f"Failed to create document category: {error}", status_code=500)
    return success_response(message="Document category created successfully", data=data, status_code=201)


@router.get("/all", dependencies=[Depends(require_permission("document:view"))])
async def get_document_categories():
    data, error = await DocumentCategoryService.list()
    if error:
        return error_response(message=f"Failed to fetch document categories: {error}", status_code=500)
    return success_response(message="Document categories fetched successfully", data=data)


@router.get("/{category_id}", dependencies=[Depends(require_permission("document:view"))])
async def get_document_category(category_id: str):
    data, error = await DocumentCategoryService.get(category_id)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(message="Document category fetched successfully", data=data)


@router.put("/update/{category_id}", dependencies=[Depends(require_permission("document:submit"))])
async def update_document_category(category_id: str, category: DocumentCategoryUpdate):
    data, error = await DocumentCategoryService.update(category_id, category)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(message="Document category updated successfully", data=data)


@router.delete("/delete/{category_id}", dependencies=[Depends(require_permission("document:submit"))])
async def delete_document_category(category_id: str):
    success, error = await DocumentCategoryService.delete(category_id)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(message="Document category deleted successfully", data=[])
