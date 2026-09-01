from fastapi import APIRouter, Depends
from typing import Dict, Any
from app.auth import verify_token
from app.services.api.settings import SettingsService
from app.helper.response_helper import success_response, error_response

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/public")
async def get_public_settings():
    """Public endpoint - no authentication required"""
    data, error = await SettingsService.get_public_settings()
    if error:
        return error_response(message=f"Server Error: {error}", status_code=500)
    return success_response(message="Public settings fetched", data=data)


@router.get("/", dependencies=[Depends(verify_token)])
async def get_settings():
    data, error = await SettingsService.get_settings()
    if error:
        return error_response(message=f"Server Error: {error}", status_code=500)
    return success_response(message="Settings fetched", data=data)


@router.put("/", dependencies=[Depends(verify_token)])
async def update_settings(settings: Dict[str, Any]):
    data, error = await SettingsService.update_settings(settings)
    if error:
        return error_response(message=f"Server Error: {error}", status_code=500)
    return success_response(message="Settings updated", data=data)

