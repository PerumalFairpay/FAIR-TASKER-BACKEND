from fastapi import APIRouter, HTTPException, Depends, File, UploadFile
from fastapi.responses import JSONResponse
from app.crud.repository import repository as repo
from app.models import AttendanceCreate, AttendanceUpdate
from typing import List, Optional
from app.auth import verify_token, get_current_user
import pandas as pd
import io
from datetime import datetime

router = APIRouter(prefix="/attendance", tags=["attendance"], dependencies=[Depends(verify_token)])

@router.post("/clock-in")
async def clock_in(attendance: AttendanceCreate, current_user: dict = Depends(get_current_user)):
    try:
        employee_id = current_user.get("employee_id") or current_user.get("id")
        if not employee_id:
            # Fallback if employee_id isn't in user record, imply the user ID itself is the link (unlikely based on project structure but safe)
            employee_id = current_user.get("id")

        result = await repo.clock_in(attendance, employee_id)
        return JSONResponse(
            status_code=201, 
            content={"message": "Clocked in successfully", "success": True, "data": result}
        )
    except ValueError as e:
        return JSONResponse(status_code=400, content={"message": str(e), "success": False})
    except Exception as e:
        return JSONResponse(status_code=500, content={"message": f"Server Error: {str(e)}", "success": False})

@router.put("/clock-out")
async def clock_out(attendance: AttendanceUpdate, current_user: dict = Depends(get_current_user)):
    try:
        employee_id = current_user.get("employee_id") or current_user.get("id")
        
        if not attendance.clock_out:
             raise HTTPException(status_code=400, detail="Clock out time required")
        
        # Extract date from clock_out string assuming ISO format
        clock_out_date = attendance.clock_out.split("T")[0]
        
        result = await repo.clock_out(attendance, employee_id, clock_out_date)
        return JSONResponse(
            status_code=200, 
            content={"message": "Clocked out successfully", "success": True, "data": result}
        )
    except ValueError as e:
         return JSONResponse(status_code=400, content={"message": str(e), "success": False})
    except Exception as e:
        return JSONResponse(status_code=500, content={"message": f"Server Error: {str(e)}", "success": False})

@router.get("/my-history")
async def get_my_history(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    try:
        employee_id = current_user.get("employee_id") or current_user.get("id")
        result = await repo.get_employee_attendance(employee_id, start_date, end_date)
        return JSONResponse(
            status_code=200,
            content={"message": "History fetched", "success": True, **result}
        )
    except Exception as e:
        return JSONResponse(status_code=500, content={"message": f"Server Error: {str(e)}", "success": False})

@router.get("/")
async def get_all_attendance(
    date: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    employee_id: Optional[str] = None,
    status: Optional[str] = None
):
    try:
        result = await repo.get_all_attendance(date, start_date, end_date, employee_id, status)
        return JSONResponse(
            status_code=200,
            content={"message": "Attendance records fetched", "success": True, **result}
        )
    except Exception as e:
        return JSONResponse(status_code=500, content={"message": f"Server Error: {str(e)}", "success": False})

@router.post("/generate-records")
async def generate_attendance_records(date: Optional[str] = None, preplanned_only: bool = False):
    """
    Manual trigger to generate attendance records for a specific date.
    Useful for testing or backfilling historical data.
    
    Args:
        date: Date in YYYY-MM-DD format. Defaults to yesterday.
        preplanned_only: If true, only generates holiday/leave records (no absences).
    """
    try:
        from app.jobs.attendance_jobs import generate_attendance_for_date
        result = await generate_attendance_for_date(date, preplanned_only=preplanned_only)
        
        if result.get("success"):
            return JSONResponse(
                status_code=200,
                content=result
            )
        else:
            return JSONResponse(
                status_code=400,
                content=result
            )
    except Exception as e:
        return JSONResponse(status_code=500, content={"message": f"Server Error: {str(e)}", "success": False})


@router.post("/import")
async def import_attendance(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        # Read excel, starting from header row
        # Based on typical biometric report exports shown in image
        df = pd.read_excel(io.BytesIO(contents), skiprows=6)
        
        # Clean column names (strip whitespace)
        df.columns = [str(c).strip() for c in df.columns]
        
        # Skip if necessary columns are missing
        required_cols = ['Employee ID', 'Date', 'Status']
        for col in required_cols:
            if col not in df.columns:
                return JSONResponse(status_code=400, content={"message": f"Missing required column: {col}", "success": False})

        # Remove rows where Employee ID is NaN or 'Total'
        df = df.dropna(subset=['Employee ID'])
        df = df[df['Employee ID'].astype(str).str.lower() != 'total']
        
        records = []
        for _, row in df.iterrows():
            try:
                emp_no_id = str(row['Employee ID']).split('.')[0].strip()
                
                # Parse Date
                date_val = row['Date']
                if isinstance(date_val, datetime):
                    formatted_date = date_val.strftime("%Y-%m-%d")
                else:
                    # Attempt common formats
                    dt_obj = pd.to_datetime(str(date_val), dayfirst=True)
                    formatted_date = dt_obj.strftime("%Y-%m-%d")
                
                # Parse Times
                def parse_time(val):
                    if pd.isna(val) or str(val).lower() == 'nan' or not str(val).strip():
                        return None
                    time_str = str(val).strip()
                    if ':' in time_str:
                         # Handle HH:MM or HH:MM:SS
                         parts = time_str.split(':')
                         if len(parts) >= 2:
                             return f"{formatted_date}T{parts[0].zfill(2)}:{parts[1].zfill(2)}:00"
                    return None

                clock_in = parse_time(row.get('Clock In'))
                clock_out = parse_time(row.get('Clock Out'))
                
                # Status mapping
                raw_status = str(row.get('Status', 'Present'))
                status = "Present"
                if "Absence" in raw_status or "(A)" in raw_status:
                    status = "Absent"
                elif "Late" in raw_status or "(LT)" in raw_status:
                    status = "Late"
                elif "Holiday" in raw_status:
                    status = "Holiday"
                elif "Leave" in raw_status:
                    status = "Leave"
                
                # Work Hours
                def parse_duration(val):
                    if pd.isna(val) or str(val).lower() == 'nan' or not str(val).strip():
                        return 0.0
                    if ':' in str(val):
                        parts = str(val).split(':')
                        try:
                            h = int(parts[0])
                            m = int(parts[1])
                            return round(h + m/60.0, 2)
                        except: return 0.0
                    return 0.0

                total_work_hours = parse_duration(row.get('Total WT'))
                overtime_hours = parse_duration(row.get('Total OT'))
                
                records.append({
                    "employee_id": emp_no_id,
                    "date": formatted_date,
                    "clock_in": clock_in,
                    "clock_out": clock_out,
                    "status": status,
                    "total_work_hours": total_work_hours,
                    "overtime_hours": overtime_hours,
                    "notes": str(row.get('Remarks', '')) if not pd.isna(row.get('Remarks')) else None,
                    "device_type": "Biometric" # Typical for this kind of Excel export
                })
            except Exception as row_err:
                print(f"Error parsing row: {row_err}")
                continue
                
        if not records:
             return JSONResponse(status_code=400, content={"message": "No valid records found in file", "success": False})

        result = await repo.bulk_import_attendance(records)
        return JSONResponse(status_code=200, content={
            "message": f"Successfully imported {result.get('upserted', 0) + result.get('matched', 0)} records", 
            "success": True, 
            "data": result
        })
    except Exception as e:
        return JSONResponse(status_code=500, content={"message": f"Server Error: {str(e)}", "success": False})
