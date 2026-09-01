from fastapi import APIRouter, Depends, UploadFile, File, Form
from app.models import ProjectCreate, ProjectUpdate
from app.helper.file_handler import file_handler
from app.helper.response_helper import success_response, error_response
from app.services.api.project import ProjectService
from typing import Optional
import json

from app.auth import verify_token, require_permission

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
    try:
        logo_path = None
        if logo and logo.filename:
            uploaded = await file_handler.upload_file(logo, subfolder="projects")
            logo_path = uploaded["url"]

        project_data = ProjectCreate(
            name=name,
            client_id=client_id,
            description=description,
            start_date=start_date,
            end_date=end_date,
            status=status,
            priority=priority,
            project_manager_ids=json.loads(project_manager_ids),
            team_leader_ids=json.loads(team_leader_ids),
            team_member_ids=json.loads(team_member_ids),
            budget=budget,
            currency=currency,
            tags=json.loads(tags),
            technical_stacks=json.loads(technical_stacks),
            third_party_vendors=json.loads(third_party_vendors),
            logo=logo_path
        )

        data, error = await ProjectService.create(project_data, logo_path)
        if error:
            return error_response(message=f"Failed to create project: {error}", status_code=500)
        return success_response(message="Project created successfully", data=data, status_code=201)
    except Exception as e:
        return error_response(message=f"Failed to create project: {str(e)}", status_code=500)


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
    try:
        logo_path = None
        if logo and logo.filename:
            uploaded = await file_handler.upload_file(logo, subfolder="projects")
            logo_path = uploaded["url"]

        update_data = ProjectUpdate(
            name=name,
            client_id=client_id,
            description=description,
            start_date=start_date,
            end_date=end_date,
            status=status,
            priority=priority,
            project_manager_ids=json.loads(project_manager_ids) if project_manager_ids else None,
            team_leader_ids=json.loads(team_leader_ids) if team_leader_ids else None,
            team_member_ids=json.loads(team_member_ids) if team_member_ids else None,
            budget=budget,
            currency=currency,
            tags=json.loads(tags) if tags else None,
            technical_stacks=json.loads(technical_stacks) if technical_stacks else None,
            third_party_vendors=json.loads(third_party_vendors) if third_party_vendors else None,
            logo=logo_path
        )

        data, error = await ProjectService.update(project_id, update_data, logo_path)
        if error:
            status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
            return error_response(message=error, status_code=status_code)
        return success_response(message="Project updated successfully", data=data)
    except Exception as e:
        return error_response(message=f"Failed to update project: {str(e)}", status_code=500)


@router.delete("/delete/{project_id}", dependencies=[Depends(require_permission("project:submit"))])
async def delete_project(project_id: str):
    success, error = await ProjectService.delete(project_id)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(message="Project deleted successfully", data=[])

