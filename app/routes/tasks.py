from fastapi import APIRouter, HTTPException, Depends, Body, Form, File, UploadFile, Request
import json
from fastapi.responses import JSONResponse
from app.crud.repository import repository as repo
from app.models import TaskCreate, TaskUpdate, EODReportRequest, TaskResponse, TaskAttachment
from typing import List, Optional
from app.auth import verify_token
from app.helper.file_handler import file_handler

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
    attachments: List[UploadFile] = File([])
):
    try:
        task_attachments = []
        if attachments:
            for file in attachments:
                uploaded = await file_handler.upload_file(file)
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
        new_task = await repo.create_task(task)
        return JSONResponse(
            status_code=201,
            content={"message": "Task created successfully", "success": True, "data": new_task}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to create task: {str(e)}", "success": False}
        )

@router.get("/")
async def get_tasks(
    project_id: Optional[str] = None, 
    assigned_to: Optional[str] = None, 
    start_date: Optional[str] = None,
    date: Optional[str] = None
):
    try:
        tasks = await repo.get_tasks(project_id, assigned_to, start_date, date)
        return JSONResponse(
            status_code=200,
            content={"message": "Tasks fetched successfully", "success": True, "data": tasks}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to fetch tasks: {str(e)}", "success": False}
        )

@router.post("/eod-report")
async def process_eod_report(request: Request):
    try:
        form = await request.form()
        reports_json = form.get("reports")
        if not reports_json:
             return JSONResponse(status_code=400, content={"message": "Reports data is missing", "success": False})
             
        reports_data = json.loads(reports_json)
        
        final_reports = []
        for report in reports_data:
            task_id = report.get("task_id")
            
            # Check for attachments_{task_id} in form
            files = form.getlist(f"attachments_{task_id}")
            
            new_attachments = []
            for file in files:
                if file.filename: # check if file object is valid/has name
                    uploaded = await file_handler.upload_file(file)
                    new_attachments.append(TaskAttachment(
                        file_name=file.filename,
                        file_url=uploaded["url"],
                        file_type=file.content_type
                    ))
            
            report_item = EODReportItem(
                task_id=task_id,
                status=report.get("status"),
                progress=float(report.get("progress", 0)),
                eod_summary=report.get("eod_summary"),
                move_to_tomorrow=report.get("move_to_tomorrow"),
                new_attachments=new_attachments
            )
            final_reports.append(report_item)
            
        results = await repo.process_eod_report(final_reports)
        return JSONResponse(
            status_code=200,
            content={"message": "EOD report processed successfully", "success": True, "data": results}
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to process EOD report: {str(e)}", "success": False}
        )

@router.get("/eod-reports")
async def get_eod_reports(
    project_id: Optional[str] = None, 
    assigned_to: Optional[str] = None, 
    date: Optional[str] = None,
    priority: Optional[str] = None
):
    try:
        reports = await repo.get_eod_reports(project_id, assigned_to, date, priority)
        return JSONResponse(
            status_code=200,
            content={"message": "EOD reports fetched successfully", "success": True, "data": reports}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to fetch EOD reports: {str(e)}", "success": False}
        )

@router.get("/{task_id}")
async def get_task(task_id: str):
    try:
        task = await repo.get_task(task_id)
        if not task:
            return JSONResponse(
                status_code=404,
                content={"message": "Task not found", "success": False}
            )
        return JSONResponse(
            status_code=200,
            content={"message": "Task fetched successfully", "success": True, "data": task}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to fetch task: {str(e)}", "success": False}
        )

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
    attachments: List[UploadFile] = File(None)
):
    try:
        task_attachments = []
        if attachments:
            for file in attachments:
                uploaded = await file_handler.upload_file(file)
                task_attachments.append(TaskAttachment(
                    file_name=file.filename,
                    file_url=uploaded["url"],
                    file_type=file.content_type
                ))

        final_attachments = []
        
        # Fetch existing task to get current attachments if new ones are added
        if task_attachments:
            current_task = await repo.get_task(task_id)
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
            attachments=final_attachments if final_attachments else None
        )
        updated_task = await repo.update_task(task_id, task)
        if not updated_task:
            return JSONResponse(
                status_code=404,
                content={"message": "Task not found", "success": False}
            )
        return JSONResponse(
            status_code=200,
            content={"message": "Task updated successfully", "success": True, "data": updated_task}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to update task: {str(e)}", "success": False}
        )



@router.delete("/{task_id}")
async def delete_task(task_id: str):
    try:
        success = await repo.delete_task(task_id)
        if not success:
            return JSONResponse(
                status_code=404,
                content={"message": "Task not found", "success": False}
            )
        return JSONResponse(
            status_code=200,
            content={"message": "Task deleted successfully", "success": True}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to delete task: {str(e)}", "success": False}
        )
