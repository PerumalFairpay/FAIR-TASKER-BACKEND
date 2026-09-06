from fastapi import APIRouter, Depends, Form, File, UploadFile
from typing import Optional, List
from app.helper.response_helper import success_response, error_response
from app.models import FeedbackCreate, FeedbackUpdate, FeedbackStatusUpdate
from app.services.api.feedback import FeedbackService
from app.database import employees_collection
from app.helper.file_handler import file_handler
from app.auth import get_current_user, require_permission

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("/", dependencies=[Depends(require_permission("feedback:submit"))])
async def create_feedback(
    employee_id: str = Form(...),
    employee_name: str = Form(...),
    type: str = Form(...),
    subject: str = Form(...),
    description: str = Form(...),
    priority: str = Form("Medium"),
    attachments: List[UploadFile] = File([]),
    current_user: dict = Depends(get_current_user)
):
    attachment_urls = []
    if attachments:
        for file in attachments:
            uploaded = await file_handler.upload_file(file, subfolder="feedback")
            attachment_urls.append({
                "document_name": file.filename,
                "document_proof": uploaded["url"],
                "file_type": file.content_type
            })

    feedback_data = FeedbackCreate(
        employee_id=employee_id,
        employee_name=employee_name,
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
    employee_id: Optional[str] = None,
    status: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    data, metrics, error = await FeedbackService.list(employee_id=employee_id, status=status)
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
    status: Optional[str] = Form(None),
    priority: Optional[str] = Form(None),
    type: Optional[str] = Form(None),
    subject: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    attachments: List[UploadFile] = File([]),
    current_user: dict = Depends(get_current_user)
):
    # Ownership check: employees can only edit their own feedback
    if current_user.get("role") not in ["admin", "super_admin"]:
        existing, err = await FeedbackService.get(feedback_id)
        if not existing or err:
            return error_response(message="Feedback not found", status_code=404)

        emp_business_id = current_user.get("employee_no_id")
        employee_record = await employees_collection.find_one({"employee_no_id": emp_business_id, "is_deleted": {"$ne": True}})
        employee_mongo_id = str(employee_record["_id"]) if employee_record else None

        if existing.get("employee_id") != employee_mongo_id:
            return error_response(
                message="You are not authorized to edit this feedback",
                status_code=403
            )

    attachment_urls = []
    if attachments:
        for file in attachments:
            uploaded = await file_handler.upload_file(file, subfolder="feedback")
            attachment_urls.append({
                "document_name": file.filename,
                "document_proof": uploaded["url"],
                "file_type": file.content_type
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

        emp_business_id = current_user.get("employee_no_id")
        employee_record = await employees_collection.find_one({"employee_no_id": emp_business_id, "is_deleted": {"$ne": True}})
        employee_mongo_id = str(employee_record["_id"]) if employee_record else None

        if existing.get("employee_id") != employee_mongo_id:
            return error_response(
                message="You are not authorized to delete this feedback",
                status_code=403
            )

    success, error = await FeedbackService.delete(feedback_id)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)

    return success_response(message="Feedback deleted successfully", data=[])
