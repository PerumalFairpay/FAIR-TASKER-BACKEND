from pydantic import BaseModel, Field
from typing import Optional, List, Any, Dict
from datetime import datetime

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
