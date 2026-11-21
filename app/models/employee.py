from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Union, List, Any, Dict
from datetime import datetime

class EmployeeDocument(BaseModel):
    document_name: str
    document_proof: str
    file_type: Optional[str] = None

class EmployeeDocumentResponse(EmployeeDocument):
    id: str
    employee_id: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class ChecklistItem(BaseModel):
    name: str
    status: str = "Pending"  # Pending, Completed
    completed_at: Optional[str] = None

class EmployeeChecklistTemplateBase(BaseModel):
    name: str
    type: str  # "Onboarding", "Offboarding"
    is_default: bool = False

class EmployeeChecklistTemplateCreate(EmployeeChecklistTemplateBase):
    pass

class EmployeeChecklistTemplateUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    is_default: Optional[bool] = None

class EmployeeChecklistTemplateResponse(EmployeeChecklistTemplateBase):
    id: str

    class Config:
        from_attributes = True

class EmployeeBase(BaseModel):
    first_name: str
    last_name: str
    name: str  # Display name
    email: EmailStr
    personal_email: Optional[EmailStr] = None
    mobile: str
    date_of_birth: str  
    gender: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_number: Optional[str] = None
    parent_name: Optional[str] = None
    marital_status: Optional[str] = None
    employee_type: Optional[str] = None
    employee_no_id: str
    biometric_id: Optional[str] = None
    department: Optional[str] = None
    designation: Optional[str] = None
    role: Optional[str] = None
    status: Optional[str] = "Active"
    shift_id: Optional[str] = None
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    date_of_joining: Optional[str] = None
    confirmation_date: Optional[str] = None
    notice_period: Optional[str] = None
    work_mode: Optional[str] = "Office"
    weekly_off: List[int] = [6]  # 0=Mon, 1=Tue, ..., 6=Sun. Default: Sunday
    documents: List[EmployeeDocument] = []
    onboarding_checklist: List[ChecklistItem] = []
    offboarding_checklist: List[ChecklistItem] = []
    resignation_date: Optional[str] = None
    last_working_day: Optional[str] = None
    exit_interview_notes: Optional[str] = None
    address: Optional[str] = None
    account_name: Optional[str] = None
    bank_name: Optional[str] = None
    account_number: Optional[str] = None
    ifsc_code: Optional[str] = None
    pf_account_number: Optional[str] = None
    esic_number: Optional[str] = None
    pan_number: Optional[str] = None
    lop_rule_01: Optional[bool] = False

class EmployeeCreate(EmployeeBase):
    password: str

class EmployeeUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    personal_email: Optional[EmailStr] = None
    mobile: Optional[str] = None
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_number: Optional[str] = None
    parent_name: Optional[str] = None
    profile_picture: Optional[str] = None
    marital_status: Optional[str] = None
    employee_type: Optional[str] = None
    employee_no_id: Optional[str] = None
    biometric_id: Optional[str] = None
    department: Optional[str] = None
    designation: Optional[str] = None
    role: Optional[str] = None
    status: Optional[str] = None
    shift_id: Optional[str] = None
    date_of_joining: Optional[str] = None
    confirmation_date: Optional[str] = None
    notice_period: Optional[str] = None
    work_mode: Optional[str] = None
    weekly_off: Optional[List[int]] = None  # 0=Mon, 1=Tue, ..., 6=Sun
    documents: Optional[List[EmployeeDocument]] = None
    onboarding_checklist: Optional[List[ChecklistItem]] = None
    offboarding_checklist: Optional[List[ChecklistItem]] = None
    resignation_date: Optional[str] = None
    last_working_day: Optional[str] = None
    exit_interview_notes: Optional[str] = None
    address: Optional[str] = None
    account_name: Optional[str] = None
    bank_name: Optional[str] = None
    account_number: Optional[str] = None
    ifsc_code: Optional[str] = None
    pf_account_number: Optional[str] = None
    esic_number: Optional[str] = None
    pan_number: Optional[str] = None
    lop_rule_01: Optional[bool] = None

class EmployeeResponse(EmployeeBase):
    id: str
    profile_picture: Optional[str] = None
    documents: List[EmployeeDocumentResponse] = []

    class Config:
        from_attributes = True

class EmployeeBasicDetails(BaseModel):
    id: str
    first_name: Optional[str] = ""
    last_name: Optional[str] = ""
    name: Optional[str] = ""  # Display name
    email: Optional[EmailStr] = None
    designation: Optional[str] = None
    department: Optional[str] = None
    profile_picture: Optional[str] = None
    status: Optional[str] = "Active"
    employee_no_id: Optional[str] = ""

    class Config:
        from_attributes = True
