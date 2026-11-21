from pydantic import BaseModel, Field
from typing import Optional, List, Any, Dict
from datetime import datetime

class FeedbackAttachment(BaseModel):
    document_name: str
    document_proof: str
    file_type: Optional[str] = None

class FeedbackBase(BaseModel):
    user_id: Optional[str] = None
    type: str  # Bug, Feedback, Feature Request
    subject: str
    description: str
    priority: str = "Medium"  # Low, Medium, High, Critical
    status: str = "Open"  # Open, In Review, Resolved, Closed
    attachments: List[FeedbackAttachment] = []

class FeedbackCreate(FeedbackBase):
    pass

class FeedbackUpdate(BaseModel):
    id: Optional[str] = None
    type: Optional[str] = None
    subject: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    attachments: Optional[List[FeedbackAttachment]] = None

class FeedbackStatusUpdate(BaseModel):
    status: str

class FeedbackResponse(FeedbackBase):
    id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
