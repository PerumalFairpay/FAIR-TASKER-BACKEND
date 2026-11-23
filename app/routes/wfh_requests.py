from fastapi import APIRouter, Depends
from typing import Optional
from app.models import WFHRequestCreate, WFHRequestStatusUpdate
from app.services.api.wfh_request import WFHRequestService
from app.helper.response_helper import success_response, error_response
from app.auth import verify_token, get_current_user

router = APIRouter(prefix="/wfh-requests", tags=["wfh-requests"], dependencies=[Depends(verify_token)])


@router.post("/create")
async def create_wfh_request(
    request: WFHRequestCreate,
    current_user: dict = Depends(get_current_user)
):
    employee_id = current_user.get("employee_id") or current_user.get("id")
    request.employee_id = employee_id

    data, error = await WFHRequestService.create(request)
    if error:
        status_code = 400 if ("already exists" in error.lower() or "cannot" in error.lower() or "invalid" in error.lower()) else 500
        return error_response(message=error, status_code=status_code)

    return success_response(message="Work From Home request submitted successfully", data=data, status_code=201)


@router.get("/all")
async def get_wfh_requests(
    id: Optional[str] = None,
    status: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    role_val = current_user.get("role")
    user_role = (role_val.get("name", "") if isinstance(role_val, dict) else str(role_val or "")).lower()

    if user_role == "employee":
        id = current_user.get("employee_id") or current_user.get("id")

    result, error = await WFHRequestService.get_all(employee_id=id, status=status)

    if error:
        return error_response(message=error, status_code=500)

    return success_response(
        message="WFH requests retrieved successfully",
        data=result.get("data", []),
        meta=result.get("metrics", {})
    )




@router.get("/{wfh_id}")
async def get_wfh_request_by_id(
    wfh_id: str,
    current_user: dict = Depends(get_current_user)
):
    data, error = await WFHRequestService.get_by_id(wfh_id)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)

    return success_response(message="WFH request details retrieved successfully", data=data)


@router.patch("/status/{wfh_id}")
async def update_wfh_status(
    wfh_id: str,
    status_update: WFHRequestStatusUpdate,
    current_user: dict = Depends(get_current_user)
):
    role_val = current_user.get("role")
    user_role = (role_val.get("name", "") if isinstance(role_val, dict) else str(role_val or "")).lower()
    user_perms = current_user.get("permissions", [])

    is_admin_or_hr = user_role in ["admin", "super_admin", "hr"]
    has_approval_perm = "leave:access" in user_perms or "attendance:access" in user_perms

    if not is_admin_or_hr and not has_approval_perm:
        return error_response(message="Only administrators or authorized managers can approve or reject WFH requests.", status_code=403)

    reviewer_name = current_user.get("name") or current_user.get("email") or str(current_user.get("_id"))
    data, error = await WFHRequestService.update_status(
        wfh_id=wfh_id,
        status_update=status_update,
        reviewed_by=reviewer_name
    )
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 400
        return error_response(message=error, status_code=status_code)

    msg = f"WFH request {status_update.status} successfully"
    if status_update.status == "Approved":
        msg += " and employee work mode updated to Remote."

    return success_response(message=msg, data=data)


@router.delete("/delete/{wfh_id}")
async def delete_wfh_request(
    wfh_id: str,
    current_user: dict = Depends(get_current_user)
):
    role_val = current_user.get("role")
    user_role = (role_val.get("name", "") if isinstance(role_val, dict) else str(role_val or "")).lower()
    user_id = str(current_user.get("_id", ""))

    success, error = await WFHRequestService.delete(wfh_id=wfh_id, user_role=user_role, user_id=user_id)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 400
        return error_response(message=error, status_code=status_code)

    return success_response(message="WFH request removed successfully", data=[])
