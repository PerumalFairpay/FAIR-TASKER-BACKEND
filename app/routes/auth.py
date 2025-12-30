from fastapi import APIRouter, HTTPException, status
from app.database import users_collection
from app.models import UserCreate, UserLogin, UserResponse
from app.utils import get_password_hash, verify_password
from bson import ObjectId

router = APIRouter()

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user: UserCreate):
    # Check if user already exists
    existing_user = await users_collection.find_one({"$or": [{"email": user.email}, {"employee_id": user.employee_id}]})
    if existing_user:
        raise HTTPException(status_code=400, detail="User with this email or Employee ID already exists")

    hashed_password = get_password_hash(user.password)
    user_dict = user.dict()
    user_dict.pop("password")
    user_dict["hashed_password"] = hashed_password
    
    new_user = await users_collection.insert_one(user_dict)
    created_user = await users_collection.find_one({"_id": new_user.inserted_id})
    
    return UserResponse(
        id=str(created_user["_id"]),
        employee_id=created_user["employee_id"],
        attendance_id=created_user["attendance_id"],
        name=created_user["name"],
        email=created_user["email"],
        mobile=created_user["mobile"]
    )

@router.post("/login")
async def login(user: UserLogin):
    user_record = await users_collection.find_one({"email": user.email})
    if not user_record or not verify_password(user.password, user_record["hashed_password"]):
        raise HTTPException(status_code=400, detail="Invalid email or password")
    
    return {
        "message": "Login successful",
        "success": True,
        "data": {
            "id": str(user_record["_id"]),
            "employee_id": user_record.get("employee_id"),
            "attendance_id": user_record.get("attendance_id"),
            "name": user_record.get("name"),
            "email": user_record.get("email"),
            "mobile": user_record.get("mobile")
        }
    }

