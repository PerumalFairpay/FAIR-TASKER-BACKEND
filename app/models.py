from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Union, List

class UserBase(BaseModel):
    employee_id: str
    attendance_id: str
    name: str
    email: EmailStr
    mobile: str

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

class RoleBase(BaseModel):
    name: str
    description: Optional[str] = None
    permissions: list[str] = []

class RoleCreate(RoleBase):
    pass

class RoleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    permissions: Optional[list[str]] = None

class RoleResponse(RoleBase):
    id: str

    class Config:
        from_attributes = True

class DepartmentBase(BaseModel):
    name: str
    parent_id: Optional[Union[str, int]] = None

class DepartmentCreate(DepartmentBase):
    pass

class DepartmentUpdate(BaseModel):
    name: Optional[str] = None
    parent_id: Optional[Union[str, int]] = None

class DepartmentResponse(DepartmentBase):
    id: str

    class Config:
        from_attributes = True
