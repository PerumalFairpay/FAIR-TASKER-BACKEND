from fastapi import APIRouter, HTTPException, Depends, Body
from fastapi.responses import JSONResponse
from app.crud.repository import repository as repo
from app.models import TaskCreate, TaskUpdate, EODReportRequest, TaskResponse
from typing import List, Optional
from app.auth import verify_token

router = APIRouter(prefix="/tasks", tags=["tasks"], dependencies=[Depends(verify_token)])

@router.post("/")
async def create_task(task: TaskCreate):
    try:
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
async def process_eod_report(payload: EODReportRequest):
    try:
        results = await repo.process_eod_report(payload.reports)
        return JSONResponse(
            status_code=200,
            content={"message": "EOD report processed successfully", "success": True, "data": results}
        )
    except Exception as e:
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
async def update_task(task_id: str, task: TaskUpdate):
    try:
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
