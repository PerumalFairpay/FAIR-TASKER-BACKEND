from fastapi import APIRouter, Depends, Form, File, UploadFile
from typing import List, Optional
from app.models import MilestoneRoadmapCreate, MilestoneRoadmapUpdate, MilestoneRoadmapAttachment
from app.auth import verify_token
from app.helper.file_handler import file_handler
from app.helper.response_helper import success_response, error_response
from app.services.api import MilestoneRoadmapService

router = APIRouter(prefix="/milestones-roadmaps", tags=["milestones-roadmaps"], dependencies=[Depends(verify_token)])


@router.post("")
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
                uploaded = await file_handler.upload_file(file, subfolder="milestones_roadmaps")
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
        new_item, err = await MilestoneRoadmapService.create(item)
        if err:
            return error_response(message=err, status_code=500)
        return success_response(message="Milestone/Roadmap created successfully", data=new_item, status_code=201)
    except Exception as e:
        return error_response(message=f"Failed to create: {str(e)}", status_code=500)


@router.get("")
@router.get("/")
async def get_milestones_roadmaps(
    project_id: Optional[str] = None, 
    assigned_to: Optional[str] = None, 
    status: Optional[str] = None,
    priority: Optional[str] = None
):
    items, err = await MilestoneRoadmapService.list(
        project_id=project_id,
        assigned_to=assigned_to,
        status=status,
        priority=priority
    )
    if err:
        return error_response(message=err, status_code=500)
    return success_response(message="Milestones/Roadmaps fetched successfully", data=items if items is not None else [])


@router.get("/{item_id}")
async def get_milestone_roadmap(item_id: str):
    item, err = await MilestoneRoadmapService.get(item_id)
    if err:
        status_code = 404 if "not found" in err.lower() or "invalid" in err.lower() else 500
        return error_response(message=err, status_code=status_code)
    return success_response(message="Milestone/Roadmap fetched successfully", data=item)


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
                uploaded = await file_handler.upload_file(file, subfolder="milestones_roadmaps")
                item_attachments.append(MilestoneRoadmapAttachment(
                    file_name=file.filename,
                    file_url=uploaded["url"],
                    file_type=file.content_type
                ))

        final_attachments = []
        if item_attachments:
            current_item, _ = await MilestoneRoadmapService.get(item_id)
            if current_item and "attachments" in current_item and current_item["attachments"]:
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
        updated_item, err = await MilestoneRoadmapService.update(item_id, item)
        if err:
            status_code = 404 if "not found" in err.lower() or "invalid" in err.lower() else 500
            return error_response(message=err, status_code=status_code)
        return success_response(message="Milestone/Roadmap updated successfully", data=updated_item)
    except Exception as e:
        return error_response(message=f"Failed to update: {str(e)}", status_code=500)


@router.delete("/{item_id}")
async def delete_milestone_roadmap(item_id: str):
    success, err = await MilestoneRoadmapService.delete(item_id)
    if not success:
        status_code = 404 if err and ("not found" in err.lower() or "invalid" in err.lower()) else 500
        return error_response(message=err or "Failed to delete milestone/roadmap", status_code=status_code)
    return success_response(message="Milestone/Roadmap deleted successfully", data=[])
