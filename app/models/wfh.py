from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

class WFHRequestBase(BaseModel):
    employee_id: str = Field(..., description="MongoDB ObjectId of the employee", example="")
    start_date: str = Field(..., description="Start date of WFH in YYYY-MM-DD format", example="2026-11-25")
    end_date: Optional[str] = Field(None, description="End date in YYYY-MM-DD format. Null for Permanent requests", example="2026-11-27")
    total_days: Optional[float] = Field(None, description="Total days requested for Work From Home. Null for Permanent", example=3.0)
    request_type: str = Field("Temporary", description="Type of WFH request: 'Temporary' or 'Permanent'", example="Temporary")
    reason: str = Field(..., description="Reason for requesting Work From Home", example="Home renovation and attending personal deliveries")
    status: str = Field("Pending", description="Current request status: 'Pending', 'Approved', or 'Rejected'", example="Pending")
    rejection_reason: Optional[str] = Field(None, description="Reason provided by admin if request is rejected", example=None)
    reviewed_by: Optional[str] = Field(None, description="Name or identifier of the reviewer/admin", example="Admin User")
    reviewed_at: Optional[str] = Field(None, description="UTC ISO timestamp of review", example="2026-11-23T07:15:00.000000")

class WFHRequestCreate(BaseModel):
    employee_id: Optional[str] = Field(None, description="Optional. If omitted, automatically derived from the authenticated token", example="")
    start_date: str = Field(..., description="Start date of WFH in YYYY-MM-DD format", example="2026-11-25")
    end_date: Optional[str] = Field(None, description="End date in YYYY-MM-DD format. Required for 'Temporary', omitted/null for 'Permanent'", example="2026-11-27")
    total_days: Optional[float] = Field(None, description="Total number of days. If omitted for temporary, calculated automatically", example=3.0)
    request_type: Optional[str] = Field("Temporary", description="Type of request: 'Temporary' or 'Permanent'", example="Temporary")
    reason: str = Field(..., description="Detailed explanation for WFH request", example="Home renovation and attending personal deliveries")

class WFHRequestUpdate(BaseModel):
    start_date: Optional[str] = Field(None, description="Start date in YYYY-MM-DD format", example="2026-11-25")
    end_date: Optional[str] = Field(None, description="End date in YYYY-MM-DD format", example="2026-11-27")
    total_days: Optional[float] = Field(None, description="Total days count", example=3.0)
    request_type: Optional[str] = Field(None, description="'Temporary' or 'Permanent'", example="Temporary")
    reason: Optional[str] = Field(None, description="Updated reason", example="Updated reason for WFH")

class WFHRequestStatusUpdate(BaseModel):
    status: str = Field(..., description="Review decision: 'Approved' or 'Rejected'", example="Approved")
    rejection_reason: Optional[str] = Field(None, description="Mandatory/optional reason if status is 'Rejected'", example="Team is required to work from office on selected days")

class WFHRequestResponse(WFHRequestBase):
    id: str = Field(..., description="MongoDB ObjectId of the WFH request", example="6741b61c8a149b25d0123456")
    employee_details: Optional[Dict[str, Any]] = Field(None, description="Basic employee details including name, email, department, profile image")
    created_at: Optional[str] = Field(None, description="UTC ISO creation timestamp", example="2026-11-23T06:30:15.123456")
    updated_at: Optional[str] = Field(None, description="UTC ISO update timestamp", example="2026-11-23T06:30:15.123456")

    class Config:
        from_attributes = True
