from fastapi import APIRouter
from fastapi.responses import JSONResponse, StreamingResponse
from app.helper.file_handler import file_handler as handler

router = APIRouter()

@router.get("/view/{file_id}")
async def view_file(file_id: str):
    try:
        result = handler.get_file(file_id)
        if not result:
            return JSONResponse(status_code=404, content={"message": "File not found", "success": False})
        
        file_info = handler.get_file_info(file_id)
        filename = "file"
        if file_info:
            filename = file_info.split("/")[-1]

        return StreamingResponse(
            result.get("Body"), 
            media_type=result.get("ContentType", "application/octet-stream"), 
            headers={"Content-Disposition": f'inline; filename="{filename}"'}
        )
    except Exception as e:
        return JSONResponse(status_code=500, content={"message": str(e), "success": False})
