from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from app.models import NDARequestCreate, NDARequestUpdate, NDARequestResponse, NDASignatureRequest
from app.crud.repository import repository
from app.helper.response_helper import success_response, error_response
from datetime import datetime, timedelta
import uuid
import os
from typing import List
from fastapi import UploadFile, File
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
        
        # Set expiry to 1 hour from now
        expires_at = datetime.utcnow() + timedelta(hours=1)
        
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


@router.get("/view/{token}")
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
        
        # Render template content as string
        template = templates.get_template("nda_form.html")
        html_content = template.render({
            "request": request,
            "employee_name": nda_request.get("employee_name"),
            "role": nda_request.get("role"),
            "employee_address": nda_request.get("address"),
            "date": formatted_date,
            "token": token
        })

        return success_response(
            message="NDA details retrieved successfully",
            data={
                "html_content": html_content,
                "nda": nda_request
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload/{token}")
async def upload_documents(token: str, files: List[UploadFile] = File(...)):
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
        
        # Upload files using file_handler
        uploaded_results = await file_handler.upload_files(files)
        
        # Create document objects with metadata
        new_documents = []
        for i, result in enumerate(uploaded_results):
            new_documents.append({
                "document_name": result["name"],
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
async def sign_nda(token: str, request_body: NDASignatureRequest):
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
            "signature": request_body.signature,
            "status": "Signed"
        })
        
        return success_response(
            message="NDA signed successfully",
            data=updated_nda
        )
    except Exception as e:
        return error_response(message=str(e), status_code=500)

from weasyprint import HTML
from io import BytesIO
from fastapi.responses import Response

@router.get("/download/{token}")
async def download_nda_pdf(token: str):
    pdf_buffer = BytesIO()
    
    # 1. Fetch Request Details
    request = await repository.get_nda_request_by_token(token)
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")

    # 2. Prepare Data for Template
    data = request
    employee_name = "N/A"
    signature_data = request.get("signature")
    
    if "employee_id" in request:
         # Ideally fetch employee details, but for now use what's available or fetching logic if needed.
         # Assuming request object might have employee details joined or we ignore for now as per current view logic.
         pass

    # The view endpoint logic does something similar, ensuring we pass "signature_data"
    
    # Parse date
    created_at = request.get("created_at")
    if isinstance(created_at, str):
        try:
            # Handle potential millisecond precision or 'Z' suffix
            created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        except ValueError:
            created_at = datetime.now() # Fallback
    elif not isinstance(created_at, datetime):
        created_at = datetime.now()

    # 3. Render HTML
    template = templates.get_template("nda_form.html")
    # We pass the same context as the view, but ensure signature is present
    html_content = template.render({
        "request": request, 
        "employee_name": request.get("employee_name", "_________________"),
        "employee_address": request.get("address", "_________________"),
        "role": request.get("role", "_________________"),
        "date": created_at.strftime("%d/%m/%Y"),
        "signature_data": signature_data,
        "token": token
    })

    # 4. Generate PDF
    HTML(string=html_content, base_url="").write_pdf(pdf_buffer)
    
    # 5. Return PDF
    pdf_buffer.seek(0)
    return Response(
        content=pdf_buffer.read(),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=NDA_{request.get('employee_name', 'Signed')}.pdf"}
    )
