from pydantic import BaseModel, EmailStr, Field
from typing import Optional

class UserBase(BaseModel):
    first_name: str
    last_name: str
    phone: str
    email: EmailStr
    department: str
    hrm_id: str

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
