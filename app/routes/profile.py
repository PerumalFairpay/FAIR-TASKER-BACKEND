from fastapi import APIRouter, Depends, Form, File, UploadFile
from typing import Optional
from pydantic import BaseModel
from app.auth import get_current_user
from app.helper.response_helper import success_response, error_response
from app.models import EmployeeUpdate
from app.helper.file_handler import file_handler
from app.services.api.profile import ProfileService

router = APIRouter(prefix="/profile", tags=["profile"])


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@router.get("/")
async def get_profile(current_user: dict = Depends(get_current_user)):
    data, error = await ProfileService.get_profile(current_user)
    if error:
        return error_response(message=error, status_code=500)
    return success_response(message="Profile fetched successfully", data=data)


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
    account_name: Optional[str] = Form(None),
    bank_name: Optional[str] = Form(None),
    account_number: Optional[str] = Form(None),
    ifsc_code: Optional[str] = Form(None),
    pan_number: Optional[str] = Form(None),
    pf_account_number: Optional[str] = Form(None),
    esic_number: Optional[str] = Form(None),
    profile_picture: Optional[UploadFile] = File(None),
    document_proof: Optional[UploadFile] = File(None)
):
    profile_pic_path = None
    if profile_picture:
        uploaded = await file_handler.upload_file(profile_picture)
        profile_pic_path = uploaded["url"]

    documents_list = None
    if document_proof:
        uploaded_doc = await file_handler.upload_file(document_proof)
        doc_path = uploaded_doc["url"]
        documents_list = [{
            "document_name": document_proof.filename,
            "document_proof": doc_path,
            "file_type": document_proof.content_type
        }]

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
        account_name=account_name,
        bank_name=bank_name,
        account_number=account_number,
        ifsc_code=ifsc_code,
        pan_number=pan_number,
        pf_account_number=pf_account_number,
        esic_number=esic_number,
        documents=documents_list
    )

    data, error = await ProfileService.update_profile(current_user, update_data, profile_pic_path)
    if error:
        if "not found" in error.lower():
            status_code = 404
        elif "already exists" in error.lower():
            status_code = 400
        else:
            status_code = 500
        return error_response(message=error, status_code=status_code)
    return success_response(message="Profile updated successfully", data=data)


@router.put("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user)
):
    success, error = await ProfileService.change_password(
        current_user,
        request.current_password,
        request.new_password
    )
    if error:
        status_code = 400 if "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(message="Password changed successfully")
