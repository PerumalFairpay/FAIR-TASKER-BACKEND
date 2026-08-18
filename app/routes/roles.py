from fastapi import APIRouter, HTTPException, status, Depends
from app.database import roles_collection, permissions_collection
from app.models import RoleCreate, RoleUpdate, RoleResponse, PermissionShortRef
from bson import ObjectId
from typing import List, Dict
from app.auth import verify_token, require_permission
from app.helper.response_helper import success_response, error_response

router = APIRouter(dependencies=[Depends(verify_token)])

async def get_permissions_map() -> Dict[str, str]:
    """Returns a dictionary mapping permission ID (str) to permission Name."""
    perm_map = {}
    async for perm in permissions_collection.find():
        perm_map[str(perm["_id"])] = perm["name"]
    return perm_map

@router.post("/", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permission("role:submit"))])
async def create_role(role: RoleCreate):
    existing_role = await roles_collection.find_one({"name": role.name})
    if existing_role:
        return error_response(message="Role with this name already exists", status_code=400)

    role_dict = role.dict()
    new_role = await roles_collection.insert_one(role_dict)
    created_role = await roles_collection.find_one({"_id": new_role.inserted_id})
     
    permission_ids = created_role.get("permissions", [])
    perm_map = await get_permissions_map()
    
    enriched_permissions = []
    for pid in permission_ids:
        pid_str = str(pid)
        if pid_str in perm_map:
            enriched_permissions.append(PermissionShortRef(id=pid_str, name=perm_map[pid_str]))
    
    data = RoleResponse(
        id=str(created_role["_id"]),
        name=created_role["name"],
        description=created_role.get("description"),
        permissions=enriched_permissions
    ).dict()
    
    return success_response(message="Role created successfully", data=data, status_code=201)

@router.get("/", dependencies=[Depends(require_permission("role:view"))])
async def get_roles():
    roles = []
    perm_map = await get_permissions_map()
    
    async for role in roles_collection.find():
        permission_ids = role.get("permissions", [])
        enriched_permissions = []
        for pid in permission_ids:
            pid_str = str(pid)
            if pid_str in perm_map:
                enriched_permissions.append(PermissionShortRef(id=pid_str, name=perm_map[pid_str]))

        roles.append(RoleResponse(
            id=str(role["_id"]),
            name=role["name"],
            description=role.get("description"),
            permissions=enriched_permissions
        ).dict())
        
    return success_response(message="Roles fetched successfully", data=roles)

@router.get("/{role_id}", dependencies=[Depends(require_permission("role:view"))])
async def get_role(role_id: str):
    if not ObjectId.is_valid(role_id):
        return error_response(message="Invalid role ID", status_code=400)
    
    role = await roles_collection.find_one({"_id": ObjectId(role_id)})
    if not role:
        return error_response(message="Role not found", status_code=404)
    
    perm_map = await get_permissions_map()
    permission_ids = role.get("permissions", [])
    enriched_permissions = []
    for pid in permission_ids:
        pid_str = str(pid)
        if pid_str in perm_map:
            enriched_permissions.append(PermissionShortRef(id=pid_str, name=perm_map[pid_str]))
    
    data = RoleResponse(
        id=str(role["_id"]),
        name=role["name"],
        description=role.get("description"),
        permissions=enriched_permissions
    ).dict()
    
    return success_response(message="Role fetched successfully", data=data)

@router.put("/{role_id}", dependencies=[Depends(require_permission("role:submit"))])
async def update_role(role_id: str, role_update: RoleUpdate):
    if not ObjectId.is_valid(role_id):
        return error_response(message="Invalid role ID", status_code=400)
    
    update_data = {k: v for k, v in role_update.dict().items() if v is not None}
    
    if not update_data:
        return error_response(message="No data to update", status_code=400)

    if "name" in update_data:
        existing_role = await roles_collection.find_one({"name": update_data["name"], "_id": {"$ne": ObjectId(role_id)}})
        if existing_role:
            return error_response(message="Role with this name already exists", status_code=400)

    result = await roles_collection.update_one({"_id": ObjectId(role_id)}, {"$set": update_data})
    
    if result.matched_count == 0:
        return error_response(message="Role not found", status_code=404)
        
    updated_role = await roles_collection.find_one({"_id": ObjectId(role_id)})
    
    perm_map = await get_permissions_map()
    permission_ids = updated_role.get("permissions", [])
    enriched_permissions = []
    for pid in permission_ids:
        pid_str = str(pid)
        if pid_str in perm_map:
            enriched_permissions.append(PermissionShortRef(id=pid_str, name=perm_map[pid_str]))

    data = RoleResponse(
        id=str(updated_role["_id"]),
        name=updated_role["name"],
        description=updated_role.get("description"),
        permissions=enriched_permissions
    ).dict()

    return success_response(message="Role updated successfully", data=data)

@router.delete("/{role_id}", dependencies=[Depends(require_permission("role:submit"))])
async def delete_role(role_id: str):
    if not ObjectId.is_valid(role_id):
        return error_response(message="Invalid role ID", status_code=400)
        
    result = await roles_collection.delete_one({"_id": ObjectId(role_id)})
    
    if result.deleted_count == 0:
        return error_response(message="Role not found", status_code=404)
        
    return success_response(message="Role deleted successfully")
