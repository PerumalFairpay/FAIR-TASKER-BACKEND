from pydantic import BaseModel, Field
from typing import Optional, List, Any, Dict
from datetime import datetime

class PermissionBase(BaseModel):
    code: str
    name: str
    module: str
    description: Optional[str] = None

class PermissionCreate(PermissionBase):
    pass

class PermissionUpdate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    module: Optional[str] = None
    description: Optional[str] = None

class PermissionResponse(PermissionBase):
    id: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
