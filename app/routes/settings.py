from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from app.crud.repository import repository as repo
from typing import Dict, Any
from app.auth import verify_token

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/", dependencies=[Depends(verify_token)])
async def get_settings():
    try:
        configs = await repo.get_system_configurations()

        # Group settings
        grouped = {}
        for config in configs:
            group = config.get("group", "Other")
            if group not in grouped:
                grouped[group] = []
            grouped[group].append(config)

        return JSONResponse(
            status_code=200,
            content={"message": "Settings fetched", "success": True, "data": grouped},
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Server Error: {str(e)}", "success": False},
        )


@router.put("/", dependencies=[Depends(verify_token)])
async def update_settings(settings: Dict[str, Any]):
    try:
        updated = await repo.update_system_configurations(settings)

        # Re-group
        grouped = {}
        for config in updated:
            group = config.get("group", "Other")
            if group not in grouped:
                grouped[group] = []
            grouped[group].append(config)

        return JSONResponse(
            status_code=200,
            content={"message": "Settings updated", "success": True, "data": grouped},
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Server Error: {str(e)}", "success": False},
        )
