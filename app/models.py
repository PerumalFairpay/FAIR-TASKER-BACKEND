from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List



# Role Models
class RoleBase(BaseModel):
    name: str
    description: Optional[str] = None
    permissions: List[str] = []

class RoleCreate(RoleBase):
    pass

class RoleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    permissions: Optional[List[str]] = None

class RoleResponse(RoleBase):
    id: str

    class Config:
        from_attributes = True

# User Models
class UserBase(BaseModel):
    name: str
    email: EmailStr
    mobile: str
    employee_id: str
    attendance_id: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    department: Optional[str] = None
    hrm_id: Optional[str] = None
    role: str = "employee"  # Default role

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
