from fastapi import APIRouter, HTTPException, status, Depends
from app.database import permissions_collection
from app.models import PermissionCreate, PermissionUpdate, PermissionResponse
from bson import ObjectId
from typing import List
from app.auth import verify_token, require_permission
from app.helper.response_helper import success_response, error_response

router = APIRouter(prefix="/permissions", tags=["permissions"], dependencies=[Depends(verify_token)])

@router.post("/", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permission("permission:submit"))])
async def create_permission(permission: PermissionCreate):
    existing_perm = await permissions_collection.find_one({"slug": permission.slug})
    if existing_perm:
        return error_response(message="Permission with this slug already exists", status_code=400)

    perm_dict = permission.dict()
    new_perm = await permissions_collection.insert_one(perm_dict)
    created_perm = await permissions_collection.find_one({"_id": new_perm.inserted_id})
    
    data = PermissionResponse(**created_perm, id=str(created_perm["_id"])).dict()
    return success_response(message="Permission created successfully", data=data, status_code=201)

@router.get("/", dependencies=[Depends(require_permission("permission:view"))])
async def get_permissions():
    permissions = []
    async for perm in permissions_collection.find():
        permissions.append(PermissionResponse(**perm, id=str(perm["_id"])).dict())
    return success_response(message="Permissions fetched successfully", data=permissions)

@router.get("/{permission_id}", dependencies=[Depends(require_permission("permission:view"))])
async def get_permission(permission_id: str):
    if not ObjectId.is_valid(permission_id):
        return error_response(message="Invalid permission ID", status_code=400)
    
    perm = await permissions_collection.find_one({"_id": ObjectId(permission_id)})
    if not perm:
        return error_response(message="Permission not found", status_code=404)
    
    data = PermissionResponse(**perm, id=str(perm["_id"])).dict()
    return success_response(message="Permission fetched successfully", data=data)

@router.put("/{permission_id}", dependencies=[Depends(require_permission("permission:submit"))])
async def update_permission(permission_id: str, perm_update: PermissionUpdate):
    if not ObjectId.is_valid(permission_id):
        return error_response(message="Invalid permission ID", status_code=400)
    
    update_data = {k: v for k, v in perm_update.dict().items() if v is not None}
    
    if not update_data:
        return error_response(message="No data to update", status_code=400)

    if "slug" in update_data:
        existing_perm = await permissions_collection.find_one({"slug": update_data["slug"], "_id": {"$ne": ObjectId(permission_id)}})
        if existing_perm:
            return error_response(message="Permission with this slug already exists", status_code=400)

    result = await permissions_collection.update_one({"_id": ObjectId(permission_id)}, {"$set": update_data})
    
    if result.matched_count == 0:
        return error_response(message="Permission not found", status_code=404)
        
    updated_perm = await permissions_collection.find_one({"_id": ObjectId(permission_id)})
    data = PermissionResponse(**updated_perm, id=str(updated_perm["_id"])).dict()
    return success_response(message="Permission updated successfully", data=data)

@router.delete("/{permission_id}", dependencies=[Depends(require_permission("permission:submit"))])
async def delete_permission(permission_id: str):
    if not ObjectId.is_valid(permission_id):
        return error_response(message="Invalid permission ID", status_code=400)
        
    result = await permissions_collection.delete_one({"_id": ObjectId(permission_id)})
    
    if result.deleted_count == 0:
        return error_response(message="Permission not found", status_code=404)
        
    return success_response(message="Permission deleted successfully")
