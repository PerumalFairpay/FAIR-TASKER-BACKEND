from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from app.helper.response_helper import success_response, error_response
from app.crud.repository import repository as repo
from app.models import EmployeeCreate, EmployeeUpdate, EmployeeDocument, UserPermissionsUpdate
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
    document_proofs: List[UploadFile] = File([]),
    
    # New Fields
    onboarding_checklist: Optional[str] = Form(None), # JSON String
    offboarding_checklist: Optional[str] = Form(None), # JSON String
    resignation_date: Optional[str] = Form(None),
    last_working_day: Optional[str] = Form(None),
    exit_interview_notes: Optional[str] = Form(None) 
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
            documents=documents_list,
            onboarding_checklist=json.loads(onboarding_checklist) if onboarding_checklist else [],
            offboarding_checklist=json.loads(offboarding_checklist) if offboarding_checklist else [],
            resignation_date=resignation_date,
            last_working_day=last_working_day,
            exit_interview_notes=exit_interview_notes
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
async def get_employees(page: int = 1, limit: int = 10):
    try:
        employees, total_items = await repo.get_employees(page, limit)
        
        total_pages = (total_items + limit - 1) // limit
        meta = {
            "current_page": page,
            "total_pages": total_pages,
            "total_items": total_items,
            "limit": limit
        }
        
        return success_response(
            message="Employees fetched successfully",
            data=employees,
            meta=meta
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
    document_proofs: List[UploadFile] = File([]),

    # New Fields
    onboarding_checklist: Optional[str] = Form(None), # JSON String
    offboarding_checklist: Optional[str] = Form(None), # JSON String
    resignation_date: Optional[str] = Form(None),
    last_working_day: Optional[str] = Form(None),
    exit_interview_notes: Optional[str] = Form(None) 
):
    try:
        profile_pic_path = None
        if profile_picture:
            uploaded = await file_handler.upload_file(profile_picture)
            profile_pic_path = uploaded["url"]

        documents_list = []
        if document_proofs:
            # Fetch existing employee to get current documents
            current_emp = await repo.get_employee(employee_id)
            if current_emp and "documents" in current_emp:
                 documents_list = current_emp["documents"]
            
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
            documents=documents_list if documents_list else None,
            onboarding_checklist=json.loads(onboarding_checklist) if onboarding_checklist else None,
            offboarding_checklist=json.loads(offboarding_checklist) if offboarding_checklist else None,
            resignation_date=resignation_date,
            last_working_day=last_working_day,
            exit_interview_notes=exit_interview_notes
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

@router.put("/{employee_id}/permissions", dependencies=[Depends(require_permission("permission:manage"))])
async def update_permissions(employee_id: str, permissions_data: UserPermissionsUpdate):
    try:
        success = await repo.update_user_permissions(employee_id, permissions_data.permissions)
        # We can't easily distinguish between "User not found" and "Permissions unchanged" with simple boolean if user exists but nothing changed.
        # But provided implementation returns matched_count > 0, so if user exists it returns true.
        
        if not success:
             return error_response(message="User not found for this employee ID", status_code=404)
        
        return success_response(
            message="User permissions updated successfully",
            data={"id": employee_id, "permissions": permissions_data.permissions}
        )
    except Exception as e:
        return error_response(message=str(e), status_code=500)

@router.get("/{employee_id}/permissions", dependencies=[Depends(require_permission("permission:manage"))])
async def get_permissions(employee_id: str):
    try:
        data = await repo.get_user_permissions(employee_id)
        return success_response(
            message="User permissions fetched successfully",
            data={
                "id": employee_id, 
                "role_permissions": data["role_permissions"],
                "direct_permissions": data["direct_permissions"]
            }
        )
    except Exception as e:
        return error_response(message=str(e), status_code=500)
