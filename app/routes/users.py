from fastapi import APIRouter, HTTPException, status, Depends, Body
from typing import List
from app.database import users_collection, roles_collection
from app.models import UserResponse
from bson import ObjectId
from app.dependencies import get_current_admin

router = APIRouter()

@router.put("/{user_id}/role", response_model=UserResponse)
async def update_user_role(
    user_id: str, 
    role_name: str = Body(..., embed=True),
    current_admin: UserResponse = Depends(get_current_admin)
):
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="Invalid user ID")
    
    # Check if role exists
    role_exists = await roles_collection.find_one({"name": role_name})
    if not role_exists:
        raise HTTPException(status_code=400, detail=f"Role '{role_name}' does not exist")

    # Update user role
    result = await users_collection.update_one(
        {"_id": ObjectId(user_id)}, 
        {"$set": {"role": role_name}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
        
    updated_user = await users_collection.find_one({"_id": ObjectId(user_id)})
    return UserResponse(id=str(updated_user["_id"]), **updated_user)

@router.get("/", response_model=List[UserResponse])
async def read_users(current_admin: UserResponse = Depends(get_current_admin)):
    users = []
    cursor = users_collection.find({})
    async for document in cursor:
        users.append(UserResponse(id=str(document["_id"]), **document))
    return users
