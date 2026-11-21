from pydantic import BaseModel, Field
from typing import Optional, List, Any, Dict
from datetime import datetime

class ShiftBase(BaseModel):
    name: str = Field(..., description="e.g., General, Night Support A")
    start_time: str = Field(..., description="Format HH:MM")
    end_time: str = Field(..., description="Format HH:MM")
    late_threshold_minutes: int = 15
    is_night_shift: bool = False
    department_ids: List[str] = []  # Departments that can use this shift

class ShiftCreate(ShiftBase):
    pass

class ShiftUpdate(BaseModel):
    name: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    late_threshold_minutes: Optional[int] = None
    is_night_shift: Optional[bool] = None
    department_ids: Optional[List[str]] = None

class ShiftResponse(ShiftBase):
    id: str

    class Config:
        from_attributes = True
