from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from app.crud.repository import repository as repo
from app.models import AttendanceCreate, AttendanceUpdate
from typing import List, Optional
from app.auth import verify_token, get_current_user

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
async def get_my_history(current_user: dict = Depends(get_current_user)):
    try:
        employee_id = current_user.get("employee_id") or current_user.get("id")
        history = await repo.get_employee_attendance(employee_id)
        return JSONResponse(
            status_code=200,
            content={"message": "History fetched", "success": True, "data": history}
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
        data = await repo.get_all_attendance(date, start_date, end_date, employee_id, status)
        return JSONResponse(
            status_code=200,
            content={"message": "Attendance records fetched", "success": True, "data": data}
        )
    except Exception as e:
        return JSONResponse(status_code=500, content={"message": f"Server Error: {str(e)}", "success": False})
