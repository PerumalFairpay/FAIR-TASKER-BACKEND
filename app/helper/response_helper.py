from fastapi.responses import JSONResponse
from typing import Any, Optional
from app.utils import normalize

def success_response(message: str, data: Any = None, meta: Any = None, status_code: int = 200):
    """
    Standard success response helper
    """
    content = {
        "success": True,
        "message": message,
        "data": normalize(data) if data is not None else None
    }
    if meta:
        content["meta"] = normalize(meta)
    return JSONResponse(status_code=status_code, content=content)

def error_response(message: str, errors: Any = None, status_code: int = 400):
    """
    Standard error response helper
    """
    content = {
        "success": False,
        "message": message,
        "errors": normalize(errors) if errors is not None else None
    }
    return JSONResponse(status_code=status_code, content=content)
