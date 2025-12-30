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

class EmployeeBase(BaseModel):
    first_name: str
    last_name: str
    name: str  # Display name
    email: EmailStr
    mobile: str
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_number: Optional[str] = None
    parent_name: Optional[str] = None
    marital_status: Optional[str] = None
    employee_type: Optional[str] = None
    employee_no_id: str
    department: Optional[str] = None
    designation: Optional[str] = None
    role: Optional[str] = None
    status: Optional[str] = "Active"
    date_of_joining: Optional[str] = None
    confirmation_date: Optional[str] = None
    notice_period: Optional[str] = None
    document_name: Optional[str] = None

class EmployeeCreate(EmployeeBase):
    password: str

class EmployeeUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    name: Optional[str] = None
    email: Optional[EmailStr] = None
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
    department: Optional[str] = None
    designation: Optional[str] = None
    role: Optional[str] = None
    status: Optional[str] = None
    date_of_joining: Optional[str] = None
    confirmation_date: Optional[str] = None
    notice_period: Optional[str] = None
    document_name: Optional[str] = None
    document_proof: Optional[str] = None

class EmployeeResponse(EmployeeBase):
    id: str
    profile_picture: Optional[str] = None
    document_proof: Optional[str] = None

    class Config:
        from_attributes = True

class ExpenseCategoryBase(BaseModel):
    name: str
    description: Optional[str] = None
    parent_id: Optional[Union[str, int]] = None

class ExpenseCategoryCreate(ExpenseCategoryBase):
    pass

class ExpenseCategoryUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    parent_id: Optional[Union[str, int]] = None

class ExpenseCategoryResponse(ExpenseCategoryBase):
    id: str

    class Config:
        from_attributes = True

class ExpenseBase(BaseModel):
    expense_category_id: str
    amount: float
    purpose: str
    payment_mode: str
    date: str
    attachment: Optional[str] = None

class ExpenseCreate(ExpenseBase):
    pass

class ExpenseUpdate(BaseModel):
    expense_category_id: Optional[str] = None
    amount: Optional[float] = None
    purpose: Optional[str] = None
    payment_mode: Optional[str] = None
    date: Optional[str] = None
    attachment: Optional[str] = None

class ExpenseResponse(ExpenseBase):
    id: str

    class Config:
        from_attributes = True

class DocumentCategoryBase(BaseModel):
    name: str
    description: Optional[str] = None
    parent_id: Optional[Union[str, int]] = None

class DocumentCategoryCreate(DocumentCategoryBase):
    pass

class DocumentCategoryUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    parent_id: Optional[Union[str, int]] = None

class DocumentCategoryResponse(DocumentCategoryBase):
    id: str

    class Config:
        from_attributes = True

class DocumentBase(BaseModel):
    name: str
    document_category_id: str
    description: Optional[str] = None
    expiry_date: Optional[str] = None
    status: Optional[str] = "Active"
    file_path: Optional[str] = None

class DocumentCreate(DocumentBase):
    pass

class DocumentUpdate(BaseModel):
    name: Optional[str] = None
    document_category_id: Optional[str] = None
    description: Optional[str] = None
    expiry_date: Optional[str] = None
    status: Optional[str] = None
    file_path: Optional[str] = None

class DocumentResponse(DocumentBase):
    id: str

    class Config:
        from_attributes = True
