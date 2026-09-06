from fastapi import APIRouter, UploadFile, File, Form, Depends, BackgroundTasks
from app.helper.response_helper import success_response, error_response
from app.services.onboarding_service import handle_new_employee_onboarding
from app.models import EmployeeCreate, EmployeeUpdate, EmployeeDocument, UserPermissionsUpdate
from app.services.api.employee import EmployeeService
from app.helper.file_handler import file_handler
from typing import Optional, List
import json
from app.auth import verify_token, require_permission

router = APIRouter(prefix="/employees", tags=["employees"], dependencies=[Depends(verify_token)])


@router.post("/create", dependencies=[Depends(require_permission("employee:submit"))])
async def create_employee(
    background_tasks: BackgroundTasks,
    first_name: str = Form(...),
    last_name: str = Form(...),
    name: str = Form(...),
    email: str = Form(...),
    personal_email: Optional[str] = Form(None),
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
    address: Optional[str] = Form(None),
    work_mode: Optional[str] = Form("Office"),
    document_names: List[str] = Form([]),
    profile_picture: Optional[UploadFile] = File(None),
    document_proofs: List[UploadFile] = File([]),
    
    # New Fields
    onboarding_checklist: Optional[str] = Form(None),
    offboarding_checklist: Optional[str] = Form(None),
    resignation_date: Optional[str] = Form(None),
    last_working_day: Optional[str] = Form(None),
    exit_interview_notes: Optional[str] = Form(None),

    # Bank Details
    account_name: Optional[str] = Form(None),
    bank_name: Optional[str] = Form(None),
    account_number: Optional[str] = Form(None),
    ifsc_code: Optional[str] = Form(None),
    pf_account_number: Optional[str] = Form(None),
    esic_number: Optional[str] = Form(None),
    pan_number: Optional[str] = Form(None),
    biometric_id: Optional[str] = Form(None),
    shift_id: Optional[str] = Form(None),
    weekly_off: Optional[str] = Form(None),
    lop_rule_01: bool = Form(False),
):
    profile_pic_path = None
    if profile_picture:
        uploaded = await file_handler.upload_file(profile_picture, subfolder="employees")
        profile_pic_path = uploaded["url"]

    documents_list = []
    if document_proofs:
        for i, doc_file in enumerate(document_proofs):
            uploaded_doc = await file_handler.upload_file(doc_file, subfolder="employees/documents")
            doc_path = uploaded_doc["url"]
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
        personal_email=personal_email,
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
        address=address,
        work_mode=work_mode,
        shift_id=shift_id,
        documents=documents_list,
        onboarding_checklist=json.loads(onboarding_checklist) if onboarding_checklist else [],
        offboarding_checklist=json.loads(offboarding_checklist) if offboarding_checklist else [],
        resignation_date=resignation_date,
        last_working_day=last_working_day,
        exit_interview_notes=exit_interview_notes,
        account_name=account_name,
        bank_name=bank_name,
        account_number=account_number,
        ifsc_code=ifsc_code,
        pf_account_number=pf_account_number,
        esic_number=esic_number,
        pan_number=pan_number,
        biometric_id=biometric_id,
        weekly_off=json.loads(weekly_off) if weekly_off else [6],
        lop_rule_01=lop_rule_01,
    )

    data, error = await EmployeeService.create(employee_data, profile_picture_path=profile_pic_path)
    if error:
        status_code = 400 if "already exists" in error.lower() else 500
        return error_response(message=error, status_code=status_code)

    background_tasks.add_task(
        handle_new_employee_onboarding,
        employee_name=name,
        employee_email=email,
        password=password
    )

    return success_response(
        message="Employee created successfully",
        status_code=201,
        data=data
    )


@router.get("/all", dependencies=[Depends(require_permission("employee:view"))])
async def get_employees(
    page: int = 1, 
    limit: int = 10,
    search: Optional[str] = None,
    status: Optional[str] = None,
    role: Optional[str] = None,
    work_mode: Optional[str] = None
):
    data, total_items, error = await EmployeeService.list(
        page=page,
        limit=limit,
        search=search,
        status=status,
        role=role,
        work_mode=work_mode
    )
    if error:
        return error_response(message=f"Failed to fetch employees: {error}", status_code=500)

    total_pages = (total_items + limit - 1) // limit if limit > 0 else 0
    meta = {
        "current_page": page,
        "total_pages": total_pages,
        "total_items": total_items,
        "limit": limit
    }

    return success_response(
        message="Employees fetched successfully",
        data=data,
        meta=meta
    )


@router.get("/summary")
async def get_employees_summary():
    data, error = await EmployeeService.get_summary()
    if error:
        return error_response(message=f"Failed to fetch employees summary: {error}", status_code=500)
    return success_response(
        message="Employees summary fetched successfully",
        data=data
    )


