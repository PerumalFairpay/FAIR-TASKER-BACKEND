from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from app.models import AssetCreate, AssetUpdate, AssetResponse, AssetAssignmentRequest
from app.crud.repository import repository
from app.helper.response_helper import success_response, error_response
from typing import List, Optional
import os
from app.helper.file_handler import file_handler

from app.auth import verify_token, require_permission

router = APIRouter(prefix="/assets", tags=["assets"], dependencies=[Depends(verify_token)])

UPLOAD_DIR = "static/assets"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/", response_model=AssetResponse, dependencies=[Depends(require_permission("asset:submit"))])
async def create_asset(
    asset_name: str = Form(...),
    asset_category_id: str = Form(...),
    asset_subcategory_id: Optional[str] = Form(None),
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
    try:
        image_paths = []
        file_type = None
        if images:
            for image in images:
                if image.filename:
                    # Use centralized file handler
                    uploaded_file = await file_handler.upload_file(image, subfolder="assets")
                    image_paths.append(uploaded_file["url"])
                    
                    # Capture content type of the first image/file
                    if not file_type:
                        file_type = image.content_type

        asset_data = AssetCreate(
            asset_name=asset_name,
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
        
        new_asset = await repository.create_asset(asset_data, image_paths)
        return success_response(
            message="Asset created successfully",
            status_code=201,
            data=new_asset
        )
    except Exception as e:
        return error_response(message=f"Failed to create asset: {str(e)}", status_code=500)

@router.get("/all", dependencies=[Depends(require_permission("asset:view"))])
async def get_assets():
    try:
        assets = await repository.get_assets()
        return success_response(
            message="Assets fetched successfully",
            data=assets
        )
    except Exception as e:
        return error_response(message=str(e), status_code=500)

@router.get("/{asset_id}", dependencies=[Depends(require_permission("asset:view"))])
async def get_asset(asset_id: str):
    try:
        asset = await repository.get_asset(asset_id)
        if not asset:
            return error_response(message="Asset not found", status_code=404)
        return success_response(
            message="Asset fetched successfully",
            data=asset
        )
    except Exception as e:
        return error_response(message=str(e), status_code=500)

@router.put("/{asset_id}", dependencies=[Depends(require_permission("asset:submit"))])
async def update_asset(
    asset_id: str,
    asset_name: Optional[str] = Form(None),
    asset_category_id: Optional[str] = Form(None),
    asset_subcategory_id: Optional[str] = Form(None),
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
    try:
        image_paths = []
        file_type = None
        if images:
            for image in images:
                if image.filename:
                    # Use centralized file handler
                    uploaded_file = await file_handler.upload_file(image, subfolder="assets")
                    image_paths.append(uploaded_file["url"])
                    
                    # Capture content type of the first image/file
                    if not file_type:
                        file_type = image.content_type

        update_data = AssetUpdate(
            asset_name=asset_name,
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
        
        updated_asset = await repository.update_asset(asset_id, update_data, image_paths if image_paths else [])
        if not updated_asset:
            return error_response(message="Asset not found", status_code=404)
        
        return success_response(
            message="Asset updated successfully",
            data=updated_asset
        )
    except Exception as e:
        return error_response(message=str(e), status_code=500)

@router.delete("/{asset_id}", dependencies=[Depends(require_permission("asset:submit"))])
async def delete_asset(asset_id: str):
    try:
        success = await repository.delete_asset(asset_id)
        if not success:
            return error_response(message="Asset not found", status_code=404)
        return success_response(message="Asset deleted successfully")
    except Exception as e:
        return error_response(message=str(e), status_code=500)


@router.put("/{asset_id}/assignment", dependencies=[Depends(require_permission("asset:submit"))])
async def manage_asset_assignment(asset_id: str, request: AssetAssignmentRequest):
    try:
        updated_asset = await repository.manage_asset_assignment(asset_id, request.employee_id)
        return success_response(
            message="Asset assignment updated successfully",
            data=updated_asset
        )
    except ValueError as e:
        return error_response(message=str(e), status_code=404)
    except Exception as e:
        return error_response(message=str(e), status_code=500)

@router.get("/employee/{employee_id}", dependencies=[Depends(require_permission("asset:view"))])
async def get_assets_by_employee(employee_id: str):
    try:
        assets = await repository.get_assets_by_employee(employee_id)
        return success_response(
            message="Employee assets fetched successfully",
            data=assets
        )
    except ValueError as e:
        return error_response(message=str(e), status_code=404)
    except Exception as e:
        return error_response(message=str(e), status_code=500)
