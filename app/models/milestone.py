from pydantic import BaseModel, Field
from typing import Optional, List, Any, Dict
from datetime import datetime

class MilestoneRoadmapAttachment(BaseModel):
    file_name: str
    file_url: str
    file_type: Optional[str] = None

class MilestoneRoadmapBase(BaseModel):
    project_id: str
    task_name: str
    description: Optional[str] = None
    start_date: str
    end_date: str
    priority: str = "Medium"
    assigned_to: List[str] = []
    attachments: List[MilestoneRoadmapAttachment] = []
    tags: List[str] = []
    status: str = "Backlog"

class MilestoneRoadmapCreate(MilestoneRoadmapBase):
    pass

class MilestoneRoadmapUpdate(BaseModel):
    project_id: Optional[str] = None
    task_name: Optional[str] = None
    description: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    priority: Optional[str] = None
    assigned_to: Optional[List[str]] = None
    attachments: Optional[List[MilestoneRoadmapAttachment]] = None
    tags: Optional[List[str]] = None
    status: Optional[str] = None

class MilestoneRoadmapResponse(MilestoneRoadmapBase):
    id: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# --- AI Chat History Models ---
