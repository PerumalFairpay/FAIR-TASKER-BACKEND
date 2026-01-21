from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from app.models import AssetCreate, AssetUpdate, AssetResponse, AssetAssignmentRequest
from app.crud.repository import repository
from typing import List, Optional
import os
import shutil
import uuid
from app.helper.file_handler import file_handler

from app.auth import verify_token

router = APIRouter(prefix="/assets", tags=["assets"], dependencies=[Depends(verify_token)])

UPLOAD_DIR = "static/assets"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/", response_model=AssetResponse)
async def create_asset(
    asset_name: str = Form(...),
    asset_category_id: str = Form(...),
    manufacturer: Optional[str] = Form(None),
    supplier: Optional[str] = Form(None),
    purchase_from: Optional[str] = Form(None),
    model_no: Optional[str] = Form(None),
    serial_no: Optional[str] = Form(None),
    purchase_date: Optional[str] = Form(None),
    purchase_cost: Optional[float] = Form(0.0),
    warranty_expiry: Optional[str] = Form(None),
    condition: Optional[str] = Form(None),
    status: Optional[str] = Form("Available"),
    assigned_to: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    images: List[UploadFile] = File(None)
):
    image_paths = []
    file_type = None
    if images:
        for image in images:
            if image.filename:
                # Use centralized file handler
                uploaded_file = await file_handler.upload_file(image)
                image_paths.append(uploaded_file["url"])
                
                # Capture content type of the first image/file
                if not file_type:
                    file_type = image.content_type

    asset_data = AssetCreate(
        asset_name=asset_name,
        asset_category_id=asset_category_id,
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
    
    return await repository.create_asset(asset_data, image_paths)

@router.get("/all")
async def get_assets():
    return await repository.get_assets()

@router.get("/{asset_id}")
async def get_asset(asset_id: str):
    asset = await repository.get_asset(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset

@router.put("/{asset_id}")
async def update_asset(
    asset_id: str,
    asset_name: Optional[str] = Form(None),
    asset_category_id: Optional[str] = Form(None),
    manufacturer: Optional[str] = Form(None),
    supplier: Optional[str] = Form(None),
    purchase_from: Optional[str] = Form(None),
    model_no: Optional[str] = Form(None),
    serial_no: Optional[str] = Form(None),
    purchase_date: Optional[str] = Form(None),
    purchase_cost: Optional[float] = Form(None),
    warranty_expiry: Optional[str] = Form(None),
    condition: Optional[str] = Form(None),
    status: Optional[str] = Form(None),
    assigned_to: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    images: List[UploadFile] = File(None)
):
    image_paths = []
    file_type = None
    if images:
        for image in images:
            if image.filename:
                # Use centralized file handler
                uploaded_file = await file_handler.upload_file(image)
                image_paths.append(uploaded_file["url"])
                
                # Capture content type of the first image/file
                if not file_type:
                    file_type = image.content_type

    update_data = AssetUpdate(
        asset_name=asset_name,
        asset_category_id=asset_category_id,
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
    
    updated_asset = await repository.update_asset(asset_id, update_data, image_paths if image_paths else [])
    if not updated_asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return updated_asset

@router.delete("/{asset_id}")
async def delete_asset(asset_id: str):
    success = await repository.delete_asset(asset_id)
    if not success:
        raise HTTPException(status_code=404, detail="Asset not found")
    return {"message": "Asset deleted successfully"}


@router.put("/{asset_id}/assignment")
async def manage_asset_assignment(asset_id: str, request: AssetAssignmentRequest):
    try:
        updated_asset = await repository.manage_asset_assignment(asset_id, request.employee_id)
        return updated_asset
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/employee/{employee_id}")
async def get_assets_by_employee(employee_id: str):
    try:
        assets = await repository.get_assets_by_employee(employee_id)
        return assets
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
