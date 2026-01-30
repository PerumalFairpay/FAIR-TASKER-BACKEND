import os
import uuid
import boto3
import io
from fastapi import UploadFile
from typing import List, Dict, Union, Optional
from botocore.exceptions import ClientError
from app.core.config import API_URL, AWS_BUCKET_NAME, AWS_REGION, AWS_ACCESS_KEY, AWS_SECRET_KEY


class FileHandler:
    def __init__(
        self,
        storage_type: str = "local",  # 'local' or 's3'
        local_dir: str = "uploads"
    ):
        self.storage_type = storage_type
        self.local_dir = local_dir
        self.aws_bucket = AWS_BUCKET_NAME
        self.aws_region = AWS_REGION

        if self.storage_type == "local":
            os.makedirs(self.local_dir, exist_ok=True)

        elif self.storage_type == "s3":
            self.s3_client = boto3.client(
                "s3",
                region_name=AWS_REGION,
                aws_access_key_id=AWS_ACCESS_KEY,
                aws_secret_access_key=AWS_SECRET_KEY,
            )
        else:
            raise ValueError("Invalid storage_type. Use 'local' or 's3'.")
    
    # --------------- Upload File ----------------- #
    async def upload_file(self, file: UploadFile) -> Dict[str, str]:
        result = None
        file_id = str(uuid.uuid4())
        file_ext = os.path.splitext(file.filename)[1] or ""
        file_name = f"{file_id}{file_ext}"

        if self.storage_type == "local":
            file_path = os.path.join(self.local_dir, file_name)
            with open(file_path, "wb") as f:
                f.write(await file.read())
                file_url = f"/files/{file_name}"  # can map via route
                result = {"id": file_id, "url": file_url, "name": file.filename}
        elif self.storage_type == "s3":
            try:
                file_name = f"dev-uploads/{file_name}"
                file_bytes = await file.read()   # <-- async
                extra_args = {"ServerSideEncryption": "AES256"}
                if file.content_type:
                    extra_args["ContentType"] = file.content_type
                
                self.s3_client.upload_fileobj(
                        io.BytesIO(file_bytes),
                        self.aws_bucket,
                        file_name,
                        ExtraArgs=extra_args,
                    )
                # file_url = f"https://{self.aws_bucket}.s3.{self.aws_region}.amazonaws.com/{file_name}"
                file_url = self.get_file_api_url(file_id)
                result = {"id": file_id, "url": file_url, "name": file.filename}
            except ClientError as e:
                raise Exception(f"Failed to upload {file.filename}: {e}")
        return result

    # --------------- Save Bytes ----------------- #
    async def save_from_bytes(self, file_bytes: bytes, filename: str, content_type: str = "application/pdf") -> Dict[str, str]:
        result = None
        file_id = str(uuid.uuid4())
        file_ext = os.path.splitext(filename)[1] or ""
        # Ensure ID is part of filename for uniqueness if needed, or just use ID
        final_filename = f"{file_id}{file_ext}"

        if self.storage_type == "local":
            file_path = os.path.join(self.local_dir, final_filename)
            with open(file_path, "wb") as f:
                f.write(file_bytes)
                file_url = f"/files/{final_filename}"
                result = {"id": file_id, "url": file_url, "name": filename}
        elif self.storage_type == "s3":
            try:
                key = f"dev-uploads/{final_filename}"
                extra_args = {"ServerSideEncryption": "AES256"}
                if content_type:
                    extra_args["ContentType"] = content_type
                
                self.s3_client.put_object(
                    Body=file_bytes,
                    Bucket=self.aws_bucket,
                    Key=key,
                    **extra_args
                )
                file_url = self.get_file_api_url(file_id)
                result = {"id": file_id, "url": file_url, "name": filename}
            except ClientError as e:
                raise Exception(f"Failed to upload {filename}: {e}")
        return result

    # ---------------- Upload Files ---------------- #
    async def upload_files(self, files: List[UploadFile]) -> List[Dict[str, str]]:
        results = []
        for file in files:
            file_id = str(uuid.uuid4())
            file_ext = os.path.splitext(file.filename)[1] or ""
            file_name = f"{file_id}{file_ext}"

            if self.storage_type == "local":
                file_path = os.path.join(self.local_dir, file_name)
                with open(file_path, "wb") as f:
                    f.write(await file.read())
                file_url = f"/files/{file_name}"  # can map via route
                results.append({"id": file_id, "url": file_url, "name": file.filename})

            elif self.storage_type == "s3":
                try:
                    file_name = f"dev-uploads/{file_name}"
                    self.s3_client.upload_fileobj(
                        file.file,
                        self.aws_bucket,
                        file_name,
                        ExtraArgs={"ServerSideEncryption": "AES256"},
                    )
                    # file_url = f"https://{self.aws_bucket}.s3.{self.aws_region}.amazonaws.com/{file_name}"
                    file_url = self.get_file_api_url(file_id)
                    results.append({"id": file_id, "url": file_url, "name": file.filename})
                except ClientError as e:
                    raise Exception(f"Failed to upload {file.filename}: {e}")

        return results

    # ---------------- Retrieve File URL ---------------- #
    def get_file_url(self, file_id: str) -> Optional[str]:
        if self.storage_type == "local":
            for f in os.listdir(self.local_dir):
                if f.startswith(file_id):
                    return f"/files/{f}"
            return None

        elif self.storage_type == "s3":
            # Assuming filename = id.ext pattern
            try:
                return self.get_file_api_url(file_id)
                # prefix = self.get_file_path(file_id)
                # if not prefix:
                #     return None
                # return self.s3_client.generate_presigned_url('get_object', Params={'Bucket': self.aws_bucket, 'Key': prefix, "ResponseContentDisposition": "inline"}, ExpiresIn=3600)
            except ClientError:
                return None

    def get_file_path(self, file_id: str) -> Optional[str]:
        if self.storage_type == "local":
            for f in os.listdir(self.local_dir):
                if f.startswith(file_id):
                    return os.path.join(self.local_dir, f)
            return None

        elif self.storage_type == "s3":
            try:
                prefix = f"dev-uploads/{file_id}"
                objs = self.s3_client.list_objects_v2(Bucket=self.aws_bucket, Prefix=prefix)
                for obj in objs.get("Contents", []):
                    return obj["Key"]
            except ClientError:
                return None
    
    def get_file(self, file_id: str) -> Optional[str]:
        if self.storage_type == "local":
            for f in os.listdir(self.local_dir):
                if f.startswith(file_id):
                    return os.path.splitext(f)[1]
            return None

        elif self.storage_type == "s3":
            try:
                prefix = self.get_file_path(file_id)
                if not prefix:
                    return None
                objs = self.s3_client.get_object(Bucket=self.aws_bucket, Key=prefix)
                return objs
            except ClientError:
                return None
    
    # ---------------- Download File ---------------- #
    def get_file_info(self, file_id: str) -> Optional[str]:
        if self.storage_type == "local":
            for f in os.listdir(self.local_dir):
                if f.startswith(file_id):
                    return os.path.join(self.local_dir, f)
            return None

        elif self.storage_type == "s3":
            try:
                prefix = self.get_file_path(file_id=file_id)
                return prefix
            except ClientError:
                return None
    
    def get_file_api_url(self, file_id: str) -> Optional[str]:
        if self.storage_type == "local":
            return f"{API_URL}/files/{file_id}"
        elif self.storage_type == "s3":
            if file_id and file_id != "" and len(file_id) > 0:
                return f"{API_URL}/api/view/{file_id}"
            return None

    # ---------------- Delete File ---------------- #
    def delete_file(self, file_id: str) -> bool:
        if self.storage_type == "local":
            for f in os.listdir(self.local_dir):
                if f.startswith(file_id):
                    os.remove(os.path.join(self.local_dir, f))
                    return True
            return False

        elif self.storage_type == "s3":
            try:
                objs = self.s3_client.list_objects_v2(Bucket=self.aws_bucket)
                for obj in objs.get("Contents", []):
                    if obj["Key"].startswith(file_id):
                        self.s3_client.delete_object(Bucket=self.aws_bucket, Key=obj["Key"])
                        return True
                return False
            except ClientError:
                return False

# Singleton class
file_handler = FileHandler(storage_type="s3")

async def save_upload_file(file: UploadFile, folder: str = None) -> str:
    "Helper to save a file using the FileHandler instance"
    if not file:
        return None
    
    # uses just the file handler's upload_file method
    result = await file_handler.upload_file(file)
    return result["url"]
