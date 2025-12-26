from fastapi import APIRouter, HTTPException, status, Depends
from typing import List
from app.database import roles_collection
from app.models import RoleCreate, RoleResponse, RoleUpdate, UserResponse
from app.dependencies import get_current_admin
from bson import ObjectId

router = APIRouter()

@router.post("/", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_role(role: RoleCreate, current_admin: UserResponse = Depends(get_current_admin)):
    existing_role = await roles_collection.find_one({"name": role.name})
    if existing_role:
        raise HTTPException(status_code=400, detail="Role with this name already exists")
    
    role_dict = role.dict()
    new_role = await roles_collection.insert_one(role_dict)
    created_role = await roles_collection.find_one({"_id": new_role.inserted_id})
    
    return RoleResponse(id=str(created_role["_id"]), **role_dict)

@router.get("/", response_model=List[RoleResponse])
async def read_roles():
    roles = []
    cursor = roles_collection.find({})
    async for document in cursor:
        roles.append(RoleResponse(id=str(document["_id"]), **document))
    return roles

@router.get("/{role_id}", response_model=RoleResponse)
async def read_role(role_id: str):
    if not ObjectId.is_valid(role_id):
        raise HTTPException(status_code=400, detail="Invalid role ID")
        
    role = await roles_collection.find_one({"_id": ObjectId(role_id)})
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
        
    return RoleResponse(id=str(role["_id"]), **role)

@router.put("/{role_id}", response_model=RoleResponse)
async def update_role(role_id: str, role_update: RoleUpdate, current_admin: UserResponse = Depends(get_current_admin)):
    if not ObjectId.is_valid(role_id):
        raise HTTPException(status_code=400, detail="Invalid role ID")
    
    # Filter out None values
    update_data = {k: v for k, v in role_update.dict().items() if v is not None}
    
    if not update_data:
         raise HTTPException(status_code=400, detail="No valid fields to update")

    result = await roles_collection.update_one(
        {"_id": ObjectId(role_id)}, 
        {"$set": update_data}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Role not found")
        
    updated_role = await roles_collection.find_one({"_id": ObjectId(role_id)})
    return RoleResponse(id=str(updated_role["_id"]), **updated_role)

@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(role_id: str, current_admin: UserResponse = Depends(get_current_admin)):
    if not ObjectId.is_valid(role_id):
        raise HTTPException(status_code=400, detail="Invalid role ID")
        
    result = await roles_collection.delete_one({"_id": ObjectId(role_id)})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Role not found")
    return
