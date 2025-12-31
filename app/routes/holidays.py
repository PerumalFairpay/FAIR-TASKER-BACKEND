from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from app.crud.repository import repository as repo
from app.models import HolidayCreate, HolidayUpdate
from typing import List

from app.auth import verify_token

router = APIRouter(prefix="/holidays", tags=["holidays"], dependencies=[Depends(verify_token)])

@router.post("/create")
async def create_holiday(holiday: HolidayCreate):
    try:
        new_holiday = await repo.create_holiday(holiday)
        return JSONResponse(
            status_code=201,
            content={"message": "Holiday created successfully", "success": True, "data": new_holiday}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to create holiday: {str(e)}", "success": False}
        )

@router.get("/all")
async def get_holidays():
    try:
        holidays = await repo.get_holidays()
        return JSONResponse(
            status_code=200,
            content={"message": "Holidays fetched successfully", "success": True, "data": holidays}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to fetch holidays: {str(e)}", "success": False}
        )

@router.get("/{holiday_id}")
async def get_holiday(holiday_id: str):
    try:
        holiday = await repo.get_holiday(holiday_id)
        if not holiday:
            return JSONResponse(
                status_code=404,
                content={"message": "Holiday not found", "success": False}
            )
        return JSONResponse(
            status_code=200,
            content={"message": "Holiday fetched successfully", "success": True, "data": holiday}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to fetch holiday: {str(e)}", "success": False}
        )

@router.put("/update/{holiday_id}")
async def update_holiday(holiday_id: str, holiday: HolidayUpdate):
    try:
        updated_holiday = await repo.update_holiday(holiday_id, holiday)
        if not updated_holiday:
            return JSONResponse(
                status_code=404,
                content={"message": "Holiday not found", "success": False}
            )
        return JSONResponse(
            status_code=200,
            content={"message": "Holiday updated successfully", "success": True, "data": updated_holiday}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to update holiday: {str(e)}", "success": False}
        )

@router.delete("/delete/{holiday_id}")
async def delete_holiday(holiday_id: str):
    try:
        success = await repo.delete_holiday(holiday_id)
        if not success:
            return JSONResponse(
                status_code=404,
                content={"message": "Holiday not found", "success": False}
            )
        return JSONResponse(
            status_code=200,
            content={"message": "Holiday deleted successfully", "success": True}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to delete holiday: {str(e)}", "success": False}
        )
