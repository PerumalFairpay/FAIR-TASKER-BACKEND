from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import JSONResponse
from app.crud.repository import repository as repo
from app.models import ClientCreate, ClientUpdate
from app.helper.file_handler import file_handler
from typing import List, Optional
import json

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
    logo: UploadFile = File(None)
):
    try:
        logo_path = None
        if logo:
            uploaded = await file_handler.upload_file(logo)
            logo_path = uploaded["url"]

        client_data = ClientCreate(
            company_name=company_name,
            contact_name=contact_name,
            contact_email=contact_email,
            contact_mobile=contact_mobile,
            contact_person_designation=contact_person_designation,
            contact_address=contact_address,
            description=description,
            status=status
        )

        new_client = await repo.create_client(client_data, logo_path)
        return JSONResponse(
            status_code=201,
            content={"message": "Client/Vendor created successfully", "success": True, "data": new_client}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to create client/vendor: {str(e)}", "success": False}
        )

@router.get("/all")
async def get_clients():
    try:
        clients = await repo.get_clients()
        return JSONResponse(
            status_code=200,
            content={"message": "Clients/Vendors fetched successfully", "success": True, "data": clients}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to fetch clients/vendors: {str(e)}", "success": False}
        )

@router.get("/{client_id}")
async def get_client(client_id: str):
    try:
        client = await repo.get_client(client_id)
        if not client:
            return JSONResponse(
                status_code=404,
                content={"message": "Client/Vendor not found", "success": False}
            )
        return JSONResponse(
            status_code=200,
            content={"message": "Client/Vendor fetched successfully", "success": True, "data": client}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to fetch client/vendor: {str(e)}", "success": False}
        )

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
    logo: UploadFile = File(None)
):
    try:
        logo_path = None
        if logo:
            uploaded = await file_handler.upload_file(logo)
            logo_path = uploaded["url"]

        client_update_data = ClientUpdate(
            company_name=company_name,
            contact_name=contact_name,
            contact_email=contact_email,
            contact_mobile=contact_mobile,
            contact_person_designation=contact_person_designation,
            contact_address=contact_address,
            description=description,
            status=status
        )

        updated_client = await repo.update_client(client_id, client_update_data, logo_path)
        if not updated_client:
            return JSONResponse(
                status_code=404,
                content={"message": "Client/Vendor not found", "success": False}
            )
        return JSONResponse(
            status_code=200,
            content={"message": "Client/Vendor updated successfully", "success": True, "data": updated_client}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to update client/vendor: {str(e)}", "success": False}
        )

@router.delete("/delete/{client_id}")
async def delete_client(client_id: str):
    try:
        success = await repo.delete_client(client_id)
        if not success:
            return JSONResponse(
                status_code=404,
                content={"message": "Client/Vendor not found", "success": False}
            )
        return JSONResponse(
            status_code=200,
            content={"message": "Client/Vendor deleted successfully", "success": True}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to delete client/vendor: {str(e)}", "success": False}
        )
