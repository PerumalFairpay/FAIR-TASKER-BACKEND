from pydantic import BaseModel, Field
from typing import Optional, List, Any, Dict
from datetime import datetime

class AssetCategoryBase(BaseModel):
    name: str
    description: Optional[str] = None
    parent_id: Optional[Union[str, int]] = None

class AssetCategoryCreate(AssetCategoryBase):
    pass

class AssetCategoryUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    parent_id: Optional[Union[str, int]] = None

class AssetCategoryResponse(AssetCategoryBase):
    id: str

    class Config:
        from_attributes = True

class AssetBase(BaseModel):
    asset_name: str
    asset_unique_id: str
    asset_category_id: str
    asset_subcategory_id: Optional[str] = None
    manufacturer: Optional[str] = None
    supplier: Optional[str] = None
    purchase_from: Optional[str] = None
    model_no: Optional[str] = None
    serial_no: Optional[str] = None
    purchase_date: Optional[str] = None
    purchase_cost: Optional[float] = 0.0
    warranty_expiry: Optional[str] = None
    condition: Optional[str] = None
    status: Optional[str] = "Available"
    assigned_to: Optional[str] = None
    description: Optional[str] = None
    images: List[str] = []
    file_type: Optional[str] = None

class AssetCreate(AssetBase):
    pass

class AssetUpdate(BaseModel):
    asset_name: Optional[str] = None
    asset_unique_id: Optional[str] = None
    asset_category_id: Optional[str] = None
    asset_subcategory_id: Optional[str] = None
    manufacturer: Optional[str] = None
    supplier: Optional[str] = None
    purchase_from: Optional[str] = None
    model_no: Optional[str] = None
    serial_no: Optional[str] = None
    purchase_date: Optional[str] = None
    purchase_cost: Optional[float] = None
    warranty_expiry: Optional[str] = None
    condition: Optional[str] = None
    status: Optional[str] = None
    assigned_to: Optional[str] = None
    description: Optional[str] = None
    images: Optional[List[str]] = None
    file_type: Optional[str] = None

class AssetResponse(AssetBase):
    id: str

    class Config:
        from_attributes = True
