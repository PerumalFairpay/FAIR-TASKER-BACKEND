from fastapi import APIRouter, Depends, Query, Path
from fastapi.responses import JSONResponse
from typing import Optional
from app.models import WFHRequestCreate, WFHRequestStatusUpdate
from app.services.api.wfh_request import WFHRequestService
from app.helper.response_helper import success_response, error_response
from app.auth import verify_token, get_current_user
from app.utils import normalize

router = APIRouter(
    prefix="/wfh-requests",
    tags=["wfh-requests"],
    dependencies=[Depends(verify_token)]
)


@router.post(
    "/create",
    summary="Submit Work From Home Request",
    description="Allows an authenticated employee to apply for Work From Home (WFH). The employee ID is automatically extracted from their active login token. Prevents past dates and overlapping requests.",
    status_code=201
)
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


@router.get(
    "/all",
    summary="List WFH Requests with Metrics",
    description="Retrieves a list of WFH requests along with summary metrics (total, pending, approved, rejected). If called by an Employee, it automatically restricts results to their own requests. Admins and HR can see all or filter by employee.",
)
async def get_wfh_requests(
    id: Optional[str] = Query(None, description="Optional employee MongoDB ObjectId to filter requests (Admin/HR only)"),
    status: Optional[str] = Query(None, description="Filter by status: 'All', 'Pending', 'Approved', 'Rejected'"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Items per page"),
    current_user: dict = Depends(get_current_user)
):
    role_val = current_user.get("role")
    user_role = (role_val.get("name", "") if isinstance(role_val, dict) else str(role_val or "")).lower()

    if user_role == "employee":
        id = current_user.get("employee_id") or current_user.get("id")

    result, error = await WFHRequestService.get_all(
        employee_id=id,
        status=status,
        page=page,
        limit=limit
    )
    if error:
        return error_response(message=error, status_code=500)

    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "message": "WFH requests retrieved successfully",
            "data": normalize(result.get("data", [])),
            "meta": normalize(result.get("meta", {})),
            "metrics": normalize(result.get("metrics", {}))
        }
    )


@router.get(
    "/{wfh_id}",
    summary="Get WFH Request Details",
    description="Fetches full details of a single Work From Home request by its ID, including employee details and review history."
)
async def get_wfh_request_by_id(
    wfh_id: str = Path(..., description="The MongoDB ObjectId of the WFH request", example="6741b61c8a149b25d0123456"),
    current_user: dict = Depends(get_current_user)
):
    data, error = await WFHRequestService.get_by_id(wfh_id)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)

    return success_response(message="WFH request details retrieved successfully", data=data)


@router.patch(
    "/status/{wfh_id}",
    summary="Review & Approve/Reject WFH Request",
    description="Admin/HR action to Approve or Reject a WFH request. **CRITICAL SIDE-EFFECT**: When approved, the employee's `work_mode` in `employees_collection` is automatically changed to `'Remote'`."
)
async def update_wfh_status(
    wfh_id: str = Path(..., description="The MongoDB ObjectId of the WFH request", example="6741b61c8a149b25d0123456"),
    status_update: WFHRequestStatusUpdate = ...,
    current_user: dict = Depends(get_current_user)
):
    role_val = current_user.get("role")
    user_role = (role_val.get("name", "") if isinstance(role_val, dict) else str(role_val or "")).lower()
    user_perms = current_user.get("permissions", [])

    is_admin_or_hr = user_role in ["admin", "super_admin", "hr"]
    has_approval_perm = "wfh:access" in user_perms or "leave:access" in user_perms or "attendance:access" in user_perms

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


@router.delete(
    "/delete/{wfh_id}",
    summary="Delete / Cancel WFH Request",
    description="Allows employees to cancel/withdraw their own pending WFH request, or enables Admins to remove any WFH request record."
)
async def delete_wfh_request(
    wfh_id: str = Path(..., description="The MongoDB ObjectId of the WFH request to delete", example="6741b61c8a149b25d0123456"),
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
