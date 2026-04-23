from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
import os
from app.models import NDARequestCreate, NDASignatureRequest, NDARegenerateRequest, NDAStatusUpdate, NDARequestUpdate
from app.crud.repository import repository
from app.helper.response_helper import success_response, error_response
from datetime import datetime, timedelta
import uuid
from typing import List
from fastapi import UploadFile, File, Form
from app.helper.file_handler import file_handler
from app.helper.template_helper import render_nda_template
from weasyprint import HTML
from io import BytesIO
from fastapi.responses import Response
from app.helper.gmail import gmail_helper

router = APIRouter(prefix="/nda", tags=["NDA"])

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "fairpayhrm@gmail.com")


# ------------------------------------------------------------------
# Email notification helpers
# ------------------------------------------------------------------

def _send_nda_link_email(email: str, name: str, link: str):
    """Send NDA link to the employee."""
    full_link = f"{FRONTEND_URL}{link}"
    body = f"""
    <div style="font-family: sans-serif; line-height: 1.6; color: #333;">
        <h2 style="color: #000;">Non-Disclosure Agreement (NDA)</h2>
        <p>Hi {name},</p>
        <p>A new Non-Disclosure Agreement (NDA) has been generated for you. Please click the link below to review, upload necessary documents, and sign the agreement:</p>
        <p style="margin: 30px 0;">
            <a href="{full_link}" style="background-color: #000; color: #fff; padding: 12px 24px; text-decoration: none; border-radius: 4px; font-weight: bold;">Review and Sign NDA</a>
        </p>
        <p>Alternatively, you can copy and paste this URL into your browser:</p>
        <p style="word-break: break-all; color: #666;">{full_link}</p>
        <p><strong>Note:</strong> This link will expire soon. Please complete the process at your earliest convenience.</p>
        <p>Best regards,<br/><strong>FairPay Team</strong></p>
    </div>
    """
    try:
        gmail_helper.send_email(
            to=email,
            subject="Action Required: Review and Sign your NDA",
            body_html=body
        )
    except Exception as e:
        print(f"[Gmail] Failed to send NDA link email: {e}")

def _send_nda_status_email(email: str, name: str, status: str, reason: str = None):
    """Notify employee of NDA status update."""
    status_text = "Approved" if status == "Approved" else "Rejected"
    color = "#28a745" if status == "Approved" else "#dc3545"
    
    rejection_html = f"<p><strong>Reason for rejection:</strong> {reason}</p><p>Please use the previous link or contact HR to re-submit your details.</p>" if reason else ""
    
    body = f"""
    <div style="font-family: sans-serif; line-height: 1.6; color: #333;">
        <h2 style="color: #000;">NDA Status Update</h2>
        <p>Hi {name},</p>
        <p>Your NDA submission has been <strong style="color: {color};">{status_text}</strong>.</p>
        {rejection_html}
        <p>Best regards,<br/><strong>FairPay Team</strong></p>
    </div>
    """
    try:
        gmail_helper.send_email(
            to=email,
            subject=f"NDA Status Update: {status_text}",
            body_html=body
        )
    except Exception as e:
        print(f"[Gmail] Failed to send status email: {e}")

def _notify_admin_nda_signed(first_name: str, last_name: str, email: str):
    """Notify admin that an NDA has been signed."""
    employee_name = f"{first_name} {last_name}"
    body = f"""
    <div style="font-family: sans-serif; line-height: 1.6; color: #333;">
        <h2 style="color: #000;">NDA Signed Notification</h2>
        <p>Admin,</p>
        <p>The employee <strong>{employee_name}</strong> ({email}) has just signed their NDA.</p>
        <p>You can now review the document in the admin dashboard.</p>
        <p style="margin-top: 20px;">
            <a href="{FRONTEND_URL}/admin/nda" style="color: #000; font-weight: bold;">View NDA Dashboard</a>
        </p>
    </div>
    """
    try:
        gmail_helper.send_email(
            to=ADMIN_EMAIL,
            subject=f"NDA Signed: {employee_name}",
            body_html=body
        )
    except Exception as e:
        print(f"[Gmail] Failed to notify admin: {e}")

