from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import JSONResponse
from app.crud.repository import repository as repo
from app.models import LeaveRequestCreate, LeaveRequestUpdate, LeaveRequestStatusUpdate
from typing import List, Optional
import os
from datetime import datetime
from app.helper.file_handler import save_upload_file
from app.services.leave_email_service import send_leave_application_email, send_leave_status_email

from app.auth import verify_token, get_current_user

router = APIRouter(prefix="/leave-requests", tags=["leave-requests"], dependencies=[Depends(verify_token)])

# --- Routes ---

@router.post("/create")
async def create_leave_request(
    background_tasks: BackgroundTasks,
    employee_id: str = Form(...),
    leave_type_id: str = Form(...),
    leave_duration_type: str = Form(...),
    start_date: str = Form(...),
    end_date: str = Form(...),
    total_days: float = Form(...),
    reason: str = Form(...),
    half_day_session: Optional[str] = Form(None),
    start_session: Optional[str] = Form("Full Day"),
    end_session: Optional[str] = Form("Full Day"),
    start_time: Optional[str] = Form(None),
    end_time: Optional[str] = Form(None),
    attachment: Optional[UploadFile] = File(None)
):
    try:
        # Validation: Past Date Check
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
        except ValueError:
            try:
                start_dt = datetime.fromisoformat(start_date).date()
            except ValueError:
                return JSONResponse(
                    status_code=400,
                    content={"message": "Invalid start date format. Use YYYY-MM-DD.", "success": False}
                )
        
        if start_dt < datetime.now().date():
            return JSONResponse(
                status_code=400,
                content={"message": "Cannot apply for leave on a past date.", "success": False}
            )

        attachment_path = None
        file_type = None
        if attachment:
            attachment_path = await save_upload_file(attachment, "leave")
            file_type = attachment.content_type
            
        leave_request = LeaveRequestCreate(
            employee_id=employee_id,
            leave_type_id=leave_type_id,
            leave_duration_type=leave_duration_type,
            start_date=start_date,
            end_date=end_date,
            total_days=total_days,
            reason=reason,
            half_day_session=half_day_session,
            start_session=start_session,
            end_session=end_session,
            start_time=start_time,
            end_time=end_time,
            status="Pending",
            attachment=attachment_path,
            file_type=file_type
        )
        
        new_request = await repo.create_leave_request(leave_request, attachment_path)
        
        # Send Email Notification
        if new_request and new_request.get("success") is not False:
            emp_details = new_request.get("employee_details")
            lt_details = new_request.get("leave_type_details")
            
            if emp_details and lt_details:
                background_tasks.add_task(
                    send_leave_application_email,
                    employee_name=emp_details.get("name"),
                    employee_email=emp_details.get("email"),
                    leave_type=lt_details.get("name"),
                    start_date=start_date,
                    end_date=end_date,
                    total_days=new_request.get("total_days"),
                    reason=reason
                )

        return JSONResponse(
            status_code=201,
            content={"message": "Leave request submitted successfully", "success": True, "data": new_request}
        )
    except ValueError as e:
        return JSONResponse(
            status_code=400,
            content={"message": str(e), "success": False}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to submit leave request: {str(e)}", "success": False}
        )

@router.get("/all")
async def get_leave_requests(
    id: Optional[str] = None, 
    status: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    try:
        # Check user role
        user_role = current_user.get("role", "").lower()
        
        # If user is an employee, enforce filtering by their own ID
        if user_role == "employee":
            emp_no_id = current_user.get("employee_no_id")
            if emp_no_id:
                # Find the employee mongo ID using the employee_no_id from user record
                employee = await repo.employees.find_one({"employee_no_id": emp_no_id})
                if employee:
                    id = str(employee["_id"])
                else:
                    # If no employee record found, return empty
                    return JSONResponse(
                        status_code=200,
                        content={"message": "Leave requests fetched successfully", "success": True, "data": []}
                    )
            
        requests = await repo.get_leave_requests(id, status)

        response_data = {
            "message": "Leave requests fetched successfully", 
            "success": True, 
            "data": requests
        }

        if user_role == "employee" and id:
            balances = await repo.get_employee_leave_balances(id)
            response_data["metrics"] = balances

        return JSONResponse(
            status_code=200,
            content=response_data
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
    start_session: Optional[str] = Form(None),
    end_session: Optional[str] = Form(None),
    start_time: Optional[str] = Form(None),
    end_time: Optional[str] = Form(None),
    is_compensated: Optional[bool] = Form(None),
    attachment: Optional[UploadFile] = File(None)
):
    try:
        attachment_path = None
        file_type = None
        if attachment:
            attachment_path = await save_upload_file(attachment, "leave")
            file_type = attachment.content_type
            
        update_data = LeaveRequestUpdate(
            employee_id=employee_id,
            leave_type_id=leave_type_id,
            leave_duration_type=leave_duration_type,
            start_date=start_date,
            end_date=end_date,
            total_days=total_days,
            reason=reason,
            status=status,
            half_day_session=half_day_session,
            start_session=start_session,
            end_session=end_session,
            start_time=start_time,
            end_time=end_time,
            is_compensated=is_compensated,
            attachment=attachment_path,
            file_type=file_type
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
    except ValueError as e:
        return JSONResponse(
            status_code=400,
            content={"message": str(e), "success": False}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to update leave request: {str(e)}", "success": False}
        )

@router.patch("/status/{leave_request_id}")
async def update_leave_status(leave_request_id: str, status_update: LeaveRequestStatusUpdate, background_tasks: BackgroundTasks):
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
            
        # Send Email Notification
        emp_details = updated_request.get("employee_details")
        lt_details = updated_request.get("leave_type_details")
        
        if emp_details and lt_details:
            background_tasks.add_task(
                send_leave_status_email,
                employee_name=emp_details.get("name"),
                employee_email=emp_details.get("email"),
                leave_type=lt_details.get("name"),
                start_date=updated_request.get("start_date"),
                end_date=updated_request.get("end_date"),
                status=status_update.status,
                rejection_reason=status_update.rejection_reason
            )

        return JSONResponse(
            status_code=200,
            content={"message": f"Leave request {status_update.status} successfully", "success": True, "data": updated_request}
        )
    except ValueError as e:
        return JSONResponse(
            status_code=400,
            content={"message": str(e), "success": False}
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
