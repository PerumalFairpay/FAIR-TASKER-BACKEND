from fastapi import APIRouter, HTTPException, Depends
from app.models import AssetCategoryCreate, AssetCategoryUpdate, AssetCategoryResponse
from app.crud.repository import repository
from typing import List

from app.auth import verify_token, require_permission

router = APIRouter(prefix="/asset-categories", tags=["asset-categories"], dependencies=[Depends(verify_token)])

@router.post("/", response_model=AssetCategoryResponse, dependencies=[Depends(require_permission("asset:submit"))])
async def create_asset_category(category: AssetCategoryCreate):
    return await repository.create_asset_category(category)

@router.get("/all", response_model=List[AssetCategoryResponse], dependencies=[Depends(require_permission("asset:view"))])
async def get_asset_categories():
    return await repository.get_asset_categories()

@router.get("/{category_id}", response_model=AssetCategoryResponse, dependencies=[Depends(require_permission("asset:view"))])
async def get_asset_category(category_id: str):
    category = await repository.get_asset_category(category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Asset category not found")
    return category

@router.put("/{category_id}", response_model=AssetCategoryResponse, dependencies=[Depends(require_permission("asset:submit"))])
async def update_asset_category(category_id: str, category: AssetCategoryUpdate):
    updated_category = await repository.update_asset_category(category_id, category)
    if not updated_category:
        raise HTTPException(status_code=404, detail="Asset category not found")
    return updated_category

@router.delete("/{category_id}", dependencies=[Depends(require_permission("asset:submit"))])
async def delete_asset_category(category_id: str):
    success = await repository.delete_asset_category(category_id)
    if not success:
        raise HTTPException(status_code=404, detail="Asset category not found")
    return {"message": "Asset category deleted successfully"}
