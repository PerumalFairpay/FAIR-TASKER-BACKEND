from fastapi import APIRouter, Depends, status
from app.models import PermissionCreate, PermissionUpdate
from app.services.api.permission import PermissionService
from app.auth import verify_token, require_permission
from app.helper.response_helper import success_response, error_response

router = APIRouter(prefix="/permissions", tags=["permissions"], dependencies=[Depends(verify_token)])


@router.post("/", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permission("permission:submit"))])
async def create_permission(permission: PermissionCreate):
    data, error = await PermissionService.create(permission)
    if error:
        status_code = 400 if "already exists" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(message="Permission created successfully", data=data, status_code=201)


@router.get("/", dependencies=[Depends(require_permission("permission:view"))])
async def get_permissions():
    data, error = await PermissionService.list()
    if error:
        return error_response(message=f"Failed to fetch permissions: {error}", status_code=500)
    return success_response(message="Permissions fetched successfully", data=data)


@router.get("/{permission_id}", dependencies=[Depends(require_permission("permission:view"))])
async def get_permission(permission_id: str):
    data, error = await PermissionService.get(permission_id)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(message="Permission fetched successfully", data=data)


@router.put("/{permission_id}", dependencies=[Depends(require_permission("permission:submit"))])
async def update_permission(permission_id: str, perm_update: PermissionUpdate):
    data, error = await PermissionService.update(permission_id, perm_update)
    if error:
        if "not found" in error.lower() or "invalid" in error.lower():
            status_code = 404
        elif "already exists" in error.lower() or "no data" in error.lower():
            status_code = 400
        else:
            status_code = 500
        return error_response(message=error, status_code=status_code)
    return success_response(message="Permission updated successfully", data=data)


@router.delete("/{permission_id}", dependencies=[Depends(require_permission("permission:submit"))])
async def delete_permission(permission_id: str):
    success, error = await PermissionService.delete(permission_id)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(message="Permission deleted successfully", data=[])
