from fastapi import APIRouter, Depends
from app.services.api.user import UserService
from app.services.api.permission import PermissionService
from app.models import UserPermissionUpdate, UserUpdate
from app.helper.response_helper import success_response, error_response
from app.auth import verify_token, get_current_user
from typing import Optional

router = APIRouter(prefix="/users", tags=["users"], dependencies=[Depends(verify_token)])

@router.get("")
async def get_users(
    page: int = 1,
    limit: int = 10,
    search: Optional[str] = None,
    role: Optional[str] = None
):
    users_list, meta, error = await UserService.list(page=page, limit=limit, search=search, role=role)
    if error:
        return error_response(message=f"Failed to fetch users: {error}", status_code=500)
    return success_response(
        message="Users fetched successfully",
        data=users_list,
        meta=meta
    )

@router.get("/{user_id}/permissions")
async def get_user_permissions(
    user_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Fetch user permissions breakdown (role_permissions, direct_permissions, effective_permissions).
    Matches FLEETGLIDE-AI GET /api/users/{user_id}/permissions
    """
    detail, error = await PermissionService.get_user_permissions_detail(user_id)
    if error:
        return error_response(message=error, status_code=404)

    return success_response(
        message="User permissions fetched successfully",
        data=detail,
    )

@router.put("/{user_id}/permissions")
async def update_user_permissions(
    user_id: str,
    payload: UserPermissionUpdate,
    current_user: dict = Depends(get_current_user),
):
    """
    Update direct permissions for a user.
    Matches FLEETGLIDE-AI PUT /api/users/{user_id}/permissions
    """
    role_val = current_user.get("role")
    user_role_str = role_val.get("name", "").lower() if isinstance(role_val, dict) else str(role_val or "").lower()
    if user_role_str != "admin":
        return error_response(
            message="Only administrators can manage user permissions", status_code=403
        )

    detail, error = await PermissionService.update_user_permissions(
        user_id, payload.permission_ids
    )
    if error:
        return error_response(message=error, status_code=400)

    return success_response(
        message="User permissions updated successfully",
        data=detail,
    )

@router.get("/{user_id}")
async def get_user(user_id: str):
    user, error = await UserService.get(user_id)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(
        message="User fetched successfully",
        data=user
    )

@router.put("/{user_id}")
async def update_user(
    user_id: str,
    payload: UserUpdate,
    current_user: dict = Depends(get_current_user)
):
    update_data = payload.model_dump(exclude_unset=True)

    user, error = await UserService.update(user_id, update_data)

    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 400
        return error_response(message=error, status_code=status_code)

    return success_response(
        message="User updated successfully",
        data=user
    )

@router.delete("/{user_id}")
async def delete_user(user_id: str):
    success, error = await UserService.delete(user_id)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(
        message="User deleted successfully",
        data=[]
    )
