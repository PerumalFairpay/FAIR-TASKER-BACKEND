from fastapi import APIRouter, Depends
from app.models import HolidayCreate, HolidayUpdate
from app.services.api.holiday import HolidayService
from app.helper.response_helper import success_response, error_response
from app.auth import verify_token

router = APIRouter(prefix="/holidays", tags=["holidays"], dependencies=[Depends(verify_token)])

@router.post("/create")
async def create_holiday(holiday: HolidayCreate):
    data, error = await HolidayService.create(holiday)
    if error:
        return error_response(message=f"Failed to create holiday: {error}", status_code=500)
    return success_response(message="Holiday created successfully", data=data, status_code=201)

@router.get("/all")
async def get_holidays():
    data, error = await HolidayService.list()
    if error:
        return error_response(message=f"Failed to fetch holidays: {error}", status_code=500)
    return success_response(message="Holidays fetched successfully", data=data)

@router.get("/{holiday_id}")
async def get_holiday(holiday_id: str):
    data, error = await HolidayService.get(holiday_id)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(message="Holiday fetched successfully", data=data)

@router.put("/update/{holiday_id}")
async def update_holiday(holiday_id: str, holiday: HolidayUpdate):
    data, error = await HolidayService.update(holiday_id, holiday)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(message="Holiday updated successfully", data=data)

@router.delete("/delete/{holiday_id}")
async def delete_holiday(holiday_id: str):
    success, error = await HolidayService.delete(holiday_id)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(message="Holiday deleted successfully", data=[])

