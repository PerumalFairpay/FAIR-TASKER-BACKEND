from fastapi import APIRouter, Depends, Form, File, UploadFile, Query
from typing import Optional, List
from app.helper.response_helper import success_response, error_response
from app.models import (
    TicketCreate,
    TicketUpdate,
    TicketStatusUpdate,
    TicketAssignUpdate,
    TicketAttachment
)
from app.services.api.ticket import TicketService
from app.helper.file_handler import file_handler
from app.auth import get_current_user

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.post("/")
async def create_ticket(
    title: str = Form(
        ...,
        description="Brief subject or title of the ticket",
        examples=["VPN connection failure"]
    ),
    description: str = Form(
        ...,
        description="Detailed description of the issue or request",
        examples=["Cannot connect to office VPN since morning after OS update."]
    ),
    category: str = Form(
        "General",
        description="Ticket category: 'IT Support', 'HR', 'Payroll', 'Facilities', 'General'",
        examples=["IT Support"]
    ),
    priority: str = Form(
        "Medium",
        description="Urgency/priority: 'Low', 'Medium', 'High', 'Critical'",
        examples=["Medium"]
    ),
    assigned_to: Optional[str] = Form(
        None,
        description="Optional User ID to assign ticket to"
    ),
    attachments: Optional[List[UploadFile]] = File(
        None,
        description="Optional image, document, or log attachments"
    ),
    current_user: dict = Depends(get_current_user)
):
    """Raise a new ticket with optional file attachments."""
    requester_id = str(current_user.get("id") or current_user.get("_id") or "")

    attachment_records = []
    if attachments:
        for file in attachments:
            if hasattr(file, "filename") and file.filename:
                uploaded = await file_handler.upload_file(file, subfolder="tickets")
                attachment_records.append(TicketAttachment(
                    document_name=file.filename,
                    document_proof=uploaded["url"],
                    file_type=getattr(file, "content_type", None),
                    file_size=getattr(file, "size", None)
                ))

    ticket_data = TicketCreate(
        title=title,
        description=description,
        category=category,
        priority=priority,
        requester_id=requester_id,
        assigned_to=assigned_to,
        attachments=attachment_records
    )

    data, error = await TicketService.create(ticket_data)
    if error:
        return error_response(message=f"Failed to create ticket: {error}", status_code=500)

    return success_response(
        message="Ticket created successfully",
        status_code=201,
        data=data
    )


