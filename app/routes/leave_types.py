from fastapi import APIRouter, Depends
from app.models import LeaveTypeCreate, LeaveTypeUpdate
from app.services.api.leave_type import LeaveTypeService
from app.helper.response_helper import success_response, error_response
from typing import Optional
from app.auth import verify_token

router = APIRouter(prefix="/leave-types", tags=["leave-types"], dependencies=[Depends(verify_token)])


@router.post("/create")
async def create_leave_type(leave_type: LeaveTypeCreate):
    data, error = await LeaveTypeService.create(leave_type)
    if error:
        return error_response(message=f"Failed to create leave type: {error}", status_code=500)
    return success_response(
        message="Leave type created successfully",
        data=data,
        status_code=201
    )


@router.get("/all")
async def get_leave_types(status: Optional[str] = None):
    data, error = await LeaveTypeService.list(status=status)
    if error:
        return error_response(message=f"Failed to fetch leave types: {error}", status_code=500)
    return success_response(
        message="Leave types fetched successfully",
        data=data
    )


@router.get("/{leave_type_id}")
async def get_leave_type(leave_type_id: str):
    data, error = await LeaveTypeService.get(leave_type_id)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(
        message="Leave type fetched successfully",
        data=data
    )


@router.put("/update/{leave_type_id}")
async def update_leave_type(leave_type_id: str, leave_type: LeaveTypeUpdate):
    data, error = await LeaveTypeService.update(leave_type_id, leave_type)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(
        message="Leave type updated successfully",
        data=data
    )


@router.delete("/delete/{leave_type_id}")
async def delete_leave_type(leave_type_id: str):
    success, error = await LeaveTypeService.delete(leave_type_id)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(
        message="Leave type deleted successfully",
        data=[]
    )