# ------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------

@router.post("/generate")
async def generate_nda_link(nda_request: NDARequestCreate, background_tasks: BackgroundTasks):
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
         
        existing_nda = await repository.nda_requests.find_one({"email": nda_request.email})
        if existing_nda:
             return error_response(message=f"NDA request already exists for email {nda_request.email}", status_code=400)
         
        nda_data = await repository.create_nda_request(nda_request, token, expires_at)
         
        link_url = f"/employee/nda/{token}"
        
        # Send Email in background
        background_tasks.add_task(
            _send_nda_link_email, 
            nda_request.email, 
            nda_request.first_name, 
            link_url
        )
        
        return success_response(
            message="NDA link generated successfully and email sent",
            data={"link": link_url, "nda": nda_data}
        )
    except Exception as e:
        return error_response(message=str(e), status_code=500)


@router.post("/regenerate/{nda_id}")
async def regenerate_nda_link(nda_id: str, request: NDARegenerateRequest, background_tasks: BackgroundTasks):
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
 
        link_url = f"/employee/nda/{new_token}"
        
        # Send Email in background
        background_tasks.add_task(
            _send_nda_link_email, 
            updated_nda.get("email"), 
            updated_nda.get("first_name"), 
            link_url
        )

        return success_response(
            message="NDA link regenerated successfully and email sent",
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

        # Render template content using helper (Full Access)
        current_date = datetime.utcnow()
        formatted_date = current_date.strftime("%d/%m/%Y")
        
        html_content = render_nda_template({
            "request": nda_request,
            "first_name": nda_request.get("first_name"),
            "last_name": nda_request.get("last_name"),
            "employee_name": f"{nda_request.get('first_name', '')} {nda_request.get('last_name', '')}".strip(),
            "role": nda_request.get("role"),
            "employee_address": nda_request.get("address"),
            "residential_address": nda_request.get("residential_address"),
            "mobile": nda_request.get("mobile"),
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
            "first_name": nda_request.get("first_name"),
            "last_name": nda_request.get("last_name"),
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


@router.patch("/update/{token}")
async def update_nda_details(token: str, update_data: NDARequestUpdate):
    """
    Update NDA request details (address, residential_address) by token.
    Allows the employee to fill in their details after link generation.
    """
    try:
        # Get NDA request
        nda_request = await repository.get_nda_request_by_token(token)
        
        if not nda_request:
            return error_response(message="NDA request not found", status_code=404)
        
        # Update details
        # Filter out None values to avoid overwriting existing data with nulls
        update_dict = {k: v for k, v in update_data.dict().items() if v is not None}
        
        updated_nda = await repository.update_nda_request(token, update_dict)
        
        # Render updated template content
        current_date = datetime.utcnow()
        formatted_date = current_date.strftime("%d/%m/%Y")
        
        html_content = render_nda_template({
            "request": updated_nda,
            "first_name": updated_nda.get("first_name"),
            "last_name": updated_nda.get("last_name"),
            "employee_name": f"{updated_nda.get('first_name', '')} {updated_nda.get('last_name', '')}".strip(),
            "role": updated_nda.get("role"),
            "employee_address": updated_nda.get("address"),
            "residential_address": updated_nda.get("residential_address"),
            "mobile": updated_nda.get("mobile"),
            "date": formatted_date,
            "token": token
        })
        
        return success_response(
            message="NDA details updated successfully",
            data={
                "html_content": html_content,
                "nda": updated_nda
            }
        )
    except Exception as e:
        return error_response(message=str(e), status_code=500)


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
        
        updated_nda = await repository.update_nda_request(token, {
            "documents": existing_docs,
            "status": "Document Uploaded"
        })
        
        return success_response(
            message="Documents uploaded successfully",
            data=updated_nda
        )
    except Exception as e:
        return error_response(message=str(e), status_code=500)


@router.post("/sign/{token}")
async def sign_nda(token: str, request_body: NDASignatureRequest, request: Request, background_tasks: BackgroundTasks):
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
        first_name = nda_request.get("first_name", "Employee")
        last_name = nda_request.get("last_name", "")
        employee_name = f"{first_name}_{last_name}".strip("_")
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
        
        # Notify Admin in background
        background_tasks.add_task(
            _notify_admin_nda_signed, 
            updated_nda.get("first_name"), 
            updated_nda.get("last_name"), 
            updated_nda.get("email")
        )

        return success_response(
            message="NDA signed successfully and PDF stored",
            data=updated_nda
        )
    except Exception as e:
        return error_response(message=str(e), status_code=500)




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

    # Render HTML using centralized helper
    first_name = nda_request.get("first_name", "_________________")
    last_name = nda_request.get("last_name", "_________________")
    employee_name = f"{first_name} {last_name}"
    
    html_content = render_nda_template({
        "request": nda_request, 
        "first_name": first_name,
        "last_name": last_name,
        "employee_name": employee_name,
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
        headers={"Content-Disposition": f"attachment; filename=NDA_{request.get('first_name', 'Signed')}_{request.get('last_name', '')}.pdf"}
    )


@router.patch("/{nda_id}/status")
async def update_nda_status(nda_id: str, status_update: NDAStatusUpdate, background_tasks: BackgroundTasks):
    """
    Admin endpoint to approve or reject an NDA.
    If rejected, it automatically regenerates a fresh token for the employee,
    requiring them to re-upload documents and re-sign.
    """
    try:
        if status_update.status not in ["Approved", "Rejected"]:
            return error_response(message="Status must be Approved or Rejected", status_code=400)
            
        # Update status
        updated_nda = await repository.update_nda_status_by_id(
            nda_id=nda_id,
            status=status_update.status,
            rejection_reason=status_update.rejection_reason if status_update.status == "Rejected" else None
        )
        
        if not updated_nda:
            return error_response(message="NDA request not found", status_code=404)
        
        # Notify employee in background
        background_tasks.add_task(
            _send_nda_status_email, 
            updated_nda.get("email"), 
            updated_nda.get("first_name"), 
            status_update.status,
            status_update.rejection_reason if status_update.status == "Rejected" else None
        )

        # If rejected, automatically provide a fresh start URL
        if status_update.status == "Rejected":
            new_token = str(uuid.uuid4())
            # Usually regenerates with 1 hour expiry
            expires_at = datetime.utcnow() + timedelta(hours=1)
            updated_nda = await repository.regenerate_nda_token(nda_id, new_token, expires_at)
            
            # Send new link email
            background_tasks.add_task(
                _send_nda_link_email, 
                updated_nda.get("email"), 
                updated_nda.get("first_name"), 
                f"/employee/nda/{new_token}"
            )
        
        # If approved, regenerate and re-upload the PDF to remove watermarks and add signs
        elif status_update.status == "Approved":
            # Generate new PDF with the updated status
            pdf_bytes = generate_pdf_from_request(updated_nda)
            
            # Re-upload PDF
            first_name = updated_nda.get("first_name", "Employee")
            last_name = updated_nda.get("last_name", "")
            employee_name = f"{first_name}_{last_name}".strip("_")
            token = updated_nda.get("token", str(uuid.uuid4()))
            filename = f"NDA_{employee_name.replace(' ', '_')}_{token[:8]}.pdf"
            
            upload_result = await file_handler.upload_bytes(
                file_data=pdf_bytes,
                filename=filename,
                content_type="application/pdf"
            )
            
            # Update background check/NDA record with new PDF path
            updated_nda = await repository.update_nda_request(token, {
                "signed_pdf_path": {
                    "document_name": filename,
                    "document_proof": upload_result["url"],
                    "file_type": "application/pdf"
                }
            })
            
        return success_response(
            message=f"NDA status updated to {status_update.status} and email sent",
            data=updated_nda
        )
    except Exception as e:
        return error_response(message=str(e), status_code=500)
