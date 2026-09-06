from fastapi import APIRouter, Depends, status
from app.models import RoleCreate, RoleUpdate
from app.services.api.role import RoleService
from app.auth import verify_token, require_permission
from app.helper.response_helper import success_response, error_response

router = APIRouter(dependencies=[Depends(verify_token)])


@router.post("/", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permission("role:submit"))])
async def create_role(role: RoleCreate):
    data, error = await RoleService.create(role)
    if error:
        status_code = 400 if "already exists" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(message="Role created successfully", data=data, status_code=201)


@router.get("/", dependencies=[Depends(require_permission("role:view"))])
async def get_roles():
    data, error = await RoleService.list()
    if error:
        return error_response(message=f"Failed to fetch roles: {error}", status_code=500)
    return success_response(message="Roles fetched successfully", data=data)


@router.get("/{role_id}", dependencies=[Depends(require_permission("role:view"))])
async def get_role(role_id: str):
    data, error = await RoleService.get(role_id)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(message="Role fetched successfully", data=data)


@router.put("/{role_id}", dependencies=[Depends(require_permission("role:submit"))])
async def update_role(role_id: str, role_update: RoleUpdate):
    data, error = await RoleService.update(role_id, role_update)
    if error:
        if "not found" in error.lower() or "invalid" in error.lower():
            status_code = 404
        elif "already exists" in error.lower() or "no data" in error.lower():
            status_code = 400
        else:
            status_code = 500
        return error_response(message=error, status_code=status_code)
    return success_response(message="Role updated successfully", data=data)


@router.delete("/{role_id}", dependencies=[Depends(require_permission("role:submit"))])
async def delete_role(role_id: str):
    success, error = await RoleService.delete(role_id)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(message="Role deleted successfully", data=[])
