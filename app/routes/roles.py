from fastapi import APIRouter, HTTPException, status, Depends
from app.database import roles_collection
from app.models import RoleCreate, RoleUpdate, RoleResponse
from bson import ObjectId
from typing import List
from app.auth import verify_token

router = APIRouter(dependencies=[Depends(verify_token)])

@router.post("/", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_role(role: RoleCreate):
    existing_role = await roles_collection.find_one({"name": role.name})
    if existing_role:
        raise HTTPException(status_code=400, detail="Role with this name already exists")

    role_dict = role.dict()
    new_role = await roles_collection.insert_one(role_dict)
    created_role = await roles_collection.find_one({"_id": new_role.inserted_id})
    return RoleResponse(**created_role, id=str(created_role["_id"]))

@router.get("/", response_model=List[RoleResponse])
async def get_roles():
    roles = []
    async for role in roles_collection.find():
        roles.append(RoleResponse(**role, id=str(role["_id"])))
    return roles

@router.get("/{role_id}", response_model=RoleResponse)
async def get_role(role_id: str):
    if not ObjectId.is_valid(role_id):
        raise HTTPException(status_code=400, detail="Invalid role ID")
    
    role = await roles_collection.find_one({"_id": ObjectId(role_id)})
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    return RoleResponse(**role, id=str(role["_id"]))

@router.put("/{role_id}", response_model=RoleResponse)
async def update_role(role_id: str, role_update: RoleUpdate):
    if not ObjectId.is_valid(role_id):
        raise HTTPException(status_code=400, detail="Invalid role ID")
    
    update_data = {k: v for k, v in role_update.dict().items() if v is not None}
    
    if not update_data:
        raise HTTPException(status_code=400, detail="No data to update")

    if "name" in update_data:
        existing_role = await roles_collection.find_one({"name": update_data["name"], "_id": {"$ne": ObjectId(role_id)}})
        if existing_role:
            raise HTTPException(status_code=400, detail="Role with this name already exists")

    result = await roles_collection.update_one({"_id": ObjectId(role_id)}, {"$set": update_data})
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Role not found")
        
    updated_role = await roles_collection.find_one({"_id": ObjectId(role_id)})
    return RoleResponse(**updated_role, id=str(updated_role["_id"]))

@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(role_id: str):
    if not ObjectId.is_valid(role_id):
        raise HTTPException(status_code=400, detail="Invalid role ID")
        
    result = await roles_collection.delete_one({"_id": ObjectId(role_id)})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Role not found")
