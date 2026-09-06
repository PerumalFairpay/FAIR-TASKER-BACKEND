from fastapi import APIRouter, Depends
from app.models import DepartmentCreate, DepartmentUpdate
from app.services.api.department import DepartmentService
from app.helper.response_helper import success_response, error_response
from app.auth import verify_token

router = APIRouter(prefix="/departments", tags=["departments"], dependencies=[Depends(verify_token)])


@router.post("/create")
async def create_department(department: DepartmentCreate):
    data, error = await DepartmentService.create(department)
    if error:
        return error_response(message=f"Failed to create department: {error}", status_code=500)
    return success_response(message="Department created successfully", data=data, status_code=201)


@router.get("/all")
async def get_departments():
    data, error = await DepartmentService.list()
    if error:
        return error_response(message=f"Failed to fetch departments: {error}", status_code=500)
    return success_response(message="Departments fetched successfully", data=data)


@router.get("/{department_id}")
async def get_department(department_id: str):
    data, error = await DepartmentService.get(department_id)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(message="Department fetched successfully", data=data)


@router.put("/update/{department_id}")
async def update_department(department_id: str, department: DepartmentUpdate):
    data, error = await DepartmentService.update(department_id, department)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(message="Department updated successfully", data=data)


@router.delete("/delete/{department_id}")
async def delete_department(department_id: str):
    success, error = await DepartmentService.delete(department_id)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(message="Department deleted successfully", data=[])
