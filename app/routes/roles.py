from fastapi import APIRouter, HTTPException, status, Depends
from app.database import roles_collection, permissions_collection
from app.models import RoleCreate, RoleUpdate, RoleResponse, PermissionShortRef
from bson import ObjectId
from typing import List, Dict
from app.auth import verify_token, require_permission

router = APIRouter(dependencies=[Depends(verify_token)])

async def get_permissions_map() -> Dict[str, str]:
    """Returns a dictionary mapping permission ID (str) to permission Name."""
    perm_map = {}
    async for perm in permissions_collection.find():
        perm_map[str(perm["_id"])] = perm["name"]
    return perm_map

@router.post("/", response_model=RoleResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permission("role:submit"))])
async def create_role(role: RoleCreate):
    existing_role = await roles_collection.find_one({"name": role.name})
    if existing_role:
        raise HTTPException(status_code=400, detail="Role with this name already exists")

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
    
    return RoleResponse(
        id=str(created_role["_id"]),
        name=created_role["name"],
        description=created_role.get("description"),
        permissions=enriched_permissions
    )

@router.get("/", response_model=List[RoleResponse], dependencies=[Depends(require_permission("role:view"))])
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
        ))
    return roles

@router.get("/{role_id}", response_model=RoleResponse, dependencies=[Depends(require_permission("role:view"))])
async def get_role(role_id: str):
    if not ObjectId.is_valid(role_id):
        raise HTTPException(status_code=400, detail="Invalid role ID")
    
    role = await roles_collection.find_one({"_id": ObjectId(role_id)})
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    perm_map = await get_permissions_map()
    permission_ids = role.get("permissions", [])
    enriched_permissions = []
    for pid in permission_ids:
        pid_str = str(pid)
        if pid_str in perm_map:
            enriched_permissions.append(PermissionShortRef(id=pid_str, name=perm_map[pid_str]))
    
    return RoleResponse(
        id=str(role["_id"]),
        name=role["name"],
        description=role.get("description"),
        permissions=enriched_permissions
    )

@router.put("/{role_id}", response_model=RoleResponse, dependencies=[Depends(require_permission("role:submit"))])
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
    
    perm_map = await get_permissions_map()
    permission_ids = updated_role.get("permissions", [])
    enriched_permissions = []
    for pid in permission_ids:
        pid_str = str(pid)
        if pid_str in perm_map:
            enriched_permissions.append(PermissionShortRef(id=pid_str, name=perm_map[pid_str]))

    return RoleResponse(
        id=str(updated_role["_id"]),
        name=updated_role["name"],
        description=updated_role.get("description"),
        permissions=enriched_permissions
    )

@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_permission("role:submit"))])
async def delete_role(role_id: str):
    if not ObjectId.is_valid(role_id):
        raise HTTPException(status_code=400, detail="Invalid role ID")
        
    result = await roles_collection.delete_one({"_id": ObjectId(role_id)})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Role not found")
