from fastapi import APIRouter, HTTPException, status, Response, Depends, Cookie
from fastapi.responses import JSONResponse
from app.database import users_collection, employees_collection
from app.models import UserLogin, UserResponse
from app.utils import get_password_hash, verify_password
from app.auth import create_access_token, verify_token, get_current_user
from bson import ObjectId
from datetime import datetime

router = APIRouter()


@router.post("/login")
async def login(user: UserLogin, response: Response):
    user_record = await users_collection.find_one({"email": user.email})
    if not user_record or not verify_password(
        user.password, user_record["hashed_password"]
    ):
        raise HTTPException(
            status_code=400,
            detail="We couldn't log you in. Please check your credentials or contact support if your account is inactive.",
        )

    # Create token and set cookie
    token = create_access_token(user_record)
    response.set_cookie(
        key="token",
        value=token,
        httponly=True,
        max_age=1440 * 60,
        samesite="lax",
        secure=False,  # Set to True in production with HTTPS
    )

    return {
        "message": "Login successful",
        "success": True,
        "token": token,
        "data": {
            "id": str(user_record["_id"]),
            "employee_id": user_record.get("employee_id"),
            "attendance_id": user_record.get("attendance_id"),
            "name": user_record.get("name"),
            "email": user_record.get("email"),
            "mobile": user_record.get("mobile"),
            "role": user_record.get("role", "employee"),
        },
    }


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("token")
    return {"message": "Logged out successfully", "success": True}


@router.get("/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    current_user.pop("hashed_password", None)

    # Fetch profile picture if linked to an employee
    if "employee_id" in current_user and current_user["employee_id"]:
        employee = await employees_collection.find_one(
            {"employee_no_id": current_user["employee_id"]}
        )
        if employee:
            current_user["profile_picture"] = employee.get("profile_picture")
            current_user["work_mode"] = employee.get("work_mode")

    return {"message": "Success", "success": True, "data": current_user}
