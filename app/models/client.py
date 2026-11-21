from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Any, Dict
from datetime import datetime

class ClientBase(BaseModel):
    company_name: str
    contact_name: str
    contact_email: EmailStr
    contact_mobile: str
    contact_person_designation: Optional[str] = None
    contact_address: Optional[str] = None
    description: Optional[str] = None
    logo: Optional[str] = None
    status: Optional[str] = "Active"

class ClientCreate(ClientBase):
    pass

class ClientUpdate(BaseModel):
    company_name: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[EmailStr] = None
    contact_mobile: Optional[str] = None
    contact_person_designation: Optional[str] = None
    contact_address: Optional[str] = None
    description: Optional[str] = None
    logo: Optional[str] = None
    status: Optional[str] = None

class ClientResponse(ClientBase):
    id: str

    class Config:
        from_attributes = True
