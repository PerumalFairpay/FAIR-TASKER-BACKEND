from fastapi import APIRouter, HTTPException, Body
from fastapi.responses import JSONResponse
from app.crud.repository import repository as repo
from app.models import DepartmentCreate, DepartmentUpdate
from typing import List

router = APIRouter(prefix="/departments", tags=["departments"])

@router.post("/create")
async def create_department(department: DepartmentCreate):
    try:
        new_department = await repo.create_department(department)
        return JSONResponse(
            status_code=201,
            content={"message": "Department created successfully", "success": True, "data": new_department}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to create department: {str(e)}", "success": False}
        )

@router.get("/all")
async def get_departments():
    try:
        departments = await repo.get_departments()
        return JSONResponse(
            status_code=200,
            content={"message": "Departments fetched successfully", "success": True, "data": departments}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to fetch departments: {str(e)}", "success": False}
        )

@router.get("/{department_id}")
async def get_department(department_id: str):
    try:
        department = await repo.get_department(department_id)
        if not department:
            return JSONResponse(
                status_code=404,
                content={"message": "Department not found", "success": False}
            )
        return JSONResponse(
            status_code=200,
            content={"message": "Department fetched successfully", "success": True, "data": department}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to fetch department: {str(e)}", "success": False}
        )

@router.put("/update/{department_id}")
async def update_department(department_id: str, department: DepartmentUpdate):
    try:
        updated_department = await repo.update_department(department_id, department)
        if not updated_department:
            return JSONResponse(
                status_code=404,
                content={"message": "Department not found", "success": False}
            )
        return JSONResponse(
            status_code=200,
            content={"message": "Department updated successfully", "success": True, "data": updated_department}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to update department: {str(e)}", "success": False}
        )

@router.delete("/delete/{department_id}")
async def delete_department(department_id: str):
    try:
        success = await repo.delete_department(department_id)
        if not success:
            return JSONResponse(
                status_code=404,
                content={"message": "Department not found", "success": False}
            )
        return JSONResponse(
            status_code=200,
            content={"message": "Department deleted successfully", "success": True}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to delete department: {str(e)}", "success": False}
        )
