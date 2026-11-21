from pydantic import BaseModel, Field
from typing import Optional, List, Any, Dict
from datetime import datetime

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
