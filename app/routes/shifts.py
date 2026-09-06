from fastapi import APIRouter, Depends
from app.models import ShiftCreate, ShiftUpdate
from app.services.api.shift import ShiftService
from app.helper.response_helper import success_response, error_response
from app.auth import verify_token, get_current_user

router = APIRouter(prefix="/shifts", tags=["shifts"])


@router.post("/", dependencies=[Depends(verify_token)])
async def create_shift(shift: ShiftCreate, current_user: dict = Depends(get_current_user)):
    data, error = await ShiftService.create(shift)
    if error:
        return error_response(message=f"Failed to create shift: {error}", status_code=500)
    return success_response(message="Shift created successfully", data=data, status_code=201)


@router.get("/", dependencies=[Depends(verify_token)])
async def get_shifts():
    data, error = await ShiftService.list()
    if error:
        return error_response(message=f"Failed to fetch shifts: {error}", status_code=500)
    return success_response(message="Shifts fetched successfully", data=data)


@router.get("/{shift_id}", dependencies=[Depends(verify_token)])
async def get_shift(shift_id: str):
    data, error = await ShiftService.get(shift_id)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(message="Shift fetched successfully", data=data)


@router.put("/{shift_id}", dependencies=[Depends(verify_token)])
async def update_shift(shift_id: str, shift: ShiftUpdate, current_user: dict = Depends(get_current_user)):
    data, error = await ShiftService.update(shift_id, shift)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(message="Shift updated successfully", data=data)


@router.delete("/{shift_id}", dependencies=[Depends(verify_token)])
async def delete_shift(shift_id: str, current_user: dict = Depends(get_current_user)):
    success, error = await ShiftService.delete(shift_id)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(message="Shift deleted successfully", data=[])
