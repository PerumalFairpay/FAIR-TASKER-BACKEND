from pydantic import BaseModel, Field
from typing import Optional, List, Any, Dict
from datetime import datetime

class DepartmentBase(BaseModel):
    name: str
    parent_id: Optional[Union[str, int]] = None
    default_shift_id: Optional[str] = None

class DepartmentCreate(DepartmentBase):
    pass

class DepartmentUpdate(BaseModel):
    name: Optional[str] = None
    parent_id: Optional[Union[str, int]] = None
    default_shift_id: Optional[str] = None

class DepartmentResponse(DepartmentBase):
    id: str
    default_shift_id: Optional[str] = None

    class Config:
        from_attributes = True
