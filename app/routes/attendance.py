from fastapi import APIRouter, Depends, File, UploadFile
from typing import Optional
import pandas as pd
import io
from datetime import datetime
from app.models import (
    AttendanceCreate,
    AttendanceUpdate,
    AttendanceAdminEdit,
    BiometricSyncRequest,
)
from app.auth import verify_token, get_current_user
from app.services.api.attendance import AttendanceService
from app.services.api.employee import EmployeeService
from app.helper.response_helper import success_response, error_response

router = APIRouter(prefix="/attendance", tags=["attendance"])


@router.post("/clock-in", dependencies=[Depends(verify_token)])
async def clock_in(
    attendance: AttendanceCreate, current_user: dict = Depends(get_current_user)
):
    employee_id = current_user.get("employee_no_id") or current_user.get("id")
    if not employee_id:
        employee_id = current_user.get("id")

    data, metrics, error = await AttendanceService.clock_in(attendance, employee_id)
    if error:
        status_code = 400 if "already" in error.lower() else 500
        return error_response(message=error, status_code=status_code)

    return success_response(
        message="Clocked in successfully",
        data=data,
        meta=metrics,
        status_code=201
    )


@router.put("/clock-out", dependencies=[Depends(verify_token)])
async def clock_out(
    attendance: AttendanceUpdate, current_user: dict = Depends(get_current_user)
):
    employee_id = current_user.get("employee_no_id") or current_user.get("id")
    if not attendance.clock_out:
        return error_response(message="Clock out time required", status_code=400)

    clock_out_date = attendance.clock_out.split("T")[0]
    data, metrics, error = await AttendanceService.clock_out(attendance, employee_id, clock_out_date)
    if error:
        status_code = 404 if "no clock-in" in error.lower() else 500
        return error_response(message=error, status_code=status_code)

    return success_response(
        message="Clocked out successfully",
        data=data,
        meta=metrics
    )


@router.get("/my-history", dependencies=[Depends(verify_token)])
async def get_my_history(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    employee_id = current_user.get("employee_no_id") or current_user.get("id")
    result, error = await AttendanceService.get_employee_attendance(employee_id, start_date, end_date)
    if error:
        return error_response(message=f"Server Error: {error}", status_code=500)

    return success_response(
        message="History fetched successfully",
        data=(result or {}).get("data", []),
        meta=(result or {}).get("metrics")
    )


@router.get("/", dependencies=[Depends(verify_token)])
async def get_all_attendance(
    date: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    employee_id: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
):
    result, error = await AttendanceService.list(
        date=date,
        start_date=start_date,
        end_date=end_date,
        employee_id=employee_id,
        status=status,
        page=page,
        limit=limit
    )
    if error:
        return error_response(message=f"Server Error: {error}", status_code=500)

    return success_response(
        message="Attendance records fetched",
        data=(result or {}).get("data", []),
        meta={
            "metrics": (result or {}).get("metrics"),
            "pagination": (result or {}).get("pagination")
        }
    )


@router.put("/edit/{attendance_id}", dependencies=[Depends(verify_token)])
async def edit_attendance(
    attendance_id: str,
    payload: AttendanceAdminEdit,
    current_user: dict = Depends(get_current_user),
):
    if current_user.get("role") not in ["admin", "super_admin"]:
        return error_response(message="Only admins can edit attendance records", status_code=403)

    data, error = await AttendanceService.edit_attendance_record(attendance_id, payload)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)

    return success_response(
        message="Attendance record updated successfully",
        data=data
    )


@router.post("/generate-records", dependencies=[Depends(verify_token)])
async def generate_attendance_records(
    date: Optional[str] = None, preplanned_only: bool = False
):
    try:
        from app.jobs.attendance_jobs import generate_attendance_for_date
        result = await generate_attendance_for_date(date, preplanned_only=preplanned_only)
        if result.get("success"):
            return success_response(message="Attendance records generated", data=result)
        else:
            return error_response(message="Failed to generate attendance records", status_code=400)
    except Exception as e:
        return error_response(message=f"Server Error: {str(e)}", status_code=500)


