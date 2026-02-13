from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import JSONResponse
from app.crud.repository import repository as repo
from app.models import ProjectCreate, ProjectUpdate
from app.helper.file_handler import file_handler
from typing import List, Optional
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
            uploaded = await file_handler.upload_file(logo)
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

        new_project = await repo.create_project(project_data, logo_path)
        return JSONResponse(
            status_code=201,
            content={"message": "Project created successfully", "success": True, "data": new_project}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to create project: {str(e)}", "success": False}
        )


@router.get("/project_summary", dependencies=[Depends(require_permission("project:view"))])
async def get_projects_summary():
    try:
        projects = await repo.get_projects_summary()
        return JSONResponse(
            status_code=200,
            content={"message": "Projects summary fetched successfully", "success": True, "data": projects}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to fetch projects summary: {str(e)}", "success": False}
        )

@router.get("/all", dependencies=[Depends(require_permission("project:view"))])
async def get_projects():
    try:
        projects = await repo.get_projects()
        return JSONResponse(
            status_code=200,
            content={"message": "Projects fetched successfully", "success": True, "data": projects}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to fetch projects: {str(e)}", "success": False}
        )

@router.get("/{project_id}", dependencies=[Depends(require_permission("project:view"))])
async def get_project(project_id: str):
    try:
        project = await repo.get_project(project_id)
        if not project:
            return JSONResponse(
                status_code=404,
                content={"message": "Project not found", "success": False}
            )
        return JSONResponse(
            status_code=200,
            content={"message": "Project fetched successfully", "success": True, "data": project}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to fetch project: {str(e)}", "success": False}
        )

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
            uploaded = await file_handler.upload_file(logo)
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

        updated_project = await repo.update_project(project_id, update_data, logo_path)
        if not updated_project:
            return JSONResponse(
                status_code=404,
                content={"message": "Project not found", "success": False}
            )
        return JSONResponse(
            status_code=200,
            content={"message": "Project updated successfully", "success": True, "data": updated_project}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to update project: {str(e)}", "success": False}
        )

@router.delete("/delete/{project_id}", dependencies=[Depends(require_permission("project:submit"))])
async def delete_project(project_id: str):
    try:
        success = await repo.delete_project(project_id)
        if not success:
            return JSONResponse(
                status_code=404,
                content={"message": "Project not found", "success": False}
            )
        return JSONResponse(
            status_code=200,
            content={"message": "Project deleted successfully", "success": True}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to delete project: {str(e)}", "success": False}
        )
