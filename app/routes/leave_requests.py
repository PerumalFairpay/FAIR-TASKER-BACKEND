from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import JSONResponse
from app.crud.repository import repository as repo
from app.models import LeaveRequestCreate, LeaveRequestUpdate, LeaveRequestStatusUpdate
from typing import List, Optional
import os
from app.helper.file_handler import save_upload_file

from app.auth import verify_token

router = APIRouter(prefix="/leave-requests", tags=["leave-requests"], dependencies=[Depends(verify_token)])

@router.post("/create")
async def create_leave_request(
    employee_id: str = Form(...),
    leave_type_id: str = Form(...),
    leave_duration_type: str = Form(...),
    start_date: str = Form(...),
    end_date: str = Form(...),
    total_days: float = Form(...),
    reason: str = Form(...),
    half_day_session: Optional[str] = Form(None),
    attachment: Optional[UploadFile] = File(None)
):
    try:
        attachment_path = None
        if attachment:
            attachment_path = await save_upload_file(attachment, "leave_attachments")
            
        leave_request = LeaveRequestCreate(
            employee_id=employee_id,
            leave_type_id=leave_type_id,
            leave_duration_type=leave_duration_type,
            start_date=start_date,
            end_date=end_date,
            total_days=total_days,
            reason=reason,
            half_day_session=half_day_session,
            status="Pending"
        )
        
        new_request = await repo.create_leave_request(leave_request, attachment_path)
        return JSONResponse(
            status_code=201,
            content={"message": "Leave request submitted successfully", "success": True, "data": new_request}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to submit leave request: {str(e)}", "success": False}
        )

@router.get("/all")
async def get_leave_requests(employee_id: Optional[str] = None):
    try:
        requests = await repo.get_leave_requests(employee_id)
        return JSONResponse(
            status_code=200,
            content={"message": "Leave requests fetched successfully", "success": True, "data": requests}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to fetch leave requests: {str(e)}", "success": False}
        )

@router.get("/{leave_request_id}")
async def get_leave_request(leave_request_id: str):
    try:
        request = await repo.get_leave_request(leave_request_id)
        if not request:
            return JSONResponse(
                status_code=404,
                content={"message": "Leave request not found", "success": False}
            )
        return JSONResponse(
            status_code=200,
            content={"message": "Leave request fetched successfully", "success": True, "data": request}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to fetch leave request: {str(e)}", "success": False}
        )

@router.put("/update/{leave_request_id}")
async def update_leave_request(
    leave_request_id: str,
    employee_id: Optional[str] = Form(None),
    leave_type_id: Optional[str] = Form(None),
    leave_duration_type: Optional[str] = Form(None),
    start_date: Optional[str] = Form(None),
    end_date: Optional[str] = Form(None),
    total_days: Optional[float] = Form(None),
    reason: Optional[str] = Form(None),
    status: Optional[str] = Form(None),
    half_day_session: Optional[str] = Form(None),
    attachment: Optional[UploadFile] = File(None)
):
    try:
        attachment_path = None
        if attachment:
            attachment_path = await save_upload_file(attachment, "leave_attachments")
            
        update_data = LeaveRequestUpdate(
            employee_id=employee_id,
            leave_type_id=leave_type_id,
            leave_duration_type=leave_duration_type,
            start_date=start_date,
            end_date=end_date,
            total_days=total_days,
            reason=reason,
            status=status,
            half_day_session=half_day_session
        )
        
        updated_request = await repo.update_leave_request(leave_request_id, update_data, attachment_path)
        if not updated_request:
            return JSONResponse(
                status_code=404,
                content={"message": "Leave request not found", "success": False}
            )
        return JSONResponse(
            status_code=200,
            content={"message": "Leave request updated successfully", "success": True, "data": updated_request}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to update leave request: {str(e)}", "success": False}
        )

@router.patch("/status/{leave_request_id}")
async def update_leave_status(leave_request_id: str, status_update: LeaveRequestStatusUpdate):
    try:
        update_data = LeaveRequestUpdate(
            status=status_update.status,
            rejection_reason=status_update.rejection_reason
        )
        updated_request = await repo.update_leave_request(leave_request_id, update_data)
        if not updated_request:
            return JSONResponse(
                status_code=404,
                content={"message": "Leave request not found", "success": False}
            )
        return JSONResponse(
            status_code=200,
            content={"message": f"Leave request {status_update.status} successfully", "success": True, "data": updated_request}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to update leave status: {str(e)}", "success": False}
        )

@router.delete("/delete/{leave_request_id}")
async def delete_leave_request(leave_request_id: str):
    try:
        success = await repo.delete_leave_request(leave_request_id)
        if not success:
            return JSONResponse(
                status_code=404,
                content={"message": "Leave request not found", "success": False}
            )
        return JSONResponse(
            status_code=200,
            content={"message": "Leave request deleted successfully", "success": True}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to delete leave request: {str(e)}", "success": False}
        )
