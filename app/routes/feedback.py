from fastapi import APIRouter, Depends, Form, File, UploadFile
from typing import Optional, List
from app.helper.response_helper import success_response, error_response
from app.models import FeedbackCreate, FeedbackUpdate, FeedbackStatusUpdate
from app.services.api.feedback import FeedbackService
from app.helper.file_handler import file_handler
from app.auth import get_current_user, require_permission

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("/", dependencies=[Depends(require_permission("feedback:submit"))])
async def create_feedback(
    type: str = Form(
        ...,
        description="Category of the feedback. Allowed values: 'Bug', 'Feedback', or 'Feature Request'",
        examples=["Bug"]
    ),
    subject: str = Form(
        ...,
        description="Brief title or summary of the issue/feedback",
        examples=["Leave calendar not rendering properly"]
    ),
    description: str = Form(
        ...,
        description="Detailed explanation of the issue, steps to reproduce, or enhancement details",
        examples=["When clicking the calendar tab in Firefox, the view stays blank."]
    ),
    priority: str = Form(
        "Medium",
        description="Urgency/priority level. Allowed values: 'Low', 'Medium', 'High', 'Critical'",
        examples=["Medium"]
    ),
    attachments: Optional[List[UploadFile]] = File(
        None,
        description="Optional image, document, or log files related to the feedback"
    ),
    current_user: dict = Depends(get_current_user)
):
    # Automatically bind user_id from authenticated session
    resolved_user_id = str(current_user.get("id") or current_user.get("_id") or "")

    attachment_urls = []
    if attachments:
        for file in attachments:
            if hasattr(file, "filename") and file.filename:
                uploaded = await file_handler.upload_file(file, subfolder="feedback")
                attachment_urls.append({
                    "document_name": file.filename,
                    "document_proof": uploaded["url"],
                    "file_type": getattr(file, "content_type", None)
                })

    feedback_data = FeedbackCreate(
        user_id=resolved_user_id,
        type=type,
        subject=subject,
        description=description,
        priority=priority,
        attachments=attachment_urls
    )

    data, metrics, error = await FeedbackService.create(feedback_data)
    if error:
        return error_response(message=f"Failed to submit feedback: {error}", status_code=500)

    return success_response(
        message="Feedback submitted successfully",
        status_code=201,
        data=data,
        meta=metrics
    )


@router.get("/", dependencies=[Depends(require_permission("feedback:view"))])
async def get_feedbacks(
    user_id: Optional[str] = None,
    status: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    data, metrics, error = await FeedbackService.list(user_id=user_id, status=status)
    if error:
        return error_response(message=f"Failed to fetch feedbacks: {error}", status_code=500)

    return success_response(
        message="Feedbacks fetched successfully",
        data=data,
        meta=metrics
    )


@router.put("/{feedback_id}", dependencies=[Depends(require_permission("feedback:submit"))])
async def update_feedback(
    feedback_id: str,
    status: Optional[str] = Form(
        None,
        description="Optional status update. Allowed values: 'Open', 'In Review', 'Resolved', 'Closed'"
    ),
    priority: Optional[str] = Form(
        None,
        description="Optional updated priority level: 'Low', 'Medium', 'High', 'Critical'"
    ),
    type: Optional[str] = Form(
        None,
        description="Optional updated category: 'Bug', 'Feedback', 'Feature Request'"
    ),
    subject: Optional[str] = Form(
        None,
        description="Optional updated subject title"
    ),
    description: Optional[str] = Form(
        None,
        description="Optional updated description text"
    ),
    attachments: Optional[List[UploadFile]] = File(
        None,
        description="Optional additional attachments to upload"
    ),
    current_user: dict = Depends(get_current_user)
):
    # Ownership check: users can only edit their own feedback unless admin
    if current_user.get("role") not in ["admin", "super_admin"]:
        existing, err = await FeedbackService.get(feedback_id)
        if not existing or err:
            return error_response(message="Feedback not found", status_code=404)

        current_uid = str(current_user.get("id") or current_user.get("_id") or "")
        feedback_uid = str(existing.get("user_id", ""))

        if feedback_uid != current_uid:
            return error_response(
                message="You are not authorized to edit this feedback",
                status_code=403
            )

    attachment_urls = []
    if attachments:
        for file in attachments:
            if hasattr(file, "filename") and file.filename:
                uploaded = await file_handler.upload_file(file, subfolder="feedback")
                attachment_urls.append({
                    "document_name": file.filename,
                    "document_proof": uploaded["url"],
                    "file_type": getattr(file, "content_type", None)
                })

    feedback_update = FeedbackUpdate(
        status=status,
        priority=priority,
        type=type,
        subject=subject,
        description=description,
        attachments=attachment_urls if attachment_urls else None
    )

    data, metrics, error = await FeedbackService.update(feedback_id, feedback_update)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)

    return success_response(
        message="Feedback updated successfully",
        data=data,
        meta=metrics
    )


@router.patch("/{feedback_id}/status", dependencies=[Depends(require_permission("feedback:manage"))])
async def update_feedback_status(
    feedback_id: str,
    payload: FeedbackStatusUpdate,
    current_user: dict = Depends(get_current_user)
):
    data, metrics, error = await FeedbackService.update(feedback_id, FeedbackUpdate(status=payload.status))
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)

    return success_response(
        message=f"Feedback status updated to {payload.status}",
        data=data,
        meta=metrics
    )


@router.delete("/{feedback_id}", dependencies=[Depends(require_permission("feedback:submit"))])
async def delete_feedback(
    feedback_id: str,
    current_user: dict = Depends(get_current_user)
):
    if current_user.get("role") not in ["admin", "super_admin"]:
        existing, err = await FeedbackService.get(feedback_id)
        if not existing or err:
            return error_response(message="Feedback not found", status_code=404)

        current_uid = str(current_user.get("id") or current_user.get("_id") or "")
        feedback_uid = str(existing.get("user_id", ""))

        if feedback_uid != current_uid:
            return error_response(
                message="You are not authorized to delete this feedback",
                status_code=403
            )

    success, error = await FeedbackService.delete(feedback_id)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)

    return success_response(message="Feedback deleted successfully", data=[])
