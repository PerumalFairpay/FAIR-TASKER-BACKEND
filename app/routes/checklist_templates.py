from fastapi import APIRouter, HTTPException, Depends
from app.models import EmployeeChecklistTemplateCreate, EmployeeChecklistTemplateUpdate, EmployeeChecklistTemplateResponse
from app.crud.repository import repository
from typing import List
from app.auth import verify_token

router = APIRouter(prefix="/checklist-templates", tags=["checklist-templates"], dependencies=[Depends(verify_token)])

@router.post("/", response_model=EmployeeChecklistTemplateResponse)
async def create_checklist_template(template: EmployeeChecklistTemplateCreate):
    return await repository.create_checklist_template(template)

@router.get("/", response_model=List[EmployeeChecklistTemplateResponse])
async def get_checklist_templates():
    return await repository.get_checklist_templates()

@router.put("/{template_id}", response_model=EmployeeChecklistTemplateResponse)
async def update_checklist_template(template_id: str, template: EmployeeChecklistTemplateUpdate):
    updated = await repository.update_checklist_template(template_id, template)
    if not updated:
        raise HTTPException(status_code=404, detail="Template not found")
    return updated

@router.delete("/{template_id}")
async def delete_checklist_template(template_id: str):
    success = await repository.delete_checklist_template(template_id)
    if not success:
         raise HTTPException(status_code=404, detail="Template not found")
    return {"message": "Template deleted successfully"}
