from fastapi import APIRouter, Depends, Form, File, UploadFile
from typing import List, Optional
from app.models import TaskCreate, TaskUpdate, TaskAttachment, EODReportItem
from app.services.api.task import TaskService
from app.helper.response_helper import success_response, error_response
from app.helper.file_handler import file_handler
from app.auth import verify_token, require_permission

router = APIRouter(prefix="/tasks", tags=["tasks"], dependencies=[Depends(verify_token)])


@router.post("/", dependencies=[Depends(require_permission("task:submit"))])
async def create_task(
    project_id: str = Form(...),
    task_name: str = Form(...),
    start_date: str = Form(...),
    end_date: str = Form(...),
    description: Optional[str] = Form(None),
    start_time: Optional[str] = Form(None),
    end_time: Optional[str] = Form(None),
    priority: str = Form("Medium"),
    assigned_to: List[str] = Form([], alias="assigned_to[]"),
    tags: List[str] = Form([], alias="tags[]"),
    status: str = Form("Todo"),
    progress: float = Form(0.0),
    attachments: List[UploadFile] = File([])
):
    task_attachments = []
    if attachments:
        for file in attachments:
            uploaded = await file_handler.upload_file(file, subfolder="tasks")
            task_attachments.append(TaskAttachment(
                file_name=file.filename,
                file_url=uploaded["url"],
                file_type=file.content_type
            ))

    task = TaskCreate(
        project_id=project_id,
        task_name=task_name,
        description=description,
        start_date=start_date,
        end_date=end_date,
        start_time=start_time,
        end_time=end_time,
        priority=priority,
        assigned_to=assigned_to,
        tags=tags,
        status=status,
        progress=progress,
        attachments=task_attachments
    )
    data, error = await TaskService.create(task)
    if error:
        return error_response(message=f"Failed to create task: {error}", status_code=500)
    return success_response(message="Task created successfully", data=data, status_code=201)


@router.get("/", dependencies=[Depends(require_permission("task:view"))])
async def get_tasks(
    project_id: Optional[str] = None, 
    assigned_to: Optional[str] = None, 
    start_date: Optional[str] = None,
    date: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None
):
    data, error = await TaskService.list(
        project_id=project_id,
        assigned_to=assigned_to,
        start_date=start_date,
        date=date,
        status=status,
        priority=priority
    )
    if error:
        return error_response(message=f"Failed to fetch tasks: {error}", status_code=500)
    return success_response(message="Tasks fetched successfully", data=data)


@router.post("/eod-report", dependencies=[Depends(require_permission("task:submit"))])
async def process_eod_report(
    task_id: str = Form(...),
    status: str = Form(...),
    progress: float = Form(...),
    eod_summary: Optional[str] = Form(None),
    move_to_tomorrow: bool = Form(False),
    attachments: List[UploadFile] = File([]) 
):
    new_attachments = []
    if attachments:
        for file in attachments:
            uploaded = await file_handler.upload_file(file, subfolder="tasks")
            new_attachments.append(TaskAttachment(
                file_name=file.filename,
                file_url=uploaded["url"],
                file_type=file.content_type
            ))
    
    report_item = EODReportItem(
        task_id=task_id,
        status=status,
        progress=progress,
        eod_summary=eod_summary,
        move_to_tomorrow=move_to_tomorrow,
        new_attachments=new_attachments
    )
        
    data, error = await TaskService.process_eod_report([report_item])
    if error:
        return error_response(message=f"Failed to process EOD report: {error}", status_code=500)
    return success_response(message="EOD report processed successfully", data=data)


@router.get("/eod-reports", dependencies=[Depends(require_permission("task:view"))])
async def get_eod_reports(
    project_id: Optional[str] = None, 
    assigned_to: Optional[str] = None, 
    date: Optional[str] = None,
    priority: Optional[str] = None,
    search: Optional[str] = None,
):
    data, error = await TaskService.get_eod_reports(
        project_id=project_id,
        assigned_to=assigned_to,
        date=date,
        priority=priority,
        search=search
    )
    if error:
        return error_response(message=f"Failed to fetch EOD reports: {error}", status_code=500)
    return success_response(message="EOD reports fetched successfully", data=data)


@router.get("/{task_id}", dependencies=[Depends(require_permission("task:view"))])
async def get_task(task_id: str):
    data, error = await TaskService.get(task_id)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(message="Task fetched successfully", data=data)


@router.put("/{task_id}", dependencies=[Depends(require_permission("task:submit"))])
async def update_task(
    task_id: str,
    project_id: Optional[str] = Form(None),
    task_name: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    start_date: Optional[str] = Form(None),
    end_date: Optional[str] = Form(None),
    start_time: Optional[str] = Form(None),
    end_time: Optional[str] = Form(None),
    priority: Optional[str] = Form(None),
    assigned_to: Optional[List[str]] = Form(None, alias="assigned_to[]"),
    tags: Optional[List[str]] = Form(None, alias="tags[]"),
    status: Optional[str] = Form(None),
    progress: Optional[float] = Form(None),
    is_overdue_moved: Optional[bool] = Form(None),
    attachments: List[UploadFile] = File(None)
):
    task_attachments = []
    if attachments:
        for file in attachments:
            uploaded = await file_handler.upload_file(file, subfolder="tasks")
            task_attachments.append(TaskAttachment(
                file_name=file.filename,
                file_url=uploaded["url"],
                file_type=file.content_type
            ))

    final_attachments = []
    if task_attachments:
        current_task, _ = await TaskService.get(task_id)
        if current_task and "attachments" in current_task:
            final_attachments.extend(current_task["attachments"])
        final_attachments.extend(task_attachments)

    task = TaskUpdate(
        project_id=project_id,
        task_name=task_name,
        description=description,
        start_date=start_date,
        end_date=end_date,
        start_time=start_time,
        end_time=end_time,
        priority=priority,
        assigned_to=assigned_to,
        tags=tags,
        status=status,
        progress=progress,
        is_overdue_moved=is_overdue_moved,
        attachments=final_attachments if final_attachments else None
    )
    data, error = await TaskService.update(task_id, task)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(message="Task updated successfully", data=data)


@router.delete("/{task_id}", dependencies=[Depends(require_permission("task:submit"))])
async def delete_task(task_id: str):
    success, error = await TaskService.delete(task_id)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(message="Task deleted successfully", data=[])
