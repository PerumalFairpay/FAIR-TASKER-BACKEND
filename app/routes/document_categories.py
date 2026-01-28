from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from app.crud.repository import repository as repo
from app.models import DocumentCategoryCreate, DocumentCategoryUpdate
from typing import List, Optional

from app.auth import verify_token, require_permission

router = APIRouter(prefix="/document-categories", tags=["document-categories"], dependencies=[Depends(verify_token)])

@router.post("/create", dependencies=[Depends(require_permission("document:submit"))])
async def create_document_category(category: DocumentCategoryCreate):
    try:
        new_category = await repo.create_document_category(category)
        return JSONResponse(
            status_code=201,
            content={"message": "Document category created successfully", "success": True, "data": new_category}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to create document category: {str(e)}", "success": False}
        )

@router.get("/all", dependencies=[Depends(require_permission("document:view"))])
async def get_document_categories():
    try:
        categories = await repo.get_document_categories()
        return JSONResponse(
            status_code=200,
            content={"message": "Document categories fetched successfully", "success": True, "data": categories}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to fetch document categories: {str(e)}", "success": False}
        )

@router.get("/{category_id}", dependencies=[Depends(require_permission("document:view"))])
async def get_document_category(category_id: str):
    try:
        category = await repo.get_document_category(category_id)
        if not category:
            return JSONResponse(
                status_code=404,
                content={"message": "Document category not found", "success": False}
            )
        return JSONResponse(
            status_code=200,
            content={"message": "Document category fetched successfully", "success": True, "data": category}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to fetch document category: {str(e)}", "success": False}
        )

@router.put("/update/{category_id}", dependencies=[Depends(require_permission("document:submit"))])
async def update_document_category(category_id: str, category: DocumentCategoryUpdate):
    try:
        updated_category = await repo.update_document_category(category_id, category)
        if not updated_category:
            return JSONResponse(
                status_code=404,
                content={"message": "Document category not found", "success": False}
            )
        return JSONResponse(
            status_code=200,
            content={"message": "Document category updated successfully", "success": True, "data": updated_category}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to update document category: {str(e)}", "success": False}
        )

@router.delete("/delete/{category_id}", dependencies=[Depends(require_permission("document:submit"))])
async def delete_document_category(category_id: str):
    try:
        success = await repo.delete_document_category(category_id)
        if not success:
            return JSONResponse(
                status_code=404,
                content={"message": "Document category not found", "success": False}
            )
        return JSONResponse(
            status_code=200,
            content={"message": "Document category deleted successfully", "success": True}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to delete document category: {str(e)}", "success": False}
        )