@router.get("/{employee_id}/summary", dependencies=[Depends(require_permission("employee:view"))])
async def get_employee_summary_details(employee_id: str):
    data, error = await EmployeeService.get_summary_details(employee_id)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(
        message="Employee summary fetched successfully",
        data=data
    )


@router.get("/{employee_id}", dependencies=[Depends(require_permission("employee:view"))])
async def get_employee(employee_id: str):
    data, error = await EmployeeService.get(employee_id)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(
        message="Employee fetched successfully",
        data=data
    )


@router.put("/update/{employee_id}", dependencies=[Depends(require_permission("employee:submit"))])
async def update_employee(
    employee_id: str,
    first_name: Optional[str] = Form(None),
    last_name: Optional[str] = Form(None),
    name: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    personal_email: Optional[str] = Form(None),
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
    address: Optional[str] = Form(None),
    work_mode: Optional[str] = Form(None),
    document_names: List[str] = Form([]),
    profile_picture: Optional[UploadFile] = File(None),
    document_proofs: List[UploadFile] = File([]),

    # New Fields
    onboarding_checklist: Optional[str] = Form(None),
    offboarding_checklist: Optional[str] = Form(None),
    resignation_date: Optional[str] = Form(None),
    last_working_day: Optional[str] = Form(None),
    exit_interview_notes: Optional[str] = Form(None),

    # Bank Details
    account_name: Optional[str] = Form(None),
    bank_name: Optional[str] = Form(None),
    account_number: Optional[str] = Form(None),
    ifsc_code: Optional[str] = Form(None),
    pf_account_number: Optional[str] = Form(None),
    esic_number: Optional[str] = Form(None),
    pan_number: Optional[str] = Form(None),
    biometric_id: Optional[str] = Form(None),
    shift_id: Optional[str] = Form(None),
    weekly_off: Optional[str] = Form(None),
    lop_rule_01: Optional[bool] = Form(None),
):
    profile_pic_path = None
    if profile_picture:
        uploaded = await file_handler.upload_file(profile_picture, subfolder="employees")
        profile_pic_path = uploaded["url"]

    documents_list = []
    if document_proofs:
        current_emp, _ = await EmployeeService.get(employee_id)
        if current_emp and "documents" in current_emp:
            documents_list = current_emp["documents"]
        
        for i, doc_file in enumerate(document_proofs):
            uploaded_doc = await file_handler.upload_file(doc_file, subfolder="employees/documents")
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
        personal_email=personal_email,
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
        address=address,
        work_mode=work_mode,
        shift_id=shift_id,
        documents=documents_list if documents_list else None,
        onboarding_checklist=json.loads(onboarding_checklist) if onboarding_checklist else None,
        offboarding_checklist=json.loads(offboarding_checklist) if offboarding_checklist else None,
        resignation_date=resignation_date,
        last_working_day=last_working_day,
        exit_interview_notes=exit_interview_notes,
        account_name=account_name,
        bank_name=bank_name,
        account_number=account_number,
        ifsc_code=ifsc_code,
        pf_account_number=pf_account_number,
        esic_number=esic_number,
        pan_number=pan_number,
        biometric_id=biometric_id,
        weekly_off=json.loads(weekly_off) if weekly_off else None,
        lop_rule_01=lop_rule_01,
    )

    data, error = await EmployeeService.update(employee_id, update_data, profile_pic_path)
    if error:
        if "not found" in error.lower() or "invalid" in error.lower():
            status_code = 404
        elif "already exists" in error.lower():
            status_code = 400
        else:
            status_code = 500
        return error_response(message=error, status_code=status_code)

    return success_response(
        message="Employee updated successfully",
        data=data
    )


@router.delete("/delete/{employee_id}", dependencies=[Depends(require_permission("employee:submit"))])
async def delete_employee(employee_id: str):
    success, error = await EmployeeService.delete(employee_id)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(message="Employee deleted successfully", data=[])


@router.put("/{employee_id}/permissions", dependencies=[Depends(require_permission("permission:submit"))])
async def update_permissions(employee_id: str, permissions_data: UserPermissionsUpdate):
    success, error = await EmployeeService.update_user_permissions(employee_id, permissions_data.permissions)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)

    return success_response(
        message="User permissions updated successfully",
        data={"id": employee_id, "permissions": permissions_data.permissions}
    )


@router.get("/{employee_id}/permissions", dependencies=[Depends(require_permission("permission:view"))])
async def get_permissions(employee_id: str):
    data, error = await EmployeeService.get_user_permissions(employee_id)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)

    return success_response(
        message="User permissions fetched successfully",
        data=data
    )


@router.delete("/documents/{doc_id}", dependencies=[Depends(require_permission("employee:submit"))])
async def delete_employee_document(doc_id: str):
    success, error = await EmployeeService.delete_employee_document(doc_id)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(
        message="Document deleted successfully",
        data=[]
    )