@router.post("/biometric/sync")
async def sync_biometric_data(payload: BiometricSyncRequest):
    if not payload.data:
        return error_response(message="No data provided", status_code=400)

    result, error = await AttendanceService.bulk_sync_biometric_logs(payload.data)
    if error:
        return error_response(message=f"Server Error: {error}", status_code=500)

    return success_response(
        message=f"Processed {(result or {}).get('processed', 0)} records",
        data=result
    )


@router.post("/import", dependencies=[Depends(verify_token)])
async def import_attendance(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        df = pd.read_excel(io.BytesIO(contents), skiprows=6)
        df.columns = [str(c).strip() for c in df.columns]

        required_cols = ["Employee ID", "Date", "Status"]
        for col in required_cols:
            if col not in df.columns:
                return error_response(message=f"Missing required column: {col}", status_code=400)

        df = df.dropna(subset=["Employee ID"])
        df = df[df["Employee ID"].astype(str).str.lower() != "total"]

        all_employees, _ = await EmployeeService.get_summary()
        all_employees = all_employees or []
        valid_biometric_map = {
            str(emp.get("biometric_id")).strip(): str(emp.get("id"))
            for emp in all_employees
            if emp.get("biometric_id")
        }

        records = []
        skipped_count = 0
        for _, row in df.iterrows():
            try:
                bio_id_input = str(row["Employee ID"]).split(".")[0].strip()
                if bio_id_input not in valid_biometric_map:
                    skipped_count += 1
                    continue

                emp_no_id = valid_biometric_map[bio_id_input]

                date_val = row["Date"]
                if isinstance(date_val, datetime):
                    formatted_date = date_val.strftime("%Y-%m-%d")
                else:
                    dt_obj = pd.to_datetime(str(date_val), dayfirst=True)
                    formatted_date = dt_obj.strftime("%Y-%m-%d")

                def parse_time(val):
                    if pd.isna(val) or str(val).lower() == "nan" or not str(val).strip():
                        return None
                    time_str = str(val).strip()
                    if ":" in time_str:
                        parts = time_str.split(":")
                        if len(parts) >= 2:
                            return f"{formatted_date}T{parts[0].zfill(2)}:{parts[1].zfill(2)}:00"
                    return None

                clock_in = parse_time(row.get("Clock In"))
                clock_out = parse_time(row.get("Clock Out"))

                raw_status = str(row.get("Status", "Present"))
                status = "Present"
                if "Absence" in raw_status or "(A)" in raw_status:
                    status = "Absent"
                elif "Late" in raw_status or "(LT)" in raw_status:
                    status = "Late"
                elif "Holiday" in raw_status:
                    status = "Holiday"
                elif "Leave" in raw_status:
                    status = "Leave"

                def parse_duration(val):
                    if pd.isna(val) or str(val).lower() == "nan" or not str(val).strip():
                        return 0.0
                    if ":" in str(val):
                        parts = str(val).split(":")
                        try:
                            h = int(parts[0])
                            m = int(parts[1])
                            return round(h + m / 60.0, 2)
                        except Exception:
                            return 0.0
                    return 0.0

                total_work_hours = parse_duration(row.get("Total WT"))
                overtime_hours = parse_duration(row.get("Total OT"))

                records.append({
                    "employee_id": emp_no_id,
                    "date": formatted_date,
                    "clock_in": clock_in,
                    "clock_out": clock_out,
                    "status": status,
                    "total_work_hours": total_work_hours,
                    "overtime_hours": overtime_hours,
                    "notes": str(row.get("Remarks", "")) if not pd.isna(row.get("Remarks")) else None,
                    "device_type": "Biometric",
                    "location": "At Office",
                })
            except Exception:
                continue

        if not records:
            return error_response(
                message=f"No valid records found in file. Skipped {skipped_count} invalid employees.",
                status_code=400
            )

        result, err = await AttendanceService.bulk_import_attendance(records)
        if err:
            return error_response(message=err, status_code=500)

        imported_cnt = (result or {}).get("upserted", 0) + (result or {}).get("matched", 0)
        return success_response(
            message=f"Successfully imported {imported_cnt} records. Skipped {skipped_count} records for non-existent employees.",
            data=result
        )
    except Exception as e:
        return error_response(message=f"Server Error: {str(e)}", status_code=500)
