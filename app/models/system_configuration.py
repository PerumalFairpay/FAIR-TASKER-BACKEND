from pydantic import BaseModel, Field
from typing import Optional, List, Any, Dict
from datetime import datetime

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
