from fastapi.responses import JSONResponse
from typing import Any, Optional

def success_response(message: str, data: Any = None, meta: Any = None, status_code: int = 200):
    """
    Standard success response helper
    """
    content = {
        "success": True,
        "message": message,
        "data": data
    }
    if meta:
        content["meta"] = meta
    return JSONResponse(status_code=status_code, content=content)

def error_response(message: str, errors: Any = None, status_code: int = 400):
    """
    Standard error response helper
    """
    content = {
        "success": False,
        "message": message,
        "errors": errors
    }
    return JSONResponse(status_code=status_code, content=content)
