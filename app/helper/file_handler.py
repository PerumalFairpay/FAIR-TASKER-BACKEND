import shutil
import os
from fastapi import UploadFile
from datetime import datetime
import uuid

class FileHandler:
    def __init__(self):
        self.upload_dir = "static/uploads"
        os.makedirs(self.upload_dir, exist_ok=True)

    async def upload_file(self, file: UploadFile) -> dict:
        try:
            filename = f"{uuid.uuid4()}_{file.filename}"
            file_path = os.path.join(self.upload_dir, filename)
            
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            return {
                "id": str(uuid.uuid4()),
                "filename": filename,
                "path": file_path,
                "url": f"/static/uploads/{filename}",
                "created_at": datetime.utcnow()
            }
        except Exception as e:
            raise e

    def get_file_url(self, file_path: str) -> str:
        # Assuming file_path is the relative path stored
        return f"/{file_path}" if file_path else None

file_handler = FileHandler()
