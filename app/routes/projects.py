from fastapi import APIRouter, Depends, UploadFile, File, Form
from app.services.api.project import ProjectService
from app.helper.response_helper import success_response, error_response
from app.auth import verify_token, require_permission
from typing import Optional

router = APIRouter(prefix="/projects", tags=["projects"], dependencies=[Depends(verify_token)])


@router.post("/create", dependencies=[Depends(require_permission("project:submit"))])
async def create_project(
    name: str = Form(...),
    client_id: str = Form(...),
    description: Optional[str] = Form(None),
    start_date: Optional[str] = Form(None),
    end_date: Optional[str] = Form(None),
    status: Optional[str] = Form("Planned"),
    priority: Optional[str] = Form("Medium"),
    project_manager_ids: Optional[str] = Form("[]"),
    team_leader_ids: Optional[str] = Form("[]"),
    team_member_ids: Optional[str] = Form("[]"),
    budget: Optional[float] = Form(0.0),
    currency: Optional[str] = Form("USD"),
    tags: Optional[str] = Form("[]"),
    technical_stacks: Optional[str] = Form("[]"),
    third_party_vendors: Optional[str] = Form("[]"),
    logo: Optional[UploadFile] = File(None)
):
    data, error = await ProjectService.create(
        name=name,
        client_id=client_id,
        description=description,
        start_date=start_date,
        end_date=end_date,
        status=status,
        priority=priority,
        project_manager_ids=project_manager_ids,
        team_leader_ids=team_leader_ids,
        team_member_ids=team_member_ids,
        budget=budget,
        currency=currency,
        tags=tags,
        technical_stacks=technical_stacks,
        third_party_vendors=third_party_vendors,
        logo=logo
    )
    if error:
        return error_response(message=f"Failed to create project: {error}", status_code=500)
    return success_response(message="Project created successfully", data=data, status_code=201)


@router.get("/project_summary", dependencies=[Depends(require_permission("project:view"))])
async def get_projects_summary():
    data, error = await ProjectService.get_summary()
    if error:
        return error_response(message=f"Failed to fetch projects summary: {error}", status_code=500)
    return success_response(message="Projects summary fetched successfully", data=data)


@router.get("/all", dependencies=[Depends(require_permission("project:view"))])
async def get_projects():
    data, error = await ProjectService.list()
    if error:
        return error_response(message=f"Failed to fetch projects: {error}", status_code=500)
    return success_response(message="Projects fetched successfully", data=data)


@router.get("/{project_id}", dependencies=[Depends(require_permission("project:view"))])
async def get_project(project_id: str):
    data, error = await ProjectService.get(project_id)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(message="Project fetched successfully", data=data)


@router.put("/update/{project_id}", dependencies=[Depends(require_permission("project:submit"))])
async def update_project(
    project_id: str,
    name: Optional[str] = Form(None),
    client_id: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    start_date: Optional[str] = Form(None),
    end_date: Optional[str] = Form(None),
    status: Optional[str] = Form(None),
    priority: Optional[str] = Form(None),
    project_manager_ids: Optional[str] = Form(None),
    team_leader_ids: Optional[str] = Form(None),
    team_member_ids: Optional[str] = Form(None),
    budget: Optional[float] = Form(None),
    currency: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    technical_stacks: Optional[str] = Form(None),
    third_party_vendors: Optional[str] = Form(None),
    logo: Optional[UploadFile] = File(None)
):
    data, error = await ProjectService.update(
        project_id=project_id,
        name=name,
        client_id=client_id,
        description=description,
        start_date=start_date,
        end_date=end_date,
        status=status,
        priority=priority,
        project_manager_ids=project_manager_ids,
        team_leader_ids=team_leader_ids,
        team_member_ids=team_member_ids,
        budget=budget,
        currency=currency,
        tags=tags,
        technical_stacks=technical_stacks,
        third_party_vendors=third_party_vendors,
        logo=logo
    )
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(message="Project updated successfully", data=data)


@router.delete("/delete/{project_id}", dependencies=[Depends(require_permission("project:submit"))])
async def delete_project(project_id: str):
    success, error = await ProjectService.delete(project_id)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(message="Project deleted successfully", data=[])
