from fastapi import APIRouter, HTTPException, Depends, Form, File, UploadFile
from app.helper.response_helper import success_response, error_response
from app.crud.repository import repository as repo
from app.models import FeedbackCreate, FeedbackUpdate, FeedbackStatusUpdate
from app.helper.file_handler import file_handler
from app.auth import get_current_user, require_permission
from typing import Optional, List

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("/")
async def create_feedback(
    employee_id: str = Form(...),
    employee_name: str = Form(...),
    type: str = Form(...),
    subject: str = Form(...),
    description: str = Form(...),
    priority: str = Form("Medium"),
    attachments: List[UploadFile] = File([]),
    current_user: dict = Depends(require_permission("feedback:submit"))
):
    try:
        attachment_urls = []
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
        
        result = await repo.create_feedback(feedback_data)
        
        return success_response(
            message="Feedback submitted successfully",
            status_code=201,
            data=result["feedback"],
            meta=result["metrics"]
        )
    except Exception as e:
        return error_response(message=str(e), status_code=500)


@router.get("/")
async def get_feedbacks(
    employee_id: Optional[str] = None,
    status: Optional[str] = None,
    current_user: dict = Depends(require_permission("feedback:view"))
):
    try:
        # Anyone with feedback:view permission can see all feedbacks
        # Optionally filter by employee_id if provided as a query param
        result = await repo.get_feedbacks(employee_id=employee_id, status=status)
        return success_response(
            message="Feedbacks fetched successfully",
            data=result["feedbacks"],
            meta=result["metrics"]
        )
    except Exception as e:
        return error_response(message=str(e), status_code=500)


@router.put("/{feedback_id}")
async def update_feedback(
    feedback_id: str,
    status: Optional[str] = Form(None),
    priority: Optional[str] = Form(None),
    type: Optional[str] = Form(None),
    subject: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    attachments: List[UploadFile] = File([]),
    current_user: dict = Depends(require_permission("feedback:submit"))
):
    try:
        # Ownership check: employees can only edit their own feedback
        if current_user.get("role") != "admin":
            existing = await repo.get_feedback(feedback_id)
            if not existing:
                return error_response(message="Feedback not found", status_code=404)
            
            # Fetch employee record to get Mongo ID for accurate comparison
            emp_business_id = current_user.get("employee_no_id")
            employee_record = await repo.db["employees"].find_one({"employee_no_id": emp_business_id})
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
        
        result = await repo.update_feedback(feedback_id, feedback_update)
        
        if not result:
            return error_response(message="Feedback not found", status_code=404)
            
        return success_response(
            message="Feedback updated successfully",
            data=result["feedback"],
            meta=result["metrics"]
        )
    except Exception as e:
        return error_response(message=str(e), status_code=500)


@router.patch("/{feedback_id}/status")
async def update_feedback_status(
    feedback_id: str,
    payload: FeedbackStatusUpdate,
    current_user: dict = Depends(require_permission("feedback:manage"))
):
    try:
        result = await repo.update_feedback(feedback_id, FeedbackUpdate(status=payload.status))
        
        if not result:
            return error_response(message="Feedback not found", status_code=404)
            
        return success_response(
            message=f"Feedback status updated to {payload.status}",
            data=result["feedback"],
            meta=result["metrics"]
        )
    except Exception as e:
        return error_response(message=str(e), status_code=500)


@router.delete("/{feedback_id}")
async def delete_feedback(
    feedback_id: str,
    current_user: dict = Depends(require_permission("feedback:submit"))
):
    try:
        if current_user.get("role") != "admin":
            existing = await repo.get_feedback(feedback_id)
            if not existing:
                return error_response(message="Feedback not found", status_code=404)
            
            # Fetch employee record to get Mongo ID for accurate comparison
            emp_business_id = current_user.get("employee_no_id")
            employee_record = await repo.db["employees"].find_one({"employee_no_id": emp_business_id})
            employee_mongo_id = str(employee_record["_id"]) if employee_record else None

            if existing.get("employee_id") != employee_mongo_id:
                return error_response(
                    message="You are not authorized to delete this feedback",
                    status_code=403
                )

        success = await repo.delete_feedback(feedback_id)
        if not success:
            return error_response(message="Feedback not found", status_code=404)
            
        return success_response(message="Feedback deleted successfully")
    except Exception as e:
        return error_response(message=str(e), status_code=500)
