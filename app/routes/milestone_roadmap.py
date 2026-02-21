from fastapi import APIRouter, HTTPException, Depends, Body, Form, File, UploadFile
from fastapi.responses import JSONResponse
from app.crud.repository import repository as repo
from app.models import MilestoneRoadmapCreate, MilestoneRoadmapUpdate, MilestoneRoadmapResponse, MilestoneRoadmapAttachment
from typing import List, Optional
from app.auth import verify_token
from app.helper.file_handler import file_handler

router = APIRouter(prefix="/milestones-roadmaps", tags=["milestones-roadmaps"], dependencies=[Depends(verify_token)])

@router.post("/")
async def create_milestone_roadmap(
    project_id: str = Form(...),
    task_name: str = Form(...),
    start_date: str = Form(...),
    end_date: str = Form(...),
    description: Optional[str] = Form(None),
    priority: str = Form("Medium"),
    assigned_to: List[str] = Form([], alias="assigned_to[]"),
    tags: List[str] = Form([], alias="tags[]"),
    status: str = Form("Backlog"),
    attachments: List[UploadFile] = File([])
):
    try:
        item_attachments = []
        if attachments:
            for file in attachments:
                uploaded = await file_handler.upload_file(file, subfolder="tasks")
                item_attachments.append(MilestoneRoadmapAttachment(
                    file_name=file.filename,
                    file_url=uploaded["url"],
                    file_type=file.content_type
                ))

        item = MilestoneRoadmapCreate(
            project_id=project_id,
            task_name=task_name,
            description=description,
            start_date=start_date,
            end_date=end_date,
            priority=priority,
            assigned_to=assigned_to,
            tags=tags,
            status=status,
            attachments=item_attachments
        )
        new_item = await repo.create_milestone_roadmap(item)
        return JSONResponse(
            status_code=201,
            content={"message": "Created successfully", "success": True, "data": new_item}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to create: {str(e)}", "success": False}
        )

@router.get("/")
async def get_milestones_roadmaps(
    project_id: Optional[str] = None, 
    assigned_to: Optional[str] = None, 
    status: Optional[str] = None,
    priority: Optional[str] = None
):
    try:
        items = await repo.get_milestones_roadmaps(project_id, assigned_to, status, priority)
        return JSONResponse(
            status_code=200,
            content={"message": "Fetched successfully", "success": True, "data": items}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to fetch: {str(e)}", "success": False}
        )

@router.get("/{item_id}")
async def get_milestone_roadmap(item_id: str):
    try:
        item = await repo.get_milestone_roadmap(item_id)
        if not item:
            return JSONResponse(
                status_code=404,
                content={"message": "Not found", "success": False}
            )
        return JSONResponse(
            status_code=200,
            content={"message": "Fetched successfully", "success": True, "data": item}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to fetch: {str(e)}", "success": False}
        )

@router.put("/{item_id}")
async def update_milestone_roadmap(
    item_id: str,
    project_id: Optional[str] = Form(None),
    task_name: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    start_date: Optional[str] = Form(None),
    end_date: Optional[str] = Form(None),
    priority: Optional[str] = Form(None),
    assigned_to: Optional[List[str]] = Form(None, alias="assigned_to[]"),
    tags: Optional[List[str]] = Form(None, alias="tags[]"),
    status: Optional[str] = Form(None),
    attachments: List[UploadFile] = File(None)
):
    try:
        item_attachments = []
        if attachments:
            for file in attachments:
                uploaded = await file_handler.upload_file(file, subfolder="tasks")
                item_attachments.append(MilestoneRoadmapAttachment(
                    file_name=file.filename,
                    file_url=uploaded["url"],
                    file_type=file.content_type
                ))

        final_attachments = []
        
        if item_attachments:
            current_item = await repo.get_milestone_roadmap(item_id)
            if current_item and "attachments" in current_item:
                 final_attachments.extend(current_item["attachments"])
            final_attachments.extend(item_attachments)

        item = MilestoneRoadmapUpdate(
            project_id=project_id,
            task_name=task_name,
            description=description,
            start_date=start_date,
            end_date=end_date,
            priority=priority,
            assigned_to=assigned_to,
            tags=tags,
            status=status,
            attachments=final_attachments if final_attachments else None
        )
        updated_item = await repo.update_milestone_roadmap(item_id, item)
        if not updated_item:
            return JSONResponse(
                status_code=404,
                content={"message": "Not found", "success": False}
            )
        return JSONResponse(
            status_code=200,
            content={"message": "Updated successfully", "success": True, "data": updated_item}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to update: {str(e)}", "success": False}
        )

@router.delete("/{item_id}")
async def delete_milestone_roadmap(item_id: str):
    try:
        success = await repo.delete_milestone_roadmap(item_id)
        if not success:
            return JSONResponse(
                status_code=404,
                content={"message": "Not found", "success": False}
            )
        return JSONResponse(
            status_code=200,
            content={"message": "Deleted successfully", "success": True}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to delete: {str(e)}", "success": False}
        )
