from fastapi import APIRouter, HTTPException, Body, Depends
from app.helper.response_helper import success_response, error_response
from app.crud.repository import repository as repo
from app.models import DepartmentCreate, DepartmentUpdate
from typing import List
from app.auth import verify_token, require_permission

router = APIRouter(prefix="/departments", tags=["departments"], dependencies=[Depends(verify_token)])

@router.post("/create", dependencies=[Depends(require_permission("department:submit"))])
async def create_department(department: DepartmentCreate):
    try:
        new_department = await repo.create_department(department)
        return success_response(
            message="Department created successfully",
            status_code=201,
            data=new_department
        )
    except Exception as e:
        return error_response(
            message=f"Failed to create department: {str(e)}",
            status_code=500
        )

@router.get("/all", dependencies=[Depends(require_permission("department:view"))])
async def get_departments():
    try:
        departments = await repo.get_departments()
        return success_response(
            message="Departments fetched successfully",
            data=departments
        )
    except Exception as e:
        return error_response(
            message=f"Failed to fetch departments: {str(e)}",
            status_code=500
        )

@router.get("/{department_id}", dependencies=[Depends(require_permission("department:view"))])
async def get_department(department_id: str):
    try:
        department = await repo.get_department(department_id)
        if not department:
            return error_response(
                message="Department not found",
                status_code=404
            )
        return success_response(
            message="Department fetched successfully",
            data=department
        )
    except Exception as e:
        return error_response(
            message=f"Failed to fetch department: {str(e)}",
            status_code=500
        )

@router.put("/update/{department_id}", dependencies=[Depends(require_permission("department:submit"))])
async def update_department(department_id: str, department: DepartmentUpdate):
    try:
        updated_department = await repo.update_department(department_id, department)
        if not updated_department:
            return error_response(
                message="Department not found",
                status_code=404
            )
        return success_response(
            message="Department updated successfully",
            data=updated_department
        )
    except Exception as e:
        return error_response(
            message=f"Failed to update department: {str(e)}",
            status_code=500
        )

@router.delete("/delete/{department_id}", dependencies=[Depends(require_permission("department:submit"))])
async def delete_department(department_id: str):
    try:
        success = await repo.delete_department(department_id)
        if not success:
            return error_response(
                message="Department not found",
                status_code=404
            )
        return success_response(
            message="Department deleted successfully"
        )
    except Exception as e:
        return error_response(
            message=f"Failed to delete department: {str(e)}",
            status_code=500
        )
