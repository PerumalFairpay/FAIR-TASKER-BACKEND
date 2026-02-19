from fastapi import APIRouter, HTTPException, Depends
from app.models import PayslipComponentCreate, PayslipComponentUpdate
from app.crud.repository import repository
from app.helper.response_helper import success_response, error_response
from typing import List, Optional

router = APIRouter(prefix="/payslip-components", tags=["Payslip Components"])

@router.post("/", response_description="Create a new payslip component")
async def create_payslip_component(component: PayslipComponentCreate):
    try:
        new_component = await repository.create_payslip_component(component)
        return success_response(
            message="Payslip component created successfully",
            data=new_component
        )
    except Exception as e:
        return error_response(message=str(e), status_code=500)

@router.get("/", response_description="List payslip components")
async def list_payslip_components(type: Optional[str] = None, is_active: Optional[bool] = None):
    try:
        components = await repository.get_payslip_components(type=type, is_active=is_active)
        return success_response(
            message="Payslip components retrieved successfully",
            data=components
        )
    except Exception as e:
        return error_response(message=str(e), status_code=500)

@router.get("/{id}", response_description="Get a single payslip component")
async def get_payslip_component(id: str):
    try:
        component = await repository.get_payslip_component(id)
        if not component:
             return error_response(message="Payslip component not found", status_code=404)
        return success_response(
            message="Payslip component retrieved successfully",
            data=component
        )
    except Exception as e:
        return error_response(message=str(e), status_code=500)

@router.put("/{id}", response_description="Update a payslip component")
async def update_payslip_component(id: str, component: PayslipComponentUpdate):
    try:
        updated_component = await repository.update_payslip_component(id, component)
        if not updated_component:
             return error_response(message="Payslip component not found", status_code=404)
        return success_response(
            message="Payslip component updated successfully",
            data=updated_component
        )
    except Exception as e:
        return error_response(message=str(e), status_code=500)

@router.delete("/{id}", response_description="Delete a payslip component")
async def delete_payslip_component(id: str):
    try:
        deleted = await repository.delete_payslip_component(id)
        if not deleted:
             return error_response(message="Payslip component not found", status_code=404)
        return success_response(
            message="Payslip component deleted successfully",
            data={"id": id}
        )
    except Exception as e:
        return error_response(message=str(e), status_code=500)
