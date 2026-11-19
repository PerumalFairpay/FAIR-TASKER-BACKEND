from fastapi import APIRouter, Depends, status
from app.models import RoleCreate, RoleUpdate
from app.services.api.role import RoleService
from app.services.api.permission import PermissionService
from app.auth import verify_token, get_current_user
from app.helper.response_helper import success_response, error_response

router = APIRouter(dependencies=[Depends(verify_token)])


@router.get("/permissions")
async def get_permissions(current_user: dict = Depends(get_current_user)):
    """
    List all available permissions grouped/ordered by module and name.
    Matches FLEETGLIDE-AI GET /api/roles/permissions
    """
    perms = await PermissionService.list()
    return success_response(message="Permissions fetched successfully", data=perms)


@router.get("/all")
async def get_all_roles():
    """
    Matches FLEETGLIDE-AI GET /api/roles/all
    """
    data, error = await RoleService.list()
    if error:
        return error_response(message=f"Failed to fetch roles: {error}", status_code=500)
    return success_response(message="Roles fetched successfully", data=data)


@router.get("/")
async def get_roles():
    data, error = await RoleService.list()
    if error:
        return error_response(message=f"Failed to fetch roles: {error}", status_code=500)
    return success_response(message="Roles fetched successfully", data=data)


@router.post("/create", status_code=status.HTTP_201_CREATED)
async def create_role_post(role: RoleCreate, current_user: dict = Depends(get_current_user)):
    """
    Matches FLEETGLIDE-AI POST /api/roles/create
    """
    role_val = current_user.get("role")
    user_role_str = role_val.get("name", "").lower() if isinstance(role_val, dict) else str(role_val or "").lower()
    if user_role_str != "admin":
        return error_response(message="Only administrators can create roles", status_code=403)

    data, error = await RoleService.create(role)
    if error:
        status_code = 400 if "already exists" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(message="Role created successfully", data=data, status_code=201)


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_role(role: RoleCreate):
    data, error = await RoleService.create(role)
    if error:
        status_code = 400 if "already exists" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(message="Role created successfully", data=data, status_code=201)


@router.get("/{role_id}")
async def get_role(role_id: str):
    data, error = await RoleService.get(role_id)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(message="Role fetched successfully", data=data)


@router.put("/update/{role_id}")
async def update_role_put(role_id: str, role_update: RoleUpdate, current_user: dict = Depends(get_current_user)):
    """
    Matches FLEETGLIDE-AI PUT /api/roles/update/{role_id}
    """
    role_val = current_user.get("role")
    user_role_str = role_val.get("name", "").lower() if isinstance(role_val, dict) else str(role_val or "").lower()
    if user_role_str != "admin":
        return error_response(message="Only administrators can update roles", status_code=403)

    data, error = await RoleService.update(role_id, role_update)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 400
        return error_response(message=error, status_code=status_code)
    return success_response(message="Role updated successfully", data=data)


@router.put("/{role_id}")
async def update_role(role_id: str, role_update: RoleUpdate):
    data, error = await RoleService.update(role_id, role_update)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 400
        return error_response(message=error, status_code=status_code)
    return success_response(message="Role updated successfully", data=data)


@router.delete("/delete/{role_id}")
async def delete_role_del(role_id: str, current_user: dict = Depends(get_current_user)):
    """
    Matches FLEETGLIDE-AI DELETE /api/roles/delete/{role_id}
    """
    role_val = current_user.get("role")
    user_role_str = role_val.get("name", "").lower() if isinstance(role_val, dict) else str(role_val or "").lower()
    if user_role_str != "admin":
        return error_response(message="Only administrators can delete roles", status_code=403)

    success, error = await RoleService.delete(role_id)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(message="Role deleted successfully", data=[])


@router.delete("/{role_id}")
async def delete_role(role_id: str):
    success, error = await RoleService.delete(role_id)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(message="Role deleted successfully", data=[])
