from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from app.crud.repository import repository as repo
from app.models import LeaveTypeCreate, LeaveTypeUpdate
from typing import List

router = APIRouter(prefix="/leave-types", tags=["leave-types"])

@router.post("/create")
async def create_leave_type(leave_type: LeaveTypeCreate):
    try:
        new_leave_type = await repo.create_leave_type(leave_type)
        return JSONResponse(
            status_code=201,
            content={"message": "Leave type created successfully", "success": True, "data": new_leave_type}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to create leave type: {str(e)}", "success": False}
        )

@router.get("/all")
async def get_leave_types():
    try:
        leave_types = await repo.get_leave_types()
        return JSONResponse(
            status_code=200,
            content={"message": "Leave types fetched successfully", "success": True, "data": leave_types}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to fetch leave types: {str(e)}", "success": False}
        )

@router.get("/{leave_type_id}")
async def get_leave_type(leave_type_id: str):
    try:
        leave_type = await repo.get_leave_type(leave_type_id)
        if not leave_type:
            return JSONResponse(
                status_code=404,
                content={"message": "Leave type not found", "success": False}
            )
        return JSONResponse(
            status_code=200,
            content={"message": "Leave type fetched successfully", "success": True, "data": leave_type}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to fetch leave type: {str(e)}", "success": False}
        )

@router.put("/update/{leave_type_id}")
async def update_leave_type(leave_type_id: str, leave_type: LeaveTypeUpdate):
    try:
        updated_leave_type = await repo.update_leave_type(leave_type_id, leave_type)
        if not updated_leave_type:
            return JSONResponse(
                status_code=404,
                content={"message": "Leave type not found", "success": False}
            )
        return JSONResponse(
            status_code=200,
            content={"message": "Leave type updated successfully", "success": True, "data": updated_leave_type}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to update leave type: {str(e)}", "success": False}
        )

@router.delete("/delete/{leave_type_id}")
async def delete_leave_type(leave_type_id: str):
    try:
        success = await repo.delete_leave_type(leave_type_id)
        if not success:
            return JSONResponse(
                status_code=404,
                content={"message": "Leave type not found", "success": False}
            )
        return JSONResponse(
            status_code=200,
            content={"message": "Leave type deleted successfully", "success": True}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to delete leave type: {str(e)}", "success": False}
        )
