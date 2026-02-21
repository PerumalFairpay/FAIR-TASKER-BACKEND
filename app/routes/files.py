from fastapi import APIRouter
from fastapi.responses import JSONResponse, StreamingResponse
from app.helper.file_handler import file_handler as handler

router = APIRouter()

@router.get("/view/{file_id:path}")
async def view_file(file_id: str, filename: str = None, content_type: str = None):
    try:
        # file_id may be "subfolder/uuid" or just "uuid" — we only need the uuid part
        actual_id = file_id.split("/")[-1]
        result = handler.get_file(actual_id)
        if not result:
            return JSONResponse(status_code=404, content={"message": "File not found", "success": False})
        
        file_info = handler.get_file_info(actual_id)
        
        # Determine the final filename
        final_filename = "file"
        if file_info:
            original_key = file_info.split("/")[-1]
            final_filename = original_key
            
            # If a custom filename is provided, use it
            if filename:
                # specific logic to handle extension
                # If filename_param doesn't have extension, append it from original
                ext = ""
                if "." in original_key:
                    ext = "." + original_key.split(".")[-1]
                
                if "." not in filename and ext:
                    final_filename = f"{filename}{ext}"
                else:
                    final_filename = filename

        # Use provided content_type or fallback to stored content type
        final_media_type = content_type or result.get("ContentType", "application/octet-stream")

        return StreamingResponse(
            result.get("Body"), 
            media_type=final_media_type, 
            headers={"Content-Disposition": f'inline; filename="{final_filename}"'}
        )
    except Exception as e:
        return JSONResponse(status_code=500, content={"message": str(e), "success": False})
