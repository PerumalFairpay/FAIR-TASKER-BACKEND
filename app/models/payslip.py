from pydantic import BaseModel, Field
from typing import Optional, List, Any, Dict
from datetime import datetime

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
