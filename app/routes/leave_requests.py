from fastapi import APIRouter, Depends, UploadFile, File, Form, BackgroundTasks
from typing import Optional
from datetime import datetime
from app.models import LeaveRequestCreate, LeaveRequestUpdate, LeaveRequestStatusUpdate
from app.services.api.leave_request import LeaveRequestService
from app.database import employees_collection
from app.helper.response_helper import success_response, error_response
from app.helper.file_handler import save_upload_file
from app.services.leave_email_service import send_leave_application_email, send_leave_status_email
from app.auth import verify_token, get_current_user, require_permission

router = APIRouter(prefix="/leave-requests", tags=["leave-requests"], dependencies=[Depends(verify_token)])


@router.post("/create", dependencies=[Depends(require_permission("leave:submit"))])
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
        start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
    except ValueError:
        try:
            start_dt = datetime.fromisoformat(start_date).date()
        except ValueError:
            return error_response(message="Invalid start date format. Use YYYY-MM-DD.", status_code=400)

    if start_dt < datetime.now().date():
        return error_response(message="Cannot apply for leave on a past date.", status_code=400)

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

    data, error = await LeaveRequestService.create(leave_request, attachment_path)
    if error:
        status_code = 400 if ("already exists" in error.lower() or "cannot" in error.lower() or "limit" in error.lower() or "insufficient" in error.lower() or "prior approval" in error.lower()) else 500
        return error_response(message=error, status_code=status_code)

    if data:
        emp_details = data.get("employee_details")
        lt_details = data.get("leave_type_details")

        if emp_details and lt_details:
            background_tasks.add_task(
                send_leave_application_email,
                employee_name=emp_details.get("name"),
                employee_email=emp_details.get("email"),
                leave_type=lt_details.get("name"),
                start_date=start_date,
                end_date=end_date,
                total_days=data.get("total_days"),
                reason=reason
            )

    return success_response(message="Leave request submitted successfully", data=data, status_code=201)


@router.get("/all", dependencies=[Depends(require_permission("leave:view"))])
async def get_leave_requests(
    id: Optional[str] = None,
    status: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    user_role = current_user.get("role", "").lower()

    if user_role == "employee":
        emp_no_id = current_user.get("employee_no_id")
        if emp_no_id:
            employee = await employees_collection.find_one({"employee_no_id": emp_no_id, "is_deleted": {"$ne": True}})
            if employee:
                id = str(employee["_id"])
            else:
                return success_response(message="Leave requests fetched successfully", data=[])

    data, error = await LeaveRequestService.list(employee_id=id, status=status)
    if error:
        return error_response(message=f"Failed to fetch leave requests: {error}", status_code=500)

    meta = None
    if user_role == "employee" and id:
        balances = await LeaveRequestService.get_employee_leave_balances(id)
        meta = balances

    return success_response(message="Leave requests fetched successfully", data=data, meta=meta)


@router.get("/{leave_request_id}", dependencies=[Depends(require_permission("leave:view"))])
async def get_leave_request(leave_request_id: str):
    data, error = await LeaveRequestService.get(leave_request_id)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(message="Leave request fetched successfully", data=data)


@router.put("/update/{leave_request_id}", dependencies=[Depends(require_permission("leave:submit"))])
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

    data, error = await LeaveRequestService.update(leave_request_id, update_data, attachment_path)
    if error:
        if "not found" in error.lower() or "invalid" in error.lower():
            status_code = 404
        elif "already exists" in error.lower() or "cannot" in error.lower():
            status_code = 400
        else:
            status_code = 500
        return error_response(message=error, status_code=status_code)

    return success_response(message="Leave request updated successfully", data=data)


@router.patch("/status/{leave_request_id}", dependencies=[Depends(require_permission("leave:manage"))])
async def update_leave_status(
    leave_request_id: str,
    status_update: LeaveRequestStatusUpdate,
    background_tasks: BackgroundTasks
):
    update_data = LeaveRequestUpdate(
        status=status_update.status,
        rejection_reason=status_update.rejection_reason
    )
    data, error = await LeaveRequestService.update(leave_request_id, update_data)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)

    emp_details = data.get("employee_details")
    lt_details = data.get("leave_type_details")

    if emp_details and lt_details:
        background_tasks.add_task(
            send_leave_status_email,
            employee_name=emp_details.get("name"),
            employee_email=emp_details.get("email"),
            leave_type=lt_details.get("name"),
            start_date=data.get("start_date"),
            end_date=data.get("end_date"),
            status=status_update.status,
            rejection_reason=status_update.rejection_reason
        )

    return success_response(
        message=f"Leave request {status_update.status} successfully",
        data=data
    )


@router.delete("/delete/{leave_request_id}", dependencies=[Depends(require_permission("leave:submit"))])
async def delete_leave_request(leave_request_id: str):
    success, error = await LeaveRequestService.delete(leave_request_id)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(message="Leave request deleted successfully", data=[])
