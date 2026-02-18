from fastapi import APIRouter, HTTPException, Depends, Form
from app.helper.response_helper import success_response, error_response
from app.crud.repository import repository as repo
from app.models import FeedbackCreate, FeedbackUpdate
from typing import Optional, List
from app.auth import verify_token

router = APIRouter(prefix="/feedback", tags=["feedback"], dependencies=[Depends(verify_token)])


@router.post("/")
async def create_feedback(
    user_id: str = Form(...),
    user_name: str = Form(...),
    type: str = Form(...),
    subject: str = Form(...),
    description: str = Form(...),
    priority: str = Form("Medium"),
    attachments: Optional[List[str]] = Form(None)
):
    try:
        feedback_data = FeedbackCreate(
            user_id=user_id,
            user_name=user_name,
            type=type,
            subject=subject,
            description=description,
            priority=priority,
            attachments=attachments or []
        )
        
        new_feedback = await repo.create_feedback(feedback_data)
        
        return success_response(
            message="Feedback submitted successfully",
            status_code=201,
            data=new_feedback
        )
    except Exception as e:
        return error_response(message=str(e), status_code=500)


@router.get("/")
async def get_feedbacks(user_id: Optional[str] = None, status: Optional[str] = None):
    try:
        feedbacks = await repo.get_feedbacks(user_id=user_id, status=status)
        return success_response(
            message="Feedbacks fetched successfully",
            data=feedbacks
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
    attachments: Optional[List[str]] = Form(None)
):
    try:
        feedback_update = FeedbackUpdate(
            status=status,
            priority=priority,
            type=type,
            subject=subject,
            description=description,
            attachments=attachments
        )
        
        updated_feedback = await repo.update_feedback(feedback_id, feedback_update)
        
        if not updated_feedback:
            return error_response(message="Feedback not found", status_code=404)
            
        return success_response(
            message="Feedback updated successfully",
            data=updated_feedback
        )
    except Exception as e:
        return error_response(message=str(e), status_code=500)


@router.delete("/{feedback_id}")
async def delete_feedback(feedback_id: str):
    try:
        success = await repo.delete_feedback(feedback_id)
        if not success:
            return error_response(message="Feedback not found", status_code=404)
            
        return success_response(message="Feedback deleted successfully")
    except Exception as e:
        return error_response(message=str(e), status_code=500)
