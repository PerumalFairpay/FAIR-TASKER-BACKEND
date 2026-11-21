from pydantic import BaseModel, Field
from typing import Optional, List, Any, Dict
from datetime import datetime

class TicketAttachment(BaseModel):
    document_name: str
    document_proof: str
    file_type: Optional[str] = None
    file_size: Optional[int] = None

class TicketMessageBase(BaseModel):
    ticket_id: str
    message: str
    attachments: Optional[List[TicketAttachment]] = []

class TicketMessageCreate(BaseModel):
    message: str
    attachments: Optional[List[TicketAttachment]] = []

class TicketMessageResponse(BaseModel):
    id: str
    ticket_id: str
    sender_id: str
    sender: Optional[Dict[str, Any]] = None
    message: str
    attachments: List[TicketAttachment] = []
    created_at: datetime

class TicketBase(BaseModel):
    title: str
    description: str
    category: str = "General"  # e.g., IT Support, HR, Payroll, Facilities, General
    priority: str = "Medium"   # Low, Medium, High, Critical
    status: str = "Open"       # Open, In Progress, Resolved, Closed

class TicketCreate(TicketBase):
    requester_id: Optional[str] = None
    assigned_to: Optional[str] = None
    attachments: Optional[List[TicketAttachment]] = []

class TicketUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    assigned_to: Optional[str] = None
    attachments: Optional[List[TicketAttachment]] = None

class TicketStatusUpdate(BaseModel):
    status: str

class TicketAssignUpdate(BaseModel):
    assigned_to: Optional[str] = None