@router.get("/")
async def get_tickets(
    search: Optional[str] = Query(None, description="Search across ticket number, title, or description"),
    status: Optional[str] = Query(None, description="Filter by status: Open, In Progress, Resolved, Closed"),
    priority: Optional[str] = Query(None, description="Filter by priority: Low, Medium, High, Critical"),
    category: Optional[str] = Query(None, description="Filter by category"),
    requester_id: Optional[str] = Query(None, description="Filter tickets by requester ID"),
    assigned_to: Optional[str] = Query(None, description="Filter tickets assigned to a user ID"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(50, ge=1, le=100, description="Items per page"),
    current_user: dict = Depends(get_current_user)
):
    """List tickets with search, filtering, and pagination."""
    data, meta, error = await TicketService.list(
        search=search,
        status=status,
        priority=priority,
        category=category,
        requester_id=requester_id,
        assigned_to=assigned_to,
        page=page,
        limit=limit
    )
    if error:
        return error_response(message=f"Failed to fetch tickets: {error}", status_code=500)

    return success_response(
        message="Tickets fetched successfully",
        data=data,
        meta=meta
    )


@router.get("/my-tickets")
async def get_my_tickets(
    search: Optional[str] = Query(None, description="Search across ticket number, title, or description"),
    status: Optional[str] = Query(None, description="Filter by status: Open, In Progress, Resolved, Closed"),
    priority: Optional[str] = Query(None, description="Filter by priority: Low, Medium, High, Critical"),
    category: Optional[str] = Query(None, description="Filter by category"),
    assigned_to: Optional[str] = Query(None, description="Filter by assigned employee/user ID (or 'me')"),
    scope: Optional[str] = Query("created", description="Scope: 'created' (raised by me) or 'assigned' (assigned to me)"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(50, ge=1, le=100, description="Items per page"),
    current_user: dict = Depends(get_current_user)
):
    """Retrieve tickets created by or assigned to the currently logged-in user."""
    user_id = str(current_user.get("id") or current_user.get("_id") or "")
    
    # Resolve all possible IDs for this user (user._id and employee._id if linked)
    user_ids = [user_id]
    emp_no_id = current_user.get("employee_no_id")
    from app.database import employees_collection
    if emp_no_id:
        emp = await employees_collection.find_one({"employee_no_id": emp_no_id, "is_deleted": {"$ne": True}})
        if emp and str(emp["_id"]) not in user_ids:
            user_ids.append(str(emp["_id"]))
    email = current_user.get("email")
    if email:
        emp_by_email = await employees_collection.find_one({"email": email, "is_deleted": {"$ne": True}})
        if emp_by_email and str(emp_by_email["_id"]) not in user_ids:
            user_ids.append(str(emp_by_email["_id"]))

    if scope == "assigned":
        # Filter where assigned_to is any of the user's IDs
        target_assigned_to = user_ids[0] if len(user_ids) == 1 else {"$in": user_ids}
        data, meta, error = await TicketService.list(
            search=search,
            status=status,
            priority=priority,
            category=category,
            assigned_to=target_assigned_to,
            page=page,
            limit=limit
        )
    else:
        # Default: tickets created by me
        data, meta, error = await TicketService.list(
            search=search,
            status=status,
            priority=priority,
            category=category,
            requester_id=user_id,
            page=page,
            limit=limit
        )

    if error:
        return error_response(message=f"Failed to fetch your tickets: {error}", status_code=500)

    return success_response(
        message="Your tickets fetched successfully",
        data=data,
        meta=meta
    )


@router.get("/{ticket_id}")
async def get_ticket(
    ticket_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get detailed ticket info including all discussion messages and attachments."""
    data, error = await TicketService.get(ticket_id)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)

    return success_response(
        message="Ticket fetched successfully",
        data=data
    )


@router.put("/{ticket_id}")
async def update_ticket(
    ticket_id: str,
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    priority: Optional[str] = Form(None),
    status: Optional[str] = Form(None),
    assigned_to: Optional[str] = Form(None),
    attachments: Optional[List[UploadFile]] = File(None),
    current_user: dict = Depends(get_current_user)
):
    """Update ticket properties and/or add new attachments."""
    attachment_records = None
    if attachments:
        attachment_records = []
        for file in attachments:
            if hasattr(file, "filename") and file.filename:
                uploaded = await file_handler.upload_file(file, subfolder="tickets")
                attachment_records.append(TicketAttachment(
                    document_name=file.filename,
                    document_proof=uploaded["url"],
                    file_type=getattr(file, "content_type", None),
                    file_size=getattr(file, "size", None)
                ))

    ticket_update = TicketUpdate(
        title=title,
        description=description,
        category=category,
        priority=priority,
        status=status,
        assigned_to=assigned_to,
        attachments=attachment_records
    )

    data, error = await TicketService.update(ticket_id, ticket_update)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)

    return success_response(
        message="Ticket updated successfully",
        data=data
    )


@router.patch("/{ticket_id}/status")
async def update_ticket_status(
    ticket_id: str,
    payload: TicketStatusUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Quickly update ticket status (e.g., Open, In Progress, Resolved, Closed)."""
    data, error = await TicketService.update(
        ticket_id,
        TicketUpdate(status=payload.status)
    )
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)

    return success_response(
        message=f"Ticket status updated to {payload.status}",
        data=data
    )


@router.patch("/{ticket_id}/assign")
async def assign_ticket(
    ticket_id: str,
    payload: TicketAssignUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Assign or reassign ticket to another user."""
    data, error = await TicketService.update(
        ticket_id,
        TicketUpdate(assigned_to=payload.assigned_to)
    )
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)

    return success_response(
        message="Ticket assignment updated successfully",
        data=data
    )


@router.post("/{ticket_id}/messages")
async def add_ticket_message(
    ticket_id: str,
    message: str = Form(..., description="Message text or reply"),
    attachments: Optional[List[UploadFile]] = File(None, description="Optional reply attachments"),
    current_user: dict = Depends(get_current_user)
):
    """Post a reply message or update in the ticket thread."""
    sender_id = str(current_user.get("id") or current_user.get("_id") or "")

    attachment_records = []
    if attachments:
        for file in attachments:
            if hasattr(file, "filename") and file.filename:
                uploaded = await file_handler.upload_file(file, subfolder="tickets")
                attachment_records.append({
                    "document_name": file.filename,
                    "document_proof": uploaded["url"],
                    "file_type": getattr(file, "content_type", None),
                    "file_size": getattr(file, "size", None)
                })

    created_msg, error = await TicketService.add_message(
        ticket_id=ticket_id,
        sender_id=sender_id,
        message=message,
        attachments=attachment_records
    )
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)

    return success_response(
        message="Reply posted successfully",
        status_code=201,
        data=created_msg
    )


@router.delete("/{ticket_id}")
async def delete_ticket(
    ticket_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Soft delete a ticket."""
    success, error = await TicketService.delete(ticket_id)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)

    return success_response(message="Ticket deleted successfully", data=[])
