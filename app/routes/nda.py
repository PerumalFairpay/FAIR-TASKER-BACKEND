from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from app.helper.response_helper import success_response, error_response
from app.crud.repository import repository as repo
from app.models import NDARequestCreate, NDARequestUpdate, NDADocument
from app.helper.file_handler import file_handler
from typing import Optional, List
from datetime import datetime
from app.auth import verify_token

router = APIRouter(prefix="/nda", tags=["nda"])

@router.post("/create", dependencies=[Depends(verify_token)])
async def create_nda_request(
    employee_name: str = Form(...),
    employee_role: str = Form(...),
    employee_address: str = Form(...)
):
    try:
        nda_data = NDARequestCreate(
            employee_name=employee_name,
            employee_role=employee_role,
            employee_address=employee_address
        )
        new_nda = await repo.create_nda_request(nda_data)
        
        # Add link for frontend convenience (optional, user can construct it)
        # Assuming frontend URL from env or string
        # new_nda["link"] = f"https://hrm.fairpaytechworks.com/nda/{new_nda['token']}"
        new_nda["link"] = f"/nda/{new_nda['token']}" # Relative link or absolute if base_url known

        return success_response(
            message="NDA Request created successfully",
            status_code=201,
            data=new_nda
        )
    except Exception as e:
        return error_response(message=str(e), status_code=500)

@router.get("/list", dependencies=[Depends(verify_token)])
async def list_ndas():
    try:
        ndas = await repo.get_all_nda_requests()
        # Enforce consistent structure if needed, but repo data should be fine
        return success_response(
            message="NDAs retrieved successfully",
            data=ndas
        )
    except Exception as e:
        return error_response(message=str(e), status_code=500)

@router.get("/{token}")
async def get_nda_details(token: str):
    try:
        nda = await repo.get_nda_request(token)
        if not nda:
            return error_response(message="Invalid or expired token", status_code=404)
        
        # Check Expiry
        # normalize converts to isoformat string
        expires_at_str = nda["expires_at"]
        try:
            expires_at = datetime.fromisoformat(expires_at_str)
            if datetime.utcnow() > expires_at:
                return error_response(message="Link has expired", status_code=410)
        except ValueError:
            pass # Use as is if parsing fails, or assume valid

        return success_response(
            message="NDA details fetched successfully",
            data=nda
        )
    except Exception as e:
        return error_response(message=str(e), status_code=500)

@router.post("/{token}/upload")
async def upload_documents(
    token: str,
    document_names: List[str] = Form(...),
    document_files: List[UploadFile] = File(...)
):
    try:
        nda = await repo.get_nda_request(token)
        if not nda:
            return error_response(message="Invalid token", status_code=404)
        
        # Expiry Check
        expires_at_str = nda["expires_at"]
        expires_at = datetime.fromisoformat(expires_at_str)
        if datetime.utcnow() > expires_at:
            return error_response(message="Link has expired", status_code=410)

        uploaded_docs = []
        # Append to existing or replace? Typically append or user might upload multiple times.
        # User requirement: "submit some documents".
        
        current_docs = nda.get("documents", [])

        for i, file in enumerate(document_files):
            uploaded = await file_handler.upload_file(file)
            doc_url = uploaded["url"]
            doc_name = document_names[i] if i < len(document_names) else file.filename
            
            new_doc = NDADocument(
                document_name=doc_name,
                document_url=doc_url,
                file_type=file.content_type,
                uploaded_at=datetime.utcnow().isoformat()
            )
            # Convert pydantic to dict
            current_docs.append(new_doc.dict())

        # Update status to 'Documents Submitted'
        update_payload = {
            "documents": current_docs,
            "status": "Documents Submitted"
        }
        
        updated_nda = await repo.update_nda_request(token, update_payload)
        
        return success_response(
            message="Documents uploaded successfully",
            data=updated_nda
        )
    except Exception as e:
        return error_response(message=str(e), status_code=500)

@router.post("/{token}/sign")
async def sign_nda(token: str):
    try:
        nda = await repo.get_nda_request(token)
        if not nda:
            return error_response(message="Invalid token", status_code=404)
        
        # Expiry Check
        expires_at_str = nda["expires_at"]
        expires_at = datetime.fromisoformat(expires_at_str)
        if datetime.utcnow() > expires_at:
            return error_response(message="Link has expired", status_code=410)

        # Update status to 'Signed'
        update_payload = {"status": "Signed"}
        updated_nda = await repo.update_nda_request(token, update_payload)
        
        return success_response(
            message="NDA signed successfully",
            data=updated_nda
        )
    except Exception as e:
        return error_response(message=str(e), status_code=500)
