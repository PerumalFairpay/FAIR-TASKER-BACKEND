from fastapi import APIRouter, Depends, Form, File, UploadFile
from typing import List, Optional
from app.models import TaskAttachment, EODReportItem
from app.services.api.eod_report import EODReportService
from app.helper.response_helper import success_response, error_response
from app.helper.file_handler import file_handler
from app.auth import verify_token

router = APIRouter(prefix="/tasks", tags=["eod-reports"], dependencies=[Depends(verify_token)])


@router.post("/eod-report")
async def process_eod_report(
    task_id: str = Form(...),
    status: str = Form(...),
    progress: float = Form(...),
    eod_summary: Optional[str] = Form(None),
    move_to_tomorrow: bool = Form(False),
    attachments: List[UploadFile] = File([]),
):
    new_attachments = []
    if attachments:
        for file in attachments:
            uploaded = await file_handler.upload_file(file, subfolder="tasks")
            new_attachments.append(TaskAttachment(
                file_name=file.filename,
                file_url=uploaded["url"],
                file_type=file.content_type,
            ))

    report_item = EODReportItem(
        task_id=task_id,
        status=status,
        progress=progress,
        eod_summary=eod_summary,
        move_to_tomorrow=move_to_tomorrow,
        new_attachments=new_attachments,
    )

    data, error = await EODReportService.process_eod_report([report_item])
    if error:
        return error_response(message=f"Failed to process EOD report: {error}", status_code=500)
    return success_response(message="EOD report processed successfully", data=data)


@router.get("/eod-reports")
async def get_eod_reports(
    project_id: Optional[str] = None,
    assigned_to: Optional[str] = None,
    date: Optional[str] = None,
    priority: Optional[str] = None,
    search: Optional[str] = None,
):
    data, error = await EODReportService.get_eod_reports(
        project_id=project_id,
        assigned_to=assigned_to,
        date=date,
        priority=priority,
        search=search,
    )
    if error:
        return error_response(message=f"Failed to fetch EOD reports: {error}", status_code=500)
    return success_response(message="EOD reports fetched successfully", data=data)
