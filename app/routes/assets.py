from fastapi import APIRouter, Depends, UploadFile, File, Form
from app.models import AssetAssignmentRequest
from app.services.api.asset import AssetService
from app.helper.response_helper import success_response, error_response
from typing import List, Optional
from app.auth import verify_token, require_permission

router = APIRouter(prefix="/assets", tags=["assets"], dependencies=[Depends(verify_token)])


@router.post("/", dependencies=[Depends(require_permission("asset:submit"))])
async def create_asset(
    asset_name: str = Form(...),
    asset_unique_id: str = Form(...),
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
    data, error = await AssetService.create(
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
        images=images
    )
    if error:
        status_code = 400 if "already in use" in error.lower() else 500
        return error_response(message=f"Failed to create asset: {error}", status_code=status_code)
    return success_response(message="Asset created successfully", data=data, status_code=201)


@router.get("/all", dependencies=[Depends(require_permission("asset:view"))])
async def get_assets():
    data, error = await AssetService.list()
    if error:
        return error_response(message=f"Failed to fetch assets: {error}", status_code=500)
    return success_response(message="Assets fetched successfully", data=data)


@router.get("/{asset_id}", dependencies=[Depends(require_permission("asset:view"))])
async def get_asset(asset_id: str):
    data, error = await AssetService.get(asset_id)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(message="Asset fetched successfully", data=data)


@router.put("/{asset_id}", dependencies=[Depends(require_permission("asset:submit"))])
async def update_asset(
    asset_id: str,
    asset_name: Optional[str] = Form(None),
    asset_unique_id: Optional[str] = Form(None),
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
    data, error = await AssetService.update(
        asset_id=asset_id,
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
        images=images
    )
    if error:
        if "not found" in error.lower() or "invalid" in error.lower():
            status_code = 404
        elif "already in use" in error.lower():
            status_code = 400
        else:
            status_code = 500
        return error_response(message=error, status_code=status_code)
    return success_response(message="Asset updated successfully", data=data)


@router.delete("/{asset_id}", dependencies=[Depends(require_permission("asset:submit"))])
async def delete_asset(asset_id: str):
    success, error = await AssetService.delete(asset_id)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(message="Asset deleted successfully", data=[])


@router.put("/{asset_id}/assignment", dependencies=[Depends(require_permission("asset:submit"))])
async def manage_asset_assignment(asset_id: str, request: AssetAssignmentRequest):
    data, error = await AssetService.manage_assignment(asset_id, request.employee_id)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(message="Asset assignment updated successfully", data=data)


@router.get("/employee/{employee_id}", dependencies=[Depends(require_permission("asset:view"))])
async def get_assets_by_employee(employee_id: str):
    data, error = await AssetService.get_by_employee(employee_id)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(message="Employee assets fetched successfully", data=data)
