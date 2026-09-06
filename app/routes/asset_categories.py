from fastapi import APIRouter, Depends
from app.models import AssetCategoryCreate, AssetCategoryUpdate
from app.services.api.asset_category import AssetCategoryService
from app.helper.response_helper import success_response, error_response
from app.auth import verify_token, require_permission

router = APIRouter(prefix="/asset-categories", tags=["asset-categories"], dependencies=[Depends(verify_token)])


@router.post("/", dependencies=[Depends(require_permission("asset:submit"))])
async def create_asset_category(category: AssetCategoryCreate):
    data, error = await AssetCategoryService.create(category)
    if error:
        return error_response(message=f"Failed to create asset category: {error}", status_code=500)
    return success_response(message="Asset category created successfully", data=data, status_code=201)


@router.get("/all", dependencies=[Depends(require_permission("asset:view"))])
async def get_asset_categories():
    data, error = await AssetCategoryService.list()
    if error:
        return error_response(message=f"Failed to fetch asset categories: {error}", status_code=500)
    return success_response(message="Asset categories fetched successfully", data=data)


@router.get("/{category_id}", dependencies=[Depends(require_permission("asset:view"))])
async def get_asset_category(category_id: str):
    data, error = await AssetCategoryService.get(category_id)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(message="Asset category fetched successfully", data=data)


@router.put("/{category_id}", dependencies=[Depends(require_permission("asset:submit"))])
async def update_asset_category(category_id: str, category: AssetCategoryUpdate):
    data, error = await AssetCategoryService.update(category_id, category)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(message="Asset category updated successfully", data=data)


@router.delete("/{category_id}", dependencies=[Depends(require_permission("asset:submit"))])
async def delete_asset_category(category_id: str):
    success, error = await AssetCategoryService.delete(category_id)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(message="Asset category deleted successfully", data=[])
