from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Union, List, Any
from datetime import datetime


class UserBase(BaseModel):
    employee_id: str
    attendance_id: str
    name: str
    email: EmailStr
    mobile: str
    role: Optional[str] = "employee"
    address: Optional[str] = None
    permissions: List[str] = []


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


class RoleBase(BaseModel):
    name: str
    description: Optional[str] = None
    permissions: List[str] = []  # List of Permission IDs


class RoleCreate(RoleBase):
    pass


class RoleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    permissions: Optional[List[str]] = None


class PermissionShortRef(BaseModel):
    id: str
    name: str


class RoleResponse(RoleBase):
    id: str
    permissions: List[PermissionShortRef]

    class Config:
        from_attributes = True


class PermissionBase(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None
    module: Optional[str] = None


class PermissionCreate(PermissionBase):
    pass


class PermissionUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None
    module: Optional[str] = None


class PermissionResponse(PermissionBase):
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


class EmployeeDocument(BaseModel):
    document_name: str
    document_proof: str
    file_type: Optional[str] = None


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
    date_of_joining: Optional[str] = None
    confirmation_date: Optional[str] = None
    notice_period: Optional[str] = None
    work_mode: Optional[str] = "Office"
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
    date_of_joining: Optional[str] = None
    confirmation_date: Optional[str] = None
    notice_period: Optional[str] = None
    work_mode: Optional[str] = None
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


class EmployeeResponse(EmployeeBase):
    id: str
    profile_picture: Optional[str] = None

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
    expense_subcategory_id: Optional[str] = None
    amount: float
    purpose: str
    payment_mode: str
    date: str
    attachment: Optional[str] = None
    file_type: Optional[str] = None


class ExpenseCreate(ExpenseBase):
    pass


class ExpenseUpdate(BaseModel):
    expense_category_id: Optional[str] = None
    expense_subcategory_id: Optional[str] = None
    amount: Optional[float] = None
    purpose: Optional[str] = None
    payment_mode: Optional[str] = None
    date: Optional[str] = None
    attachment: Optional[str] = None
    file_type: Optional[str] = None


class ExpenseResponse(ExpenseBase):
    id: str
    category_name: Optional[str] = None
    subcategory_name: Optional[str] = None

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
    document_subcategory_id: Optional[str] = None
    description: Optional[str] = None
    expiry_date: Optional[str] = None
    status: Optional[str] = "Active"
    file_path: Optional[str] = None
    file_type: Optional[str] = None


class DocumentCreate(DocumentBase):
    pass


class DocumentUpdate(BaseModel):
    name: Optional[str] = None
    document_category_id: Optional[str] = None
    document_subcategory_id: Optional[str] = None
    description: Optional[str] = None
    expiry_date: Optional[str] = None
    status: Optional[str] = None
    file_path: Optional[str] = None
    file_type: Optional[str] = None


class DocumentResponse(DocumentBase):
    id: str

    class Config:
        from_attributes = True


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


class ProjectBase(BaseModel):
    name: str
    client_id: str
    description: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    status: Optional[str] = "Planned"
    priority: Optional[str] = "Medium"
    project_manager_ids: List[str] = []
    team_leader_ids: List[str] = []
    team_member_ids: List[str] = []
    budget: Optional[float] = 0.0
    currency: Optional[str] = "USD"
    tags: List[str] = []
    technical_stacks: List[str] = []
    third_party_vendors: List[str] = []
    logo: Optional[str] = None


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    client_id: Optional[str] = None
    description: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    project_manager_ids: Optional[List[str]] = None
    team_leader_ids: Optional[List[str]] = None
    team_member_ids: Optional[List[str]] = None
    budget: Optional[float] = None
    currency: Optional[str] = None
    tags: Optional[List[str]] = None
    technical_stacks: Optional[List[str]] = None
    third_party_vendors: Optional[List[str]] = None
    logo: Optional[str] = None


class ProjectResponse(ProjectBase):
    id: str

    class Config:
        from_attributes = True


class HolidayBase(BaseModel):
    name: str
    date: str  # Format: "YYYY-MM-DD"
    description: Optional[str] = None
    holiday_type: str = "Public"  # e.g., Public, Mandatory, Optional/Restricted
    status: str = "Active"  # Active or Inactive


class HolidayCreate(HolidayBase):
    pass


class HolidayUpdate(BaseModel):
    name: Optional[str] = None
    date: Optional[str] = None
    description: Optional[str] = None
    holiday_type: Optional[str] = None
    status: Optional[str] = None


class HolidayResponse(HolidayBase):
    id: str

    class Config:
        from_attributes = True


class AssetCategoryBase(BaseModel):
    name: str
    description: Optional[str] = None
    parent_id: Optional[Union[str, int]] = None


class AssetCategoryCreate(AssetCategoryBase):
    pass


class AssetCategoryUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    parent_id: Optional[Union[str, int]] = None


class AssetCategoryResponse(AssetCategoryBase):
    id: str

    class Config:
        from_attributes = True


class AssetBase(BaseModel):
    asset_name: str
    asset_category_id: str
    asset_subcategory_id: Optional[str] = None
    manufacturer: Optional[str] = None
    supplier: Optional[str] = None
    purchase_from: Optional[str] = None
    model_no: Optional[str] = None
    serial_no: Optional[str] = None
    purchase_date: Optional[str] = None
    purchase_cost: Optional[float] = 0.0
    warranty_expiry: Optional[str] = None
    condition: Optional[str] = None
    status: Optional[str] = "Available"
    assigned_to: Optional[str] = None
    description: Optional[str] = None
    images: List[str] = []
    file_type: Optional[str] = None


class AssetCreate(AssetBase):
    pass


class AssetUpdate(BaseModel):
    asset_name: Optional[str] = None
    asset_category_id: Optional[str] = None
    asset_subcategory_id: Optional[str] = None
    manufacturer: Optional[str] = None
    supplier: Optional[str] = None
    purchase_from: Optional[str] = None
    model_no: Optional[str] = None
    serial_no: Optional[str] = None
    purchase_date: Optional[str] = None
    purchase_cost: Optional[float] = None
    warranty_expiry: Optional[str] = None
    condition: Optional[str] = None
    status: Optional[str] = None
    assigned_to: Optional[str] = None
    description: Optional[str] = None
    images: Optional[List[str]] = None
    file_type: Optional[str] = None


class AssetResponse(AssetBase):
    id: str

    class Config:
        from_attributes = True


class AssetAssignmentRequest(BaseModel):
    employee_id: Optional[str] = None


class BlogBase(BaseModel):
    title: str
    slug: str
    excerpt: str
    content: str
    category: str
    tags: List[str] = []
    is_published: bool = True
    cover_image: Optional[str] = None


class BlogCreate(BlogBase):
    pass


class BlogUpdate(BaseModel):
    title: Optional[str] = None
    slug: Optional[str] = None
    excerpt: Optional[str] = None
    content: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    is_published: Optional[bool] = None
    cover_image: Optional[str] = None


class BlogResponse(BlogBase):
    id: str
    author: Optional[dict] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class LeaveTypeBase(BaseModel):
    name: str
    type: str
    code: str
    status: str = "Active"
    number_of_days: int
    monthly_allowed: int
    allowed_hours: Optional[float] = 0.0


class LeaveTypeCreate(LeaveTypeBase):
    pass


class LeaveTypeUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    code: Optional[str] = None
    status: Optional[str] = None
    number_of_days: Optional[int] = None
    monthly_allowed: Optional[int] = None
    allowed_hours: Optional[float] = None


class LeaveTypeResponse(LeaveTypeBase):
    id: str

    class Config:
        from_attributes = True


class LeaveRequestBase(BaseModel):
    employee_id: str
    leave_type_id: str
    leave_duration_type: str  # "Single", "Multiple", "Half Day"
    start_date: str
    end_date: str
    half_day_session: Optional[str] = None  # "First Half", "Second Half"
    start_session: Optional[str] = (
        "Full Day"  # "Full Day", "Second Half" (For Multiple)
    )
    end_session: Optional[str] = "Full Day"  # "Full Day", "First Half" (For Multiple)
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    total_days: float
    reason: str
    attachment: Optional[str] = None
    file_type: Optional[str] = None
    status: str = "Pending"
    rejection_reason: Optional[str] = None


class LeaveRequestCreate(LeaveRequestBase):
    pass


class LeaveRequestUpdate(BaseModel):
    employee_id: Optional[str] = None
    leave_type_id: Optional[str] = None
    leave_duration_type: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    half_day_session: Optional[str] = None
    start_session: Optional[str] = None
    end_session: Optional[str] = None
    total_days: Optional[float] = None
    reason: Optional[str] = None
    attachment: Optional[str] = None
    file_type: Optional[str] = None
    status: Optional[str] = None
    rejection_reason: Optional[str] = None


class LeaveRequestStatusUpdate(BaseModel):
    status: str
    rejection_reason: Optional[str] = None


class LeaveRequestResponse(LeaveRequestBase):
    id: str
    employee_details: Optional[dict] = None
    leave_type_details: Optional[dict] = None
    file_type: Optional[str] = None

    class Config:
        from_attributes = True


class TaskAttachment(BaseModel):
    file_name: str
    file_url: str
    file_type: Optional[str] = None


class TaskBase(BaseModel):
    project_id: str
    task_name: str
    description: Optional[str] = None
    start_date: str
    end_date: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    priority: str = "Medium"
    assigned_to: List[str] = []
    attachments: List[TaskAttachment] = []
    tags: List[str] = []
    status: str = "Todo"
    progress: float = 0.0
    last_rollover_date: Optional[str] = None
    is_overdue_moved: bool = False


class TaskCreate(TaskBase):
    pass


class TaskUpdate(BaseModel):
    project_id: Optional[str] = None
    task_name: Optional[str] = None
    description: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    priority: Optional[str] = None
    assigned_to: Optional[List[str]] = None
    attachments: Optional[List[TaskAttachment]] = None
    tags: Optional[List[str]] = None
    status: Optional[str] = None
    progress: Optional[float] = None
    is_overdue_moved: Optional[bool] = None


class TaskStatusUpdate(BaseModel):
    status: str
    progress: float


class EODReportItem(BaseModel):
    task_id: str
    status: str
    progress: float
    eod_summary: Optional[str] = None
    move_to_tomorrow: bool = False
    new_attachments: List[TaskAttachment] = []


class EODReportRequest(BaseModel):
    reports: List[EODReportItem]


class TaskResponse(TaskBase):
    id: str
    parent_task_id: Optional[str] = None
    eod_history: List[dict] = []
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None

    class Config:
        from_attributes = True


class AttendanceBase(BaseModel):
    employee_id: str
    date: str  # Format: "YYYY-MM-DD"
    clock_in: str  # ISO 8601 timestamp

    # New Field
    device_type: str = "Web"  # Options: "Web", "Mobile", "Biometric", "Manual"

    clock_out: Optional[str] = None
    break_start: Optional[str] = None
    break_end: Optional[str] = None
    total_break_hours: float = 0.0
    total_work_hours: float = 0.0
    status: str = "Present"
    overtime_hours: float = 0.0
    is_late: bool = False
    notes: Optional[str] = None
    ip_address: Optional[str] = None
    location: Optional[str] = None


class AttendanceCreate(BaseModel):
    """Payload for Clock In"""

    date: str
    clock_in: str
    device_type: str = "Web"  # Default to Web if not specified
    ip_address: Optional[str] = None
    location: Optional[str] = None
    notes: Optional[str] = None


class AttendanceUpdate(BaseModel):
    """Payload for Clock Out"""

    clock_out: Optional[str] = None
    break_start: Optional[str] = None
    break_end: Optional[str] = None
    device_type: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None


class AttendanceStatusUpdate(BaseModel):
    """Payload for updating attendance status"""

    status: str
    reason: Optional[str] = None
    notes: Optional[str] = None



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


class AttendanceResponse(AttendanceBase):
    id: str
    employee_details: Optional[EmployeeBasicDetails] = None

    class Config:
        from_attributes = True


class BiometricLogItem(BaseModel):
    user_id: str
    timestamp: str
    status: Optional[Union[int, str]] = None
    punch: Optional[Union[int, str]] = None


class BiometricSyncRequest(BaseModel):
    data: List[BiometricLogItem]


class SystemConfigurationBase(BaseModel):
    key: str
    label: str
    value: Any
    input_type: (
        str  # "text", "number", "boolean", "time", "date", "select", "multiselect"
    )
    group: str
    options: List[str] = []
    is_public: bool = False


class SystemConfigurationCreate(SystemConfigurationBase):
    pass


class SystemConfigurationUpdate(BaseModel):
    value: Any


class SystemConfigurationResponse(SystemConfigurationBase):
    id: str

    class Config:
        from_attributes = True


# NDA Models
class NDARequestBase(BaseModel):
    employee_name: str
    email: EmailStr
    mobile: str
    role: str
    address: str
    residential_address: str
    required_documents: List[str] = []


class NDARequestCreate(NDARequestBase):
    expires_in_hours: Optional[int] = 1


class NDARequestUpdate(BaseModel):
    status: Optional[str] = None
    documents: Optional[List[str]] = None
    signature: Optional[str] = None
    signed_pdf_path: Optional[dict] = None
    browser: Optional[str] = None
    os: Optional[str] = None
    device_type: Optional[str] = None
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None


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


class PayslipBase(BaseModel):
    employee_id: str
    month: str
    year: int
    earnings: dict
    deductions: dict
    net_pay: float
    status: str = "Generated"  # Generated, Viewed
    file_path: Optional[str] = None
    generated_at: Optional[datetime] = None


class PayslipCreate(PayslipBase):
    pass


class PayslipUpdate(BaseModel):
    month: Optional[str] = None
    year: Optional[int] = None
    earnings: Optional[dict] = None
    deductions: Optional[dict] = None
    net_pay: Optional[float] = None


class PayslipResponse(PayslipBase):
    id: str
    employee_name: Optional[str] = None
    employee_email: Optional[str] = None
    employee_mobile: Optional[str] = None

    class Config:
        from_attributes = True


class PayslipComponentBase(BaseModel):
    name: str
    type: str  # "Earnings" or "Deductions"
    is_active: bool = True


class PayslipComponentCreate(PayslipComponentBase):
    pass


class PayslipComponentUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    is_active: Optional[bool] = None


class PayslipComponentResponse(PayslipComponentBase):
    id: str

    class Config:
        from_attributes = True


class FeedbackBase(BaseModel):
    employee_id: str
    employee_name: str
    type: str  # Bug, Feedback, Feature Request
    subject: str
    description: str
    priority: str = "Medium"  # Low, Medium, High, Critical
    status: str = "Open"  # Open, In Review, Resolved, Closed
    attachments: List[str] = []


class FeedbackCreate(FeedbackBase):
    pass


class FeedbackUpdate(BaseModel):
    id: Optional[str] = None
    employee_id: Optional[str] = None
    employee_name: Optional[str] = None
    type: Optional[str] = None
    subject: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    attachments: Optional[List[str]] = None


class FeedbackStatusUpdate(BaseModel):
    status: str


class FeedbackResponse(FeedbackBase):
    id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True