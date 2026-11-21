from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Any, Dict
from datetime import datetime

class NDARequestBase(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    mobile: Optional[str] = None
    designation: str
    department: Optional[str] = None
    address: Optional[str] = None
    residential_address: Optional[str] = None
    # Granular Permanent Address
    perma_door_no: Optional[str] = None
    perma_care_of_type: Optional[str] = None
    perma_care_of_name: Optional[str] = None
    perma_street: Optional[str] = None
    perma_city: Optional[str] = None
    perma_state: Optional[str] = None
    perma_pincode: Optional[str] = None
    # Granular Residential Address
    res_door_no: Optional[str] = None
    res_care_of_type: Optional[str] = None
    res_care_of_name: Optional[str] = None
    res_street: Optional[str] = None
    res_city: Optional[str] = None
    res_state: Optional[str] = None
    res_pincode: Optional[str] = None
    required_documents: List[str] = []
    status: str = "Pending"
    rejection_reason: Optional[str] = None
    nda_date: Optional[str] = None

class NDARequestCreate(NDARequestBase):
    expires_in_hours: Optional[int] = 1

class NDARequestUpdate(BaseModel):
    status: Optional[str] = None
    address: Optional[str] = None
    residential_address: Optional[str] = None
    # Granular Permanent Address
    perma_door_no: Optional[str] = None
    perma_care_of_type: Optional[str] = None
    perma_care_of_name: Optional[str] = None
    perma_street: Optional[str] = None
    perma_city: Optional[str] = None
    perma_state: Optional[str] = None
    perma_pincode: Optional[str] = None
    # Granular Residential Address
    res_door_no: Optional[str] = None
    res_care_of_type: Optional[str] = None
    res_care_of_name: Optional[str] = None
    res_street: Optional[str] = None
    res_city: Optional[str] = None
    res_state: Optional[str] = None
    res_pincode: Optional[str] = None
    mobile: Optional[str] = None
    documents: Optional[List[str]] = None
    signature: Optional[str] = None
    signed_pdf_path: Optional[dict] = None
    browser: Optional[str] = None
    os: Optional[str] = None
    device_type: Optional[str] = None
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None
    rejection_reason: Optional[str] = None
    nda_date: Optional[str] = None

class NDAStatusUpdate(BaseModel):
    status: str
    rejection_reason: Optional[str] = None

class NDARequestResponse(NDARequestBase):
    id: str
    token: str
    status: str
    expires_at: datetime
    created_at: datetime
    documents: List[EmployeeDocument] = []
    signature: Optional[str] = None
    signed_pdf_path: Optional[dict] = None
    browser: Optional[str] = None
    os: Optional[str] = None
    device_type: Optional[str] = None 
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None
    email: Optional[EmailStr] = None
    mobile: Optional[str] = None
    # Granular Permanent Address
    perma_door_no: Optional[str] = None
    perma_care_of_type: Optional[str] = None
    perma_care_of_name: Optional[str] = None
    perma_street: Optional[str] = None
    perma_city: Optional[str] = None
    perma_state: Optional[str] = None
    perma_pincode: Optional[str] = None
    # Granular Residential Address
    res_door_no: Optional[str] = None
    res_care_of_type: Optional[str] = None
    res_care_of_name: Optional[str] = None
    res_street: Optional[str] = None
    res_city: Optional[str] = None
    res_state: Optional[str] = None
    res_pincode: Optional[str] = None

class NDADropdownItem(BaseModel):
    id: str
    first_name: str
    last_name: str
    email: str
    mobile: str
    address: Optional[str] = None
    residential_address: Optional[str] = None
    designation: str
    department: Optional[str] = None

    class Config:
        from_attributes = True

class NDASignatureRequest(BaseModel):
    signature: str
    browser: Optional[str] = None
    os: Optional[str] = None
    device_type: Optional[str] = None
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None

class NDARegenerateRequest(BaseModel):
    expires_in_hours: Optional[int] = 1
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    mobile: Optional[str] = None
    designation: Optional[str] = None
    department: Optional[str] = None
    address: Optional[str] = None
    residential_address: Optional[str] = None
    # Granular Permanent Address
    perma_door_no: Optional[str] = None
    perma_care_of_type: Optional[str] = None
    perma_care_of_name: Optional[str] = None
    perma_street: Optional[str] = None
    perma_city: Optional[str] = None
    perma_state: Optional[str] = None
    perma_pincode: Optional[str] = None
    # Granular Residential Address
    res_door_no: Optional[str] = None
    res_care_of_type: Optional[str] = None
    res_care_of_name: Optional[str] = None
    res_street: Optional[str] = None
    res_city: Optional[str] = None
    res_state: Optional[str] = None
    res_pincode: Optional[str] = None
    required_documents: Optional[List[str]] = None
    nda_date: Optional[str] = None
