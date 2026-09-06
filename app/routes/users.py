from fastapi import APIRouter, Depends
from app.services.api.user import UserService
from app.helper.response_helper import success_response, error_response
from app.auth import verify_token, require_permission
from typing import Optional

router = APIRouter(prefix="/users", tags=["users"], dependencies=[Depends(verify_token)])

@router.get("", dependencies=[Depends(require_permission("employee:view"))])
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

@router.get("/{user_id}", dependencies=[Depends(require_permission("employee:view"))])
async def get_user(user_id: str):
    user, error = await UserService.get(user_id)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(
        message="User fetched successfully",
        data=user
    )

@router.delete("/{user_id}", dependencies=[Depends(require_permission("employee:submit"))])
async def delete_user(user_id: str):
    success, error = await UserService.delete(user_id)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(
        message="User deleted successfully",
        data=[]
    )
