from pydantic import BaseModel, EmailStr, Field
from typing import Optional

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
