from fastapi import APIRouter, Depends
from app.models import PayslipComponentCreate, PayslipComponentUpdate
from app.services.api.payslip_component import PayslipComponentService
from app.helper.response_helper import success_response, error_response
from typing import Optional

router = APIRouter(prefix="/payslip-components", tags=["Payslip Components"])


@router.post("/", response_description="Create a new payslip component")
async def create_payslip_component(component: PayslipComponentCreate):
    data, error = await PayslipComponentService.create(component)
    if error:
        return error_response(message=f"Failed to create payslip component: {error}", status_code=500)
    return success_response(
        message="Payslip component created successfully",
        data=data,
        status_code=201
    )


@router.get("/", response_description="List payslip components")
async def list_payslip_components(type: Optional[str] = None, is_active: Optional[bool] = None):
    data, error = await PayslipComponentService.list(type=type, is_active=is_active)
    if error:
        return error_response(message=f"Failed to fetch payslip components: {error}", status_code=500)
    return success_response(
        message="Payslip components retrieved successfully",
        data=data
    )


@router.get("/{id}", response_description="Get a single payslip component")
async def get_payslip_component(id: str):
    data, error = await PayslipComponentService.get(id)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(
        message="Payslip component retrieved successfully",
        data=data
    )


@router.put("/{id}", response_description="Update a payslip component")
async def update_payslip_component(id: str, component: PayslipComponentUpdate):
    data, error = await PayslipComponentService.update(id, component)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(
        message="Payslip component updated successfully",
        data=data
    )


@router.delete("/{id}", response_description="Delete a payslip component")
async def delete_payslip_component(id: str):
    success, error = await PayslipComponentService.delete(id)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(
        message="Payslip component deleted successfully",
        data=[]
    )
