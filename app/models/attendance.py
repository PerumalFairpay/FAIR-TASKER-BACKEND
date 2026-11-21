from pydantic import BaseModel, Field
from typing import Optional, List, Any, Dict
from datetime import datetime
from .employee import EmployeeBasicDetails

class AttendanceBase(BaseModel):
    employee_id: str
    date: str  # Format: "YYYY-MM-DD"
    clock_in: str  # ISO 8601 timestamp

    device_type: str = "Web"  # Options: "Web", "Mobile", "Biometric", "Manual"

    clock_out: Optional[str] = None
    break_start: Optional[str] = None
    break_end: Optional[str] = None
    total_break_hours: float = 0.0
    total_work_hours: float = 0.0

    # Primary status: Present | Absent | Leave | Holiday
    status: str = "Present"

    # Detailed sub-status: Ontime | Late | Permission | Half Day
    attendance_status: Optional[str] = None

    overtime_hours: float = 0.0
    is_late: bool = False
    is_half_day: bool = False      # True when employee has an approved Half Day leave
    is_permission: bool = False    # True when employee has an approved Permission leave request
    leave_type_code: Optional[str] = None  # e.g. "CL", "SL", "LOP", "Half Day"

    notes: Optional[str] = None
    ip_address: Optional[str] = None
    location: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

class AttendanceCreate(BaseModel):
    """Payload for Clock In"""

    date: str
    clock_in: str
    device_type: str = "Web"  # Default to Web if not specified
    ip_address: Optional[str] = None
    location: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    notes: Optional[str] = None

class AttendanceUpdate(BaseModel):
    """Payload for Clock Out"""

    clock_out: Optional[str] = None
    break_start: Optional[str] = None
    break_end: Optional[str] = None
    device_type: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None
    location: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

class AttendanceAdminEdit(BaseModel):
    """Payload for Admin-Only Attendance Record Edit"""

    clock_in: Optional[str] = None           # ISO timestamp e.g. "2026-02-21T09:05:00"
    clock_out: Optional[str] = None          # ISO timestamp
    status: Optional[str] = None             # Present | Absent | Leave | Holiday
    attendance_status: Optional[str] = None  # Ontime | Late | Permission | Half Day
    is_late: Optional[bool] = None
    is_half_day: Optional[bool] = None
    is_permission: Optional[bool] = None
    device_type: Optional[str] = None
    notes: Optional[str] = None

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
