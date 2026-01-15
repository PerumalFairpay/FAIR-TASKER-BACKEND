from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from app.helper.response_helper import success_response, error_response
from app.crud.repository import repository as repo
from app.models import EmployeeCreate, EmployeeUpdate, EmployeeDocument
from app.helper.file_handler import file_handler
from typing import Optional, List
import json
from app.auth import verify_token, require_permission

router = APIRouter(prefix="/employees", tags=["employees"], dependencies=[Depends(verify_token)])

@router.post("/create", dependencies=[Depends(require_permission("employee:create"))])
async def create_employee(
    first_name: str = Form(...),
    last_name: str = Form(...),
    name: str = Form(...),
    email: str = Form(...),
    mobile: str = Form(...),
    password: str = Form(...),
    date_of_birth: Optional[str] = Form(None),
    gender: Optional[str] = Form(None),
    emergency_contact_name: Optional[str] = Form(None),
    emergency_contact_number: Optional[str] = Form(None),
    parent_name: Optional[str] = Form(None),
    marital_status: Optional[str] = Form(None),
    employee_type: Optional[str] = Form(None),
    employee_no_id: str = Form(...),
    department: Optional[str] = Form(None),
    designation: Optional[str] = Form(None),
    role: Optional[str] = Form(None),
    status: Optional[str] = Form("Active"),
    date_of_joining: Optional[str] = Form(None),
    confirmation_date: Optional[str] = Form(None),
    notice_period: Optional[str] = Form(None),

    work_mode: Optional[str] = Form("Office"),
    document_names: List[str] = Form([]),
    profile_picture: Optional[UploadFile] = File(None),
    document_proofs: List[UploadFile] = File([]) 
):
    try:
        profile_pic_path = None
        if profile_picture:
            uploaded = await file_handler.upload_file(profile_picture)
            profile_pic_path = uploaded["url"]

        documents_list = []
        if document_proofs:
            for i, doc_file in enumerate(document_proofs):
                uploaded_doc = await file_handler.upload_file(doc_file)
                doc_path = uploaded_doc["url"]
                # Use provided name or filename fallback
                doc_name = document_names[i] if i < len(document_names) else doc_file.filename
                
                documents_list.append(EmployeeDocument(
                    document_name=doc_name,
                    document_proof=doc_path,
                    file_type=doc_file.content_type
                ))

        employee_data = EmployeeCreate(
            first_name=first_name,
            last_name=last_name,
            name=name,
            email=email,
            mobile=mobile,
            password=password,
            date_of_birth=date_of_birth,
            gender=gender,
            emergency_contact_name=emergency_contact_name,
            emergency_contact_number=emergency_contact_number,
            parent_name=parent_name,
            marital_status=marital_status,
            employee_type=employee_type,
            employee_no_id=employee_no_id,
            department=department,
            designation=designation,
            role=role,
            status=status,
            date_of_joining=date_of_joining,
            confirmation_date=confirmation_date,
            notice_period=notice_period,

            work_mode=work_mode,
            documents=documents_list
        )

        # Call repository. Note: repo signature change pending. passing profile_pic_path.
        # If repo not updated yet, I might need to pass `document_proof_path=None` if strictly required as separate arg.
        # But python allows kwargs or defaults. The old signature had default None. 
        # So invoking with 2 args works if I removed the 3rd or if 3rd has default.
        new_employee = await repo.create_employee(employee_data, profile_picture_path=profile_pic_path)
        
        return success_response(
            message="Employee created successfully",
            status_code=201,
            data=new_employee
        )
    except ValueError as ve:
        return error_response(message=str(ve), status_code=400)
    except Exception as e:
        return error_response(message=f"Failed to create employee: {str(e)}", status_code=500)

@router.get("/all", dependencies=[Depends(require_permission("employee:view"))])
async def get_employees():
    try:
        employees = await repo.get_employees()
        return success_response(
            message="Employees fetched successfully",
            data=employees
        )
    except Exception as e:
        return error_response(message=str(e), status_code=500)

@router.get("/{employee_id}", dependencies=[Depends(require_permission("employee:view"))])
async def get_employee(employee_id: str):
    try:
        employee = await repo.get_employee(employee_id)
        if not employee:
             return error_response(message="Employee not found", status_code=404)
        return success_response(
            message="Employee fetched successfully",
            data=employee
        )
    except Exception as e:
        return error_response(message=str(e), status_code=500)

@router.put("/update/{employee_id}", dependencies=[Depends(require_permission("employee:edit"))])
async def update_employee(
    employee_id: str,
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
    employee_type: Optional[str] = Form(None),
    employee_no_id: Optional[str] = Form(None),
    department: Optional[str] = Form(None),
    designation: Optional[str] = Form(None),
    role: Optional[str] = Form(None),
    status: Optional[str] = Form(None),
    date_of_joining: Optional[str] = Form(None),
    confirmation_date: Optional[str] = Form(None),
    notice_period: Optional[str] = Form(None),

    work_mode: Optional[str] = Form(None),
    document_names: List[str] = Form([]),
    profile_picture: Optional[UploadFile] = File(None),
    document_proofs: List[UploadFile] = File([]) 
):
    try:
        profile_pic_path = None
        if profile_picture:
            uploaded = await file_handler.upload_file(profile_picture)
            profile_pic_path = uploaded["url"]

        documents_list = []
        if document_proofs:
            for i, doc_file in enumerate(document_proofs):
                uploaded_doc = await file_handler.upload_file(doc_file)
                doc_path = uploaded_doc["url"]
                doc_name = document_names[i] if i < len(document_names) else doc_file.filename
                
                documents_list.append(EmployeeDocument(
                    document_name=doc_name,
                    document_proof=doc_path,
                    file_type=doc_file.content_type
                ))
            
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
            employee_type=employee_type,
            employee_no_id=employee_no_id,
            department=department,
            designation=designation,
            role=role,
            status=status,
            date_of_joining=date_of_joining,
            confirmation_date=confirmation_date,
            notice_period=notice_period,

            work_mode=work_mode,
            documents=documents_list if documents_list else None
        )
        
        updated_employee = await repo.update_employee(employee_id, update_data, profile_pic_path)
        
        if not updated_employee:
            return error_response(message="Employee not found", status_code=404)

        return success_response(
            message="Employee updated successfully",
            data=updated_employee
        )
    except Exception as e:
        return error_response(message=str(e), status_code=500)

@router.delete("/delete/{employee_id}", dependencies=[Depends(require_permission("employee:delete"))])
async def delete_employee(employee_id: str):
    try:
        success = await repo.delete_employee(employee_id)
        if not success:
            return error_response(message="Employee not found", status_code=404)
        return success_response(
            message="Employee deleted successfully"
        )
    except Exception as e:
        return error_response(message=str(e), status_code=500)
