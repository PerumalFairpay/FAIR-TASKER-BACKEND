from pydantic import BaseModel, Field
from typing import Optional, List, Any, Dict
from datetime import datetime
from .permission import PermissionResponse

class RoleBase(BaseModel):
    name: str
    description: Optional[str] = None

class RoleCreate(BaseModel):
    name: str
    description: Optional[str] = None
    permission_ids: Optional[List[str]] = None

class RoleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    permission_ids: Optional[List[str]] = None

class RoleResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    permissions: List[PermissionResponse] = []
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class RolePermissionUpdate(BaseModel):
    permission_ids: List[str]
