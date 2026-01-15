from fastapi import APIRouter, HTTPException, status, Depends
from app.database import permissions_collection
from app.models import PermissionCreate, PermissionUpdate, PermissionResponse
from bson import ObjectId
from typing import List
from app.auth import verify_token

router = APIRouter(prefix="/permissions", tags=["permissions"], dependencies=[Depends(verify_token)])

@router.post("/", response_model=PermissionResponse, status_code=status.HTTP_201_CREATED)
async def create_permission(permission: PermissionCreate):
    existing_perm = await permissions_collection.find_one({"slug": permission.slug})
    if existing_perm:
        raise HTTPException(status_code=400, detail="Permission with this slug already exists")

    perm_dict = permission.dict()
    new_perm = await permissions_collection.insert_one(perm_dict)
    created_perm = await permissions_collection.find_one({"_id": new_perm.inserted_id})
    return PermissionResponse(**created_perm, id=str(created_perm["_id"]))

@router.get("/", response_model=List[PermissionResponse])
async def get_permissions():
    permissions = []
    async for perm in permissions_collection.find():
        permissions.append(PermissionResponse(**perm, id=str(perm["_id"])))
    return permissions

@router.get("/{permission_id}", response_model=PermissionResponse)
async def get_permission(permission_id: str):
    if not ObjectId.is_valid(permission_id):
        raise HTTPException(status_code=400, detail="Invalid permission ID")
    
    perm = await permissions_collection.find_one({"_id": ObjectId(permission_id)})
    if not perm:
        raise HTTPException(status_code=404, detail="Permission not found")
    
    return PermissionResponse(**perm, id=str(perm["_id"]))

@router.put("/{permission_id}", response_model=PermissionResponse)
async def update_permission(permission_id: str, perm_update: PermissionUpdate):
    if not ObjectId.is_valid(permission_id):
        raise HTTPException(status_code=400, detail="Invalid permission ID")
    
    update_data = {k: v for k, v in perm_update.dict().items() if v is not None}
    
    if not update_data:
        raise HTTPException(status_code=400, detail="No data to update")

    if "slug" in update_data:
        existing_perm = await permissions_collection.find_one({"slug": update_data["slug"], "_id": {"$ne": ObjectId(permission_id)}})
        if existing_perm:
            raise HTTPException(status_code=400, detail="Permission with this slug already exists")

    result = await permissions_collection.update_one({"_id": ObjectId(permission_id)}, {"$set": update_data})
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Permission not found")
        
    updated_perm = await permissions_collection.find_one({"_id": ObjectId(permission_id)})
    return PermissionResponse(**updated_perm, id=str(updated_perm["_id"]))

@router.delete("/{permission_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_permission(permission_id: str):
    if not ObjectId.is_valid(permission_id):
        raise HTTPException(status_code=400, detail="Invalid permission ID")
        
    result = await permissions_collection.delete_one({"_id": ObjectId(permission_id)})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Permission not found")
