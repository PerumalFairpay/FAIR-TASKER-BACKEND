from fastapi import APIRouter, HTTPException, Depends
from app.helper.response_helper import success_response, error_response
from app.crud.repository import repository as repo
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
    try:
        users_list, total_items = await repo.get_users(page, limit, search, role)
        total_pages = (total_items + limit - 1) // limit
        meta = {
            "current_page": page,
            "total_pages": total_pages,
            "total_items": total_items,
            "limit": limit
        }
        return success_response(
            message="Users fetched successfully",
            data=users_list,
            meta=meta
        )
    except Exception as e:
        return error_response(message=str(e), status_code=500)

@router.get("/{user_id}", dependencies=[Depends(require_permission("employee:view"))])
async def get_user(user_id: str):
    try:
        user = await repo.get_user_by_id(user_id)
        if not user:
            return error_response(message="User not found", status_code=404)
        return success_response(
            message="User fetched successfully",
            data=user
        )
    except Exception as e:
        return error_response(message=str(e), status_code=500)

@router.delete("/{user_id}", dependencies=[Depends(require_permission("employee:submit"))])
async def delete_user(user_id: str):
    try:
        success = await repo.delete_user(user_id)
        if not success:
            return error_response(message="User not found", status_code=404)
        return success_response(
            message="User deleted successfully"
        )
    except Exception as e:
        return error_response(message=str(e), status_code=500)
