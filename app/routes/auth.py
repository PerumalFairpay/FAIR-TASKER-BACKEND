from fastapi import APIRouter, HTTPException, status, Response, Depends, Cookie
from fastapi.responses import JSONResponse
from app.database import users_collection
from app.models import UserCreate, UserLogin, UserResponse
from app.utils import get_password_hash, verify_password
from app.auth import create_access_token, verify_token, get_current_user
from bson import ObjectId
from datetime import datetime

router = APIRouter()

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user: UserCreate, response: Response):
    # Check if user already exists
    existing_user = await users_collection.find_one({"$or": [{"email": user.email}, {"employee_id": user.employee_id}]})
    if existing_user:
        raise HTTPException(status_code=400, detail="User with this email or Employee ID already exists")

    hashed_password = get_password_hash(user.password)
    user_dict = user.dict()
    user_dict.pop("password")
    user_dict["hashed_password"] = hashed_password
    user_dict["created_at"] = datetime.utcnow()
    
    new_user = await users_collection.insert_one(user_dict)
    created_user = await users_collection.find_one({"_id": new_user.inserted_id})
    
    # Create token and set cookie
    token = create_access_token(created_user)
    response.set_cookie(
        key="token", 
        value=token, 
        httponly=True, 
        max_age=1440 * 60, 
        samesite="lax", 
        secure=False # Set to True in production with HTTPS
    )
    
    return UserResponse(
        id=str(created_user["_id"]),
        employee_id=created_user["employee_id"],
        attendance_id=created_user["attendance_id"],
        name=created_user["name"],
        email=created_user["email"],
        mobile=created_user["mobile"],
        role=created_user.get("role", "employee")
    )

@router.post("/login")
async def login(user: UserLogin, response: Response):
    user_record = await users_collection.find_one({"email": user.email})
    if not user_record or not verify_password(user.password, user_record["hashed_password"]):
        raise HTTPException(status_code=400, detail="Invalid email or password")
    
    # Create token and set cookie
    token = create_access_token(user_record)
    response.set_cookie(
        key="token", 
        value=token, 
        httponly=True, 
        max_age=1440 * 60, 
        samesite="lax", 
        secure=False # Set to True in production with HTTPS
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
            "role": user_record.get("role", "employee")
        }
    }

@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("token")
    return {"message": "Logged out successfully", "success": True}

@router.get("/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    return {
        "message": "Success",
        "success": True,
        "data": current_user
    }

