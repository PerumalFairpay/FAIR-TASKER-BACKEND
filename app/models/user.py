from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Union, List, Any, Dict
from datetime import datetime
from .permission import PermissionResponse

class UserBase(BaseModel):
    employee_no_id: str
    biometric_id: Optional[str] = None
    name: str
    email: EmailStr
    mobile: str
    role: Optional[str] = "employee"
    address: Optional[str] = None
    permissions: List[str] = []
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None

class UserCreate(UserBase):
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserInDB(UserBase):
    hashed_password: str

class UserResponse(UserBase):
    id: str

    class Config:
        from_attributes = True

class UserPermissionsUpdate(BaseModel):
    permissions: List[str]

class UserPermissionUpdate(BaseModel):
    permission_ids: List[str]

class UserPermissionsDetailResponse(BaseModel):
    user_id: str
    name: Optional[str] = None
    email: Optional[str] = None
    role_id: Optional[str] = None
    role_name: Optional[str] = None
    role_permissions: List[PermissionResponse] = []
    direct_permissions: List[PermissionResponse] = []
    effective_permissions: List[str] = []
