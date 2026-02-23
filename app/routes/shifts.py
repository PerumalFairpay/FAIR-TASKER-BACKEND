from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from app.crud.repository import repository as repo
from app.models import ShiftCreate, ShiftUpdate
from typing import List
from app.auth import verify_token, get_current_user

router = APIRouter(prefix="/shifts", tags=["shifts"])

@router.post("/", dependencies=[Depends(verify_token)])
async def create_shift(shift: ShiftCreate, current_user: dict = Depends(get_current_user)):
    try:
        # Permission check could go here
        result = await repo.create_shift(shift)
        return JSONResponse(status_code=201, content={"message": "Shift created successfully", "success": True, "data": result})
    except Exception as e:
        return JSONResponse(status_code=500, content={"message": f"Server Error: {str(e)}", "success": False})

@router.get("/", dependencies=[Depends(verify_token)])
async def get_shifts():
    try:
        result = await repo.get_shifts()
        return JSONResponse(status_code=200, content={"message": "Shifts fetched successfully", "success": True, "data": result})
    except Exception as e:
        return JSONResponse(status_code=500, content={"message": f"Server Error: {str(e)}", "success": False})

@router.get("/{shift_id}", dependencies=[Depends(verify_token)])
async def get_shift(shift_id: str):
    try:
        result = await repo.get_shift(shift_id)
        if not result:
            return JSONResponse(status_code=404, content={"message": "Shift not found", "success": False})
        return JSONResponse(status_code=200, content={"message": "Shift fetched successfully", "success": True, "data": result})
    except Exception as e:
        return JSONResponse(status_code=500, content={"message": f"Server Error: {str(e)}", "success": False})

@router.put("/{shift_id}", dependencies=[Depends(verify_token)])
async def update_shift(shift_id: str, shift: ShiftUpdate, current_user: dict = Depends(get_current_user)):
    try:
        result = await repo.update_shift(shift_id, shift)
        if not result:
            return JSONResponse(status_code=404, content={"message": "Shift not found", "success": False})
        return JSONResponse(status_code=200, content={"message": "Shift updated successfully", "success": True, "data": result})
    except Exception as e:
        return JSONResponse(status_code=500, content={"message": f"Server Error: {str(e)}", "success": False})

@router.delete("/{shift_id}", dependencies=[Depends(verify_token)])
async def delete_shift(shift_id: str, current_user: dict = Depends(get_current_user)):
    try:
        result = await repo.delete_shift(shift_id)
        if not result:
            return JSONResponse(status_code=404, content={"message": "Shift not found", "success": False})
        return JSONResponse(status_code=200, content={"message": "Shift deleted successfully", "success": True})
    except Exception as e:
        return JSONResponse(status_code=500, content={"message": f"Server Error: {str(e)}", "success": False})
