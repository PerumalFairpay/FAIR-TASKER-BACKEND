from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from app.models import NDARequestCreate, NDARequestUpdate, NDARequestResponse
from app.crud.repository import repository
from app.helper.response_helper import success_response, error_response
from datetime import datetime, timedelta
import uuid
import os

router = APIRouter(prefix="/nda", tags=["NDA"])

# Setup Jinja2 templates
templates_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
templates = Jinja2Templates(directory=templates_dir)


@router.post("/generate")
async def generate_nda_link(nda_request: NDARequestCreate):
    """
    Generate a new NDA link for an employee.
    Admin endpoint to create NDA request with 1-hour expiry.
    """
    try:
        # Generate unique token
        token = str(uuid.uuid4())
        
        # Set expiry to 1 hour from now
        expires_at = datetime.utcnow() + timedelta(hours=1)
        
        # Create NDA request in database
        nda_data = await repository.create_nda_request(nda_request, token, expires_at)
        
        # Generate link URL
        link_url = f"/api/nda/view/{token}"
        
        return success_response(
            message="NDA link generated successfully",
            data={"link": link_url, "nda": nda_data}
        )
    except Exception as e:
        return error_response(message=str(e), status_code=500)


@router.get("/list")
async def list_nda_requests():
    """
    Get list of all NDA requests.
    Returns data in standard response format.
    """
    try:
        nda_requests = await repository.get_nda_requests()
        return success_response(
            message="NDA requests retrieved successfully",
            data=nda_requests
        )
    except Exception as e:
        return error_response(message=str(e), status_code=500)


@router.get("/view/{token}", response_class=HTMLResponse)
async def view_nda_form(token: str, request: Request):
    """
    Serve the NDA form HTML with pre-populated employee data.
    Checks token expiration before serving.
    """
    try:
        # Get NDA request by token
        nda_request = await repository.get_nda_request_by_token(token)
        
        if not nda_request:
            raise HTTPException(status_code=404, detail="NDA request not found")
        
        # Check if expired
        expires_at = nda_request.get("expires_at")
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
        
        if datetime.utcnow() > expires_at:
            # Update status to Expired
            await repository.update_nda_request(token, {"status": "Expired"})
            raise HTTPException(status_code=410, detail="NDA link has expired")
        
        # Format date
        current_date = datetime.utcnow()
        formatted_date = current_date.strftime("%d/%m/%Y")
        
        # Render template with employee data
        return templates.TemplateResponse("nda_form.html", {
            "request": request,
            "employee_name": nda_request.get("employee_name"),
            "role": nda_request.get("role"),
            "employee_address": nda_request.get("address"),
            "date": formatted_date,
            "token": token
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload/{token}")
async def upload_documents(token: str, documents: list[str]):
    """
    Handle document uploads for an NDA request.
    Accepts list of document URLs.
    """
    try:
        # Get NDA request
        nda_request = await repository.get_nda_request_by_token(token)
        
        if not nda_request:
            return error_response(message="NDA request not found", status_code=404)
        
        # Check if expired
        expires_at = nda_request.get("expires_at")
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
        
        if datetime.utcnow() > expires_at:
            return error_response(message="NDA link has expired", status_code=410)
        
        # Update documents
        existing_docs = nda_request.get("documents", [])
        existing_docs.extend(documents)
        
        updated_nda = await repository.update_nda_request(token, {"documents": existing_docs})
        
        return success_response(
            message="Documents uploaded successfully",
            data=updated_nda
        )
    except Exception as e:
        return error_response(message=str(e), status_code=500)


@router.post("/sign/{token}")
async def sign_nda(token: str, signature: str):
    """
    Accept signature and update NDA status to Signed.
    Signature should be a Base64 encoded string.
    """
    try:
        # Get NDA request
        nda_request = await repository.get_nda_request_by_token(token)
        
        if not nda_request:
            return error_response(message="NDA request not found", status_code=404)
        
        # Check if expired
        expires_at = nda_request.get("expires_at")
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
        
        if datetime.utcnow() > expires_at:
            return error_response(message="NDA link has expired", status_code=410)
        
        # Update signature and status
        updated_nda = await repository.update_nda_request(token, {
            "signature": signature,
            "status": "Signed"
        })
        
        return success_response(
            message="NDA signed successfully",
            data=updated_nda
        )
    except Exception as e:
        return error_response(message=str(e), status_code=500)
