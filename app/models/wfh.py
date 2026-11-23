from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime

class WFHRequestBase(BaseModel):
    employee_id: str
    start_date: str
    end_date: str
    total_days: float = 1.0
    request_type: str = "Temporary"  # "Temporary" or "Permanent"
    reason: str
    status: str = "Pending"  # "Pending", "Approved", "Rejected", "Cancelled"
    rejection_reason: Optional[str] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[str] = None

class WFHRequestCreate(BaseModel):
    employee_id: Optional[str] = None
    start_date: str
    end_date: str
    total_days: Optional[float] = None
    request_type: Optional[str] = "Temporary"
    reason: str


class WFHRequestUpdate(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    total_days: Optional[float] = None
    request_type: Optional[str] = None
    reason: Optional[str] = None

class WFHRequestStatusUpdate(BaseModel):
    status: str  # "Approved" or "Rejected"
    rejection_reason: Optional[str] = None

class WFHRequestResponse(WFHRequestBase):
    id: str
    employee_details: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True
