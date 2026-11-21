from pydantic import BaseModel, Field
from typing import Optional, List, Any, Dict
from datetime import datetime

class LeaveTypeBase(BaseModel):
    name: str
    type: str
    code: str
    description: Optional[str] = None
    status: str = "Active"
    number_of_days: int
    monthly_allowed: int
    allowed_hours: Optional[float] = 0.0
    can_carry_forward: bool = False
    can_encash: bool = False
    probation_period_months: int = 0
    min_service_days: int = 0
    notice_period_days: int = 0
    allow_adjacent_to_holiday: bool = True

class LeaveTypeCreate(LeaveTypeBase):
    pass

class LeaveTypeUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    code: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    number_of_days: Optional[int] = None
    monthly_allowed: Optional[int] = None
    allowed_hours: Optional[float] = None
    can_carry_forward: Optional[bool] = None
    can_encash: Optional[bool] = None
    probation_period_months: Optional[int] = None
    min_service_days: Optional[int] = None
    notice_period_days: Optional[int] = None
    allow_adjacent_to_holiday: Optional[bool] = None

class LeaveTypeResponse(LeaveTypeBase):
    id: str

    class Config:
        from_attributes = True

class LeaveRequestBase(BaseModel):
    employee_id: str
    leave_type_id: str
    leave_duration_type: str  # "Single", "Multiple", "Half Day", "Permission"
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
    is_compensated: bool = False

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
    is_compensated: Optional[bool] = None

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
