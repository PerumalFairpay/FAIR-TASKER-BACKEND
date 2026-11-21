from pydantic import BaseModel, Field
from typing import Optional, List, Any, Dict
from datetime import datetime

class ProjectBase(BaseModel):
    name: str
    client_id: str
    description: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    status: Optional[str] = "Planned"
    priority: Optional[str] = "Medium"
    project_manager_id: Optional[str] = None
    team_leader_ids: List[str] = []
    team_member_ids: List[str] = []
    budget: Optional[float] = 0.0
    currency: Optional[str] = "USD"
    tags: List[str] = []
    technical_stacks: List[str] = []
    third_party_vendors: List[str] = []
    logo: Optional[str] = None

class ProjectCreate(ProjectBase):
    pass

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    client_id: Optional[str] = None
    description: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    project_manager_id: Optional[str] = None
    team_leader_ids: Optional[List[str]] = None
    team_member_ids: Optional[List[str]] = None
    budget: Optional[float] = None
    currency: Optional[str] = None
    tags: Optional[List[str]] = None
    technical_stacks: Optional[List[str]] = None
    third_party_vendors: Optional[List[str]] = None
    logo: Optional[str] = None

class ProjectResponse(ProjectBase):
    id: str

    class Config:
        from_attributes = True
