from fastapi import APIRouter, Depends, Form, File, UploadFile
from typing import Optional
from app.auth import get_current_user
from app.crud.repository import repository as repo
from app.helper.response_helper import success_response, error_response
from app.models import EmployeeUpdate
from app.helper.file_handler import file_handler
from app.utils import normalize, verify_password, get_password_hash
from pydantic import BaseModel
from bson import ObjectId
from datetime import datetime

router = APIRouter(prefix="/profile", tags=["profile"])

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

@router.get("/")
async def get_profile(current_user: dict = Depends(get_current_user)):
    try:
        employee_id = current_user.get("employee_no_id")
        if not employee_id:
             # If no employee_no_id link, return user data as fallback
             current_user.pop("hashed_password", None)
             return success_response(message="User profile fetched", data=current_user)
        
        # Find employee by employee_no_id (the logical link)
        employee = await repo.db["employees"].find_one({"employee_no_id": employee_id})
        if not employee:
            current_user.pop("hashed_password", None)
            return success_response(message="User profile fetched", data=current_user)
        
        full_profile = normalize(employee)
        # Ensure sensitive fields are removed
        full_profile.pop("hashed_password", None)
        full_profile.pop("password", None)
        
        # Add permissions and user ID from the user database record
        full_profile["permissions"] = current_user.get("permissions", [])
        full_profile["user_id"] = current_user.get("id")
        
        return success_response(message="Profile fetched successfully", data=full_profile)
    except Exception as e:
        return error_response(message=str(e), status_code=500)

@router.put("/update")
async def update_profile(
    current_user: dict = Depends(get_current_user),
    first_name: Optional[str] = Form(None),
    last_name: Optional[str] = Form(None),
    name: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    mobile: Optional[str] = Form(None),
    date_of_birth: Optional[str] = Form(None),
    gender: Optional[str] = Form(None),
    emergency_contact_name: Optional[str] = Form(None),
    emergency_contact_number: Optional[str] = Form(None),
    parent_name: Optional[str] = Form(None),
    marital_status: Optional[str] = Form(None),
    address: Optional[str] = Form(None),
    profile_picture: Optional[UploadFile] = File(None),
    document_proof: Optional[UploadFile] = File(None)
):
    try:
        employee_id = current_user.get("employee_no_id")
        if not employee_id:
             return error_response(message="Employee record not found for this user", status_code=404)
        
        # Find employee by employee_no_id
        employee = await repo.db["employees"].find_one({"employee_no_id": employee_id})
        if not employee:
            return error_response(message="Employee record not found", status_code=404)
        
        db_id = str(employee["_id"])
        
        profile_pic_path = None
        if profile_picture:
            uploaded = await file_handler.upload_file(profile_picture)
            profile_pic_path = uploaded["url"]

        documents_list = None
        if document_proof:
            documents_list = employee.get("documents", []) or []
            uploaded_doc = await file_handler.upload_file(document_proof)
            doc_path = uploaded_doc["url"]
            # Append new document to existing list
            documents_list.append({
                "document_name": document_proof.filename,
                "document_proof": doc_path,
                "file_type": document_proof.content_type
            })
            
        update_data = EmployeeUpdate(
            first_name=first_name,
            last_name=last_name,
            name=name,
            email=email,
            mobile=mobile,
            date_of_birth=date_of_birth,
            gender=gender,
            emergency_contact_name=emergency_contact_name,
            emergency_contact_number=emergency_contact_number,
            parent_name=parent_name,
            marital_status=marital_status,
            address=address,
            documents=documents_list
        )
        
        updated_employee = await repo.update_employee(db_id, update_data, profile_pic_path)
        
        return success_response(message="Profile updated successfully", data=updated_employee)
    except Exception as e:
        return error_response(message=str(e), status_code=500)

@router.put("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user)
):
    try:
        user_id = current_user.get("id")
        
        # Verify current password
        user_record = await repo.users.find_one({"_id": ObjectId(user_id)})
        if not user_record or not verify_password(request.current_password, user_record["hashed_password"]):
            return error_response(message="Invalid current password", status_code=400)
        
        # Hash new password
        hashed_password = get_password_hash(request.new_password)
        
        # Update User table
        await repo.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"hashed_password": hashed_password, "updated_at": datetime.utcnow()}}
        )
        
        # Update Employee table if employee_no_id exists
        employee_id = current_user.get("employee_no_id")
        if employee_id:
            await repo.employees.update_one(
                {"employee_no_id": employee_id},
                {"$set": {"hashed_password": hashed_password, "updated_at": datetime.utcnow()}}
            )
            
        return success_response(message="Password changed successfully")
    except Exception as e:
        return error_response(message=str(e), status_code=500)
