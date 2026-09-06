from fastapi import APIRouter, Depends
from app.models import EmployeeChecklistTemplateCreate, EmployeeChecklistTemplateUpdate
from app.services.api.checklist_template import ChecklistTemplateService
from app.helper.response_helper import success_response, error_response
from app.auth import verify_token

router = APIRouter(prefix="/checklist-templates", tags=["checklist-templates"], dependencies=[Depends(verify_token)])


@router.post("/")
async def create_checklist_template(template: EmployeeChecklistTemplateCreate):
    data, error = await ChecklistTemplateService.create(template)
    if error:
        return error_response(message=f"Failed to create checklist template: {error}", status_code=500)
    return success_response(
        message="Checklist template created successfully",
        data=data,
        status_code=201
    )


@router.get("/")
async def get_checklist_templates():
    data, error = await ChecklistTemplateService.list()
    if error:
        return error_response(message=f"Failed to fetch checklist templates: {error}", status_code=500)
    return success_response(
        message="Checklist templates fetched successfully",
        data=data
    )


@router.get("/{template_id}")
async def get_checklist_template(template_id: str):
    data, error = await ChecklistTemplateService.get(template_id)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(
        message="Checklist template fetched successfully",
        data=data
    )


@router.put("/{template_id}")
async def update_checklist_template(template_id: str, template: EmployeeChecklistTemplateUpdate):
    data, error = await ChecklistTemplateService.update(template_id, template)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(
        message="Checklist template updated successfully",
        data=data
    )


@router.delete("/{template_id}")
async def delete_checklist_template(template_id: str):
    success, error = await ChecklistTemplateService.delete(template_id)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(
        message="Template deleted successfully",
        data=[]
    )
