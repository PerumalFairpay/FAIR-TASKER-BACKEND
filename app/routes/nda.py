from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from app.models import NDARequestCreate, NDARequestUpdate, NDARequestResponse, NDASignatureRequest, NDARegenerateRequest
from app.crud.repository import repository
from app.helper.response_helper import success_response, error_response
from datetime import datetime, timedelta
import uuid
import os
from typing import List
from fastapi import UploadFile, File, Form
from app.helper.file_handler import file_handler

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
        
        # Set expiry based on request, default to 1 hour
        expiry_hours = nda_request.expires_in_hours if nda_request.expires_in_hours else 1
        expires_at = datetime.utcnow() + timedelta(hours=expiry_hours)
        
        # Create NDA request in database
        nda_data = await repository.create_nda_request(nda_request, token, expires_at)
        
        # Generate frontend link URL (not backend API URL)
        link_url = f"/nda/{token}"
        
        return success_response(
            message="NDA link generated successfully",
            data={"link": link_url, "nda": nda_data}
        )
    except Exception as e:
        return error_response(message=str(e), status_code=500)


@router.post("/regenerate/{nda_id}")
async def regenerate_nda_link(nda_id: str, request: NDARegenerateRequest):
    """
    Regenerate an NDA link for an existing request.
    Useful for expired links.
    """
    try: 
        new_token = str(uuid.uuid4())
         
        expiry_hours = request.expires_in_hours if request.expires_in_hours else 1
        expires_at = datetime.utcnow() + timedelta(hours=expiry_hours)
         
        updated_nda = await repository.regenerate_nda_token(nda_id, new_token, expires_at)
        
        if not updated_nda:
             return error_response(message="NDA request not found", status_code=404)
 
        link_url = f"/nda/{new_token}"
        
        return success_response(
            message="NDA link regenerated successfully",
            data={"link": link_url, "nda": updated_nda}
        )
    except Exception as e:
        return error_response(message=str(e), status_code=500)


@router.delete("/delete/{nda_id}")
async def delete_nda_request(nda_id: str):
    """
    Delete an NDA request.
    Only admin can delete.
    """
    try:
        success = await repository.delete_nda_request(nda_id)
        
        if not success:
             return error_response(message="NDA request not found", status_code=404)
        
        return success_response(
            message="NDA request deleted successfully",
            data={"id": nda_id}
        )
    except Exception as e:
        return error_response(message=str(e), status_code=500)


@router.get("/list")
async def list_nda_requests(
    page: int = 1,
    limit: int = 10,
    search: str = None,
    status: str = None,
):
    """
    Get list of all NDA requests.
    Returns data in standard response format.
    """
    try:
        if status == "All":
             status = None

        nda_requests, total_items = await repository.get_nda_requests(
            page, limit, search, status
        )
        
        total_pages = (total_items + limit - 1) // limit
        
        meta = {
            "current_page": page,
            "total_pages": total_pages,
            "total_items": total_items,
            "limit": limit
        }
        
        return success_response(
            message="NDA requests retrieved successfully",
            data=nda_requests,
            meta=meta
        )
    except Exception as e:
        return error_response(message=str(e), status_code=500)


