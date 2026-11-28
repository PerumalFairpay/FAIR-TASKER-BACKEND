from fastapi import APIRouter, Depends, Form, File, UploadFile
from typing import List, Optional
from app.models import TaskCreate, TaskUpdate, TaskAttachment
from app.services.api.task import TaskService
from app.helper.response_helper import success_response, error_response
from app.helper.file_handler import file_handler
from app.services.notification_helper import NotificationHelper
from app.auth import verify_token, get_current_user

router = APIRouter(prefix="/tasks", tags=["tasks"], dependencies=[Depends(verify_token)])


@router.post("/")
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
    attachments: List[UploadFile] = File([]),
    current_user: dict = Depends(get_current_user),
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

    assigner_id = str(current_user["id"])
    assigner_name = current_user.get("username") or current_user.get("name") or current_user.get("email") or "Someone"

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
        assigned_by=assigner_id,
        tags=tags,
        status=status,
        progress=progress,
        attachments=task_attachments
    )
    data, error = await TaskService.create(task)
    if error:
        is_validation_err = any(k in error.lower() for k in ("end date", "end time", "invalid date"))
        return error_response(
            message=error if is_validation_err else f"Failed to create task: {error}",
            status_code=400 if is_validation_err else 500,
        )

    if assigned_to:
        NotificationHelper.trigger_assignee_notification(
            assignee_ids=assigned_to,
            title="New Task Assigned",
            body=f"{assigner_name} assigned you to \"{task_name}\" (Due: {end_date}).",
            notification_type="task_assigned",
            data={
                "task_id": str(data.get("id") or data.get("_id", "")),
                "project_id": project_id,
                "assigned_by": assigner_id,
            },
            url="/tasks",
        )

    return success_response(message="Task created successfully", data=data, status_code=201)


@router.get("/")
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


@router.get("/{task_id}")
async def get_task(task_id: str):
    data, error = await TaskService.get(task_id)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(message="Task fetched successfully", data=data)


@router.put("/{task_id}")
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
    attachments: List[UploadFile] = File(None),
    current_user: dict = Depends(get_current_user),
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

    current_task = None
    if task_attachments or assigned_to is not None:
        current_task, _ = await TaskService.get(task_id)

    final_attachments = []
    if task_attachments:
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
        lower_err = error.lower()
        if "not found" in lower_err or "invalid task id" in lower_err:
            status_code = 404
        elif any(k in lower_err for k in ("end date", "end time", "invalid date")):
            status_code = 400
        else:
            status_code = 500
        return error_response(message=error, status_code=status_code)

    if assigned_to is not None and data:
        prev_assignees = set((current_task or {}).get("assigned_to") or [])
        new_assignees = [uid for uid in assigned_to if uid not in prev_assignees]
        if new_assignees:
            assigner_id = str(current_user["id"])
            assigner_name = current_user.get("username") or current_user.get("name") or current_user.get("email") or "Someone"
            resolved_task_name = data.get("task_name") or task_name or "a task"
            NotificationHelper.trigger_assignee_notification(
                assignee_ids=new_assignees,
                title="New Task Assigned",
                body=f"{assigner_name} assigned you to \"{resolved_task_name}\".",
                notification_type="task_assigned",
                data={
                    "task_id": str(data.get("id") or data.get("_id", task_id)),
                    "project_id": data.get("project_id"),
                    "assigned_by": assigner_id,
                },
                url="/tasks",
            )

    return success_response(message="Task updated successfully", data=data)


@router.delete("/{task_id}")
async def delete_task(task_id: str):
    success, error = await TaskService.delete(task_id)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(message="Task deleted successfully", data=[])
