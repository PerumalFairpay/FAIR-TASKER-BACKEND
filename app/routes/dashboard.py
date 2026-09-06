from fastapi import APIRouter, Depends
from app.auth import get_current_user, verify_token
from app.services.api.dashboard import DashboardService
from app.helper.response_helper import success_response, error_response

router = APIRouter(prefix="/dashboard", tags=["dashboard"], dependencies=[Depends(verify_token)])


@router.get("")
async def get_dashboard_data(current_user: dict = Depends(get_current_user)):
    data, error = await DashboardService.get_dashboard_data(current_user)
    if error:
        status_code = 404 if "not found" in error.lower() else (400 if "no employee" in error.lower() else 500)
        return error_response(message=error, status_code=status_code)
    return success_response(message="Dashboard data fetched successfully", data=data)
