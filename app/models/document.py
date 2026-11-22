from pydantic import BaseModel, Field
from typing import Optional, List, Any, Dict, Union
from datetime import datetime

class DocumentCategoryBase(BaseModel):
    name: str
    description: Optional[str] = None
    parent_id: Optional[Union[str, int]] = None

class DocumentCategoryCreate(DocumentCategoryBase):
    pass

class DocumentCategoryUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    parent_id: Optional[Union[str, int]] = None

class DocumentCategoryResponse(DocumentCategoryBase):
    id: str

    class Config:
        from_attributes = True

class DocumentBase(BaseModel):
    name: str
    document_category_id: str
    document_subcategory_id: Optional[str] = None
    description: Optional[str] = None
    expiry_date: Optional[str] = None
    status: Optional[str] = "Active"
    file_path: Optional[str] = None
    file_type: Optional[str] = None

class DocumentCreate(DocumentBase):
    pass

class DocumentUpdate(BaseModel):
    name: Optional[str] = None
    document_category_id: Optional[str] = None
    document_subcategory_id: Optional[str] = None
    description: Optional[str] = None
    expiry_date: Optional[str] = None
    status: Optional[str] = None
    file_path: Optional[str] = None
    file_type: Optional[str] = None

class DocumentStatusUpdate(BaseModel):
    status: str

class DocumentResponse(DocumentBase):
    id: str

    class Config:
        from_attributes = True
