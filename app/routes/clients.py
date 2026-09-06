from fastapi import APIRouter, Depends, UploadFile, File, Form
from app.services.api.client import ClientService
from app.helper.response_helper import success_response, error_response
from typing import Optional
from app.auth import verify_token

router = APIRouter(prefix="/clients", tags=["clients"], dependencies=[Depends(verify_token)])


@router.post("/create")
async def create_client(
    company_name: str = Form(...),
    contact_name: str = Form(...),
    contact_email: str = Form(...),
    contact_mobile: str = Form(...),
    contact_person_designation: Optional[str] = Form(None),
    contact_address: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    status: Optional[str] = Form("Active"),
    logo: Optional[UploadFile] = File(None)
):
    data, error = await ClientService.create(
        company_name=company_name,
        contact_name=contact_name,
        contact_email=contact_email,
        contact_mobile=contact_mobile,
        contact_person_designation=contact_person_designation,
        contact_address=contact_address,
        description=description,
        status=status,
        logo=logo
    )
    if error:
        return error_response(message=f"Failed to create client/vendor: {error}", status_code=500)
    return success_response(message="Client/Vendor created successfully", data=data, status_code=201)


@router.get("/all")
async def get_clients():
    data, error = await ClientService.list()
    if error:
        return error_response(message=f"Failed to fetch clients/vendors: {error}", status_code=500)
    return success_response(message="Clients/Vendors fetched successfully", data=data)


@router.get("/{client_id}")
async def get_client(client_id: str):
    data, error = await ClientService.get(client_id)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(message="Client/Vendor fetched successfully", data=data)


@router.put("/update/{client_id}")
async def update_client(
    client_id: str,
    company_name: Optional[str] = Form(None),
    contact_name: Optional[str] = Form(None),
    contact_email: Optional[str] = Form(None),
    contact_mobile: Optional[str] = Form(None),
    contact_person_designation: Optional[str] = Form(None),
    contact_address: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    status: Optional[str] = Form(None),
    logo: Optional[UploadFile] = File(None)
):
    data, error = await ClientService.update(
        client_id=client_id,
        company_name=company_name,
        contact_name=contact_name,
        contact_email=contact_email,
        contact_mobile=contact_mobile,
        contact_person_designation=contact_person_designation,
        contact_address=contact_address,
        description=description,
        status=status,
        logo=logo
    )
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(message="Client/Vendor updated successfully", data=data)


@router.delete("/delete/{client_id}")
async def delete_client(client_id: str):
    success, error = await ClientService.delete(client_id)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(message="Client/Vendor deleted successfully", data=[])