@router.post("/access/{token}")
async def verify_nda_access(token: str, request_body: dict):
    """
    Verify email access to view the full NDA form.
    Returns the HTML content if email matches.
    """
    try:
        email = request_body.get("email")
        if not email:
             raise HTTPException(status_code=400, detail="Email is required")

        # Get NDA request by token
        nda_request = await repository.get_nda_request_by_token(token)
        
        if not nda_request:
            raise HTTPException(status_code=404, detail="NDA request not found")
        
        # Check if expired
        expires_at = nda_request.get("expires_at")
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
        
        if datetime.utcnow() > expires_at:
            await repository.update_nda_request(token, {"status": "Expired"})
            raise HTTPException(status_code=410, detail="NDA link has expired")

        # Verify Email
        stored_email = nda_request.get("email")
        if not stored_email or stored_email.lower().strip() != email.lower().strip():
             raise HTTPException(status_code=403, detail="Invalid Email Address")

        # Render template content as string (Full Access)
        current_date = datetime.utcnow()
        formatted_date = current_date.strftime("%d/%m/%Y")
        
        template = templates.get_template("nda_form.html")
        html_content = template.render({
            "request": nda_request, # Pass full object if needed
            "employee_name": nda_request.get("employee_name"),
            "role": nda_request.get("role"),
            "employee_address": nda_request.get("address"),
            "residential_address": nda_request.get("residential_address"),
            "date": formatted_date,
            "token": token
        })

        return success_response(
            message="NDA access granted",
            data={
                "html_content": html_content,
                "nda": nda_request
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/view/{token}")
async def view_nda_form(token: str):
    """
    Serve the NDA status and basic info.
    DOES NOT RETURN HTML CONTENT or PII.
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
        
        # Return only safe data used for initial load / login check
        safe_data = {
            "employee_name": nda_request.get("employee_name"),
            "status": nda_request.get("status"),
            "requires_auth": True 
        }

        return success_response(
            message="NDA request found",
            data={
                "nda": safe_data,
                # "html_content": None  <-- Explicitly missing
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload/{token}")
async def upload_documents(
    token: str, 
    files: List[UploadFile] = File(...),
    names: List[str] = Form(...)
):
    """
    Handle document uploads for an NDA request.
    Accepts list of files.
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
        
        # Validate matching lengths
        if len(files) != len(names):
             return error_response(message="Number of files and names must match", status_code=400)

        # Upload files using file_handler
        uploaded_results = await file_handler.upload_files(files)
        
        # Create document objects with metadata
        new_documents = []
        for i, result in enumerate(uploaded_results):
            new_documents.append({
                "document_name": names[i],
                "document_proof": result["url"],
                "file_type": files[i].content_type
            })
        
        # Update documents
        existing_docs = nda_request.get("documents", [])
        existing_docs.extend(new_documents)
        
        updated_nda = await repository.update_nda_request(token, {"documents": existing_docs})
        
        return success_response(
            message="Documents uploaded successfully",
            data=updated_nda
        )
    except Exception as e:
        return error_response(message=str(e), status_code=500)


@router.post("/sign/{token}")
async def sign_nda(token: str, request_body: NDASignatureRequest, request: Request):
    """
    Accept signature and update NDA status to Signed.
    Automatically generates and stores the signed PDF.
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
        
        # Capture IP address if not provided
        ip_address = request_body.ip_address
        if not ip_address and request.client:
            ip_address = request.client.host
            
        # Update signature and status first
        await repository.update_nda_request(token, {
            "signature": request_body.signature,
            "status": "Signed",
            "browser": request_body.browser,
            "os": request_body.os,
            "device_type": request_body.device_type,
            "user_agent": request_body.user_agent,
            "ip_address": ip_address
        })
        
        # Fetch updated request with signature
        nda_request = await repository.get_nda_request_by_token(token)
        
        # Generate PDF
        pdf_bytes = generate_pdf_from_request(nda_request)
        
        # Upload PDF to storage
        employee_name = nda_request.get("employee_name", "Employee")
        filename = f"NDA_{employee_name.replace(' ', '_')}_{token[:8]}.pdf"
        upload_result = await file_handler.upload_bytes(
            file_data=pdf_bytes,
            filename=filename,
            content_type="application/pdf"
        )
        
        # Update NDA request with PDF path in document format
        updated_nda = await repository.update_nda_request(token, {
            "signed_pdf_path": {
                "document_name": filename,
                "document_proof": upload_result["url"],
                "file_type": "application/pdf"
            }
        })
        
        return success_response(
            message="NDA signed successfully and PDF stored",
            data=updated_nda
        )
    except Exception as e:
        return error_response(message=str(e), status_code=500)

from weasyprint import HTML
from io import BytesIO
from fastapi.responses import Response


def generate_pdf_from_request(nda_request: dict) -> bytes:
    """Helper function to generate PDF from NDA request data"""
    pdf_buffer = BytesIO()
    
    signature_data = nda_request.get("signature")
    
    # Parse date
    created_at = nda_request.get("created_at")
    if isinstance(created_at, str):
        try:
            created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        except ValueError:
            created_at = datetime.now()
    elif not isinstance(created_at, datetime):
        created_at = datetime.now()

    # Render HTML
    template = templates.get_template("nda_form.html")
    html_content = template.render({
        "request": nda_request, 
        "employee_name": nda_request.get("employee_name", "_________________"),
        "employee_address": nda_request.get("address", "_________________"),
        "residential_address": nda_request.get("residential_address", "_________________"),
        "role": nda_request.get("role", "_________________"),
        "date": created_at.strftime("%d/%m/%Y"),
        "signature_data": signature_data,
        "token": nda_request.get("token")
    })

    # Generate PDF
    HTML(string=html_content, base_url="").write_pdf(pdf_buffer)
    pdf_buffer.seek(0)
    return pdf_buffer.read()


@router.get("/download/{token}")
async def download_nda_pdf(token: str):
    # Fetch Request Details
    request = await repository.get_nda_request_by_token(token)
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")

    # Check if signed PDF already exists
    signed_pdf = request.get("signed_pdf_path")
    if signed_pdf:
        # TODO: Stream the file from storage instead of regenerating
        # For now, we'll regenerate to maintain compatibility
        pass
    
    # Generate PDF
    pdf_bytes = generate_pdf_from_request(request)
    
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=NDA_{request.get('employee_name', 'Signed')}.pdf"}
    )
