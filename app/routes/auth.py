from fastapi import APIRouter, HTTPException, status, Response
from app.database import users_collection
from app.models import UserCreate, UserLogin, UserResponse
from app.utils import get_password_hash, verify_password, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES
from bson import ObjectId
from datetime import timedelta

router = APIRouter()

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user: UserCreate):
    # Check if user already exists
    existing_user = await users_collection.find_one({"$or": [{"email": user.email}, {"hrm_id": user.hrm_id}]})
    if existing_user:
        raise HTTPException(status_code=400, detail="User with this email or HRM ID already exists")

    # Determine role: First user is 'admin', others are 'employee'
    from app.database import roles_collection
    total_users = await users_collection.count_documents({})
    role_name = "admin" if total_users == 0 else "employee"
    role_description = "Administrator with full access" if role_name == "admin" else "Standard employee role"

    # Ensure the role exists
    existing_role = await roles_collection.find_one({"name": role_name})
    if not existing_role:
        await roles_collection.insert_one({"name": role_name, "description": role_description, "permissions": []})

    hashed_password = get_password_hash(user.password)
    user_dict = user.dict()
    user_dict.pop("password")
    user_dict["hashed_password"] = hashed_password
    user_dict["role"] = role_name 
    
    new_user = await users_collection.insert_one(user_dict)
    created_user = await users_collection.find_one({"_id": new_user.inserted_id})
    
    return UserResponse(
        id=str(created_user["_id"]),
        first_name=created_user["first_name"],
        last_name=created_user["last_name"],
        phone=created_user["phone"],
        email=created_user["email"],
        department=created_user["department"],
        hrm_id=created_user["hrm_id"],
        role=created_user["role"]
    )

@router.post("/login")
async def login(response: Response, user: UserLogin):
    user_record = await users_collection.find_one({"email": user.email})
    if not user_record or not verify_password(user.password, user_record["hashed_password"]):
        raise HTTPException(status_code=400, detail="Invalid email or password")
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user_record["_id"]), "role": user_record.get("role", "employee")},
        expires_delta=access_token_expires
    )
    
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        expires=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax",
        secure=False  # Set to True in production with HTTPS
    )
    
    return {"message": "Login successful", "user_id": str(user_record["_id"])}

@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(key="access_token")
    return {"message": "Logout successful"}
