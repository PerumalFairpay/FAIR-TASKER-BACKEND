import os
import uuid
from io import BytesIO
from datetime import datetime
from typing import List, Optional
from weasyprint import HTML
from fastapi import APIRouter, HTTPException, Request, BackgroundTasks, UploadFile, File, Form
from fastapi.responses import Response

from app.models import (
    NDARequestCreate,
    NDASignatureRequest,
    NDARegenerateRequest,
    NDAStatusUpdate,
    NDARequestUpdate,
)
from app.helper.response_helper import success_response, error_response
from app.helper.file_handler import file_handler
from app.helper.template_helper import render_nda_template
from app.helper.gmail import gmail_helper
from app.services.api import NDAService

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
    <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #333; max-width: 600px;">
        <h2 style="color: #000; border-bottom: 2px solid #eee; padding-bottom: 10px;">Non-Disclosure Agreement (NDA)</h2>
        <p>Dear {name},</p>
        <p>A Non-Disclosure Agreement (NDA) has been prepared for your review and execution. This document is a standard requirement for your engagement with <strong>FairPAY Tech Works</strong>.</p>
        <p>Please use the secure link below to review the agreement, upload any necessary documentation, and complete the digital signature process:</p>
        <p style="margin: 35px 0; text-align: center;">
            <a href="{full_link}" style="background-color: #000; color: #fff; padding: 14px 28px; text-decoration: none; border-radius: 4px; font-weight: 600; display: inline-block;">Review and Execute NDA</a>
        </p>
        <p style="background-color: #fff9e6; border-left: 4px solid #ffcc00; padding: 15px; margin-top: 25px; font-size: 14px;">
            <strong>Important:</strong> This secure link is time-sensitive. We kindly request that you complete the process at your earliest convenience to avoid any delays in your onboarding.
        </p>
        <p style="margin-top: 30px;">Best regards,<br/><strong>FairPAY Tech Works India Private Limited</strong></p>
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
    
    rejection_html = f"<p><strong>Reason for rejection:</strong> {reason}</p><p>Please contact HR to re-submit your details.</p>" if reason else ""
    
    body = f"""
    <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #333; max-width: 600px;">
        <h2 style="color: #000; border-bottom: 2px solid #eee; padding-bottom: 10px;">NDA Status Update</h2>
        <p>Dear {name},</p>
        <p>This email is to notify you that your recent NDA submission has been reviewed.</p>
        <p>The status of your submission is: <strong style="color: {color}; text-transform: uppercase;">{status_text}</strong>.</p>
        {rejection_html}
        <p style="margin-top: 25px;">Should you have any questions, please reach out to the HR department.</p>
        <p style="margin-top: 30px;">Best regards,<br/><strong>FairPAY Tech Works India Private Limited</strong></p>
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
    <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #333; max-width: 600px;">
        <h2 style="color: #000; border-bottom: 2px solid #eee; padding-bottom: 10px;">NDA Signed Notification</h2>
        <p>Administrative Team,</p>
        <p>This is to inform you that <strong>{employee_name}</strong> ({email}) has successfully completed and signed their Non-Disclosure Agreement.</p>
        <p>The document is now available for review within the administrative dashboard.</p>
        <p style="margin: 30px 0;">
            <a href="{FRONTEND_URL}/admin/nda" style="background-color: #000; color: #fff; padding: 12px 24px; text-decoration: none; border-radius: 4px; font-weight: 600; display: inline-block;">View Signed Document</a>
        </p>
        <p style="font-size: 13px; color: #777; border-top: 1px solid #eee; padding-top: 15px;">
            This is an automated system notification.
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

    # Use nda_date if available, otherwise fallback to created_at
    formatted_date = nda_request.get("nda_date")
    if not formatted_date:
        formatted_date = created_at.strftime("%d/%m/%Y")

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
        "designation": nda_request.get("designation", "_________________"),
        "date": formatted_date,
        "signature_data": signature_data,
        "token": nda_request.get("token")
    })

    # Generate PDF
    HTML(string=html_content, base_url="").write_pdf(pdf_buffer)
    pdf_buffer.seek(0)
    return pdf_buffer.read()


# ------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------

@router.post("/generate")
async def generate_nda_link(nda_request: NDARequestCreate, background_tasks: BackgroundTasks):
    """
    Generate a new NDA link for an employee.
    Admin endpoint to create NDA request with expiry.
    """
    nda_data, token, err = await NDAService.create(nda_request)
    if err:
        status_code = 400 if "already exists" in err.lower() else 500
        return error_response(message=err, status_code=status_code)
    
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
        data={"link": link_url, "nda": NDAService.format_nda_response(nda_data)}
    )


@router.post("/regenerate/{nda_id}")
async def regenerate_nda_link(nda_id: str, request: NDARegenerateRequest, background_tasks: BackgroundTasks):
    """
    Regenerate an NDA link for an existing request.
    Useful for expired links.
    """
    updated_nda, new_token, err = await NDAService.regenerate_token(nda_id, request)
    if err:
        status_code = 404 if "not found" in err.lower() or "invalid" in err.lower() else 500
        return error_response(message=err, status_code=status_code)

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
        data={"link": link_url, "nda": NDAService.format_nda_response(updated_nda)}
    )


@router.delete("/delete/{nda_id}")
@router.delete("/{nda_id}")
async def delete_nda_request(nda_id: str):
    """
    Delete an NDA request.
    Only admin can delete.
    """
    success, err = await NDAService.delete(nda_id)
    if not success:
        status_code = 404 if err and ("not found" in err.lower() or "invalid" in err.lower()) else 500
        return error_response(message=err or "Failed to delete NDA request", status_code=status_code)
    
    return success_response(
        message="NDA request deleted successfully",
        data=[]
    )


@router.get("/list")
@router.get("")
@router.get("/")
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
    nda_requests, total_items, err = await NDAService.list(page=page, limit=limit, search=search, status=status)
    if err:
        return error_response(message=err, status_code=500)
    
    formatted_requests = [NDAService.format_nda_response(req) for req in (nda_requests or [])]
    total_pages = (total_items + limit - 1) // limit if limit else 1
    
    meta = {
        "current_page": page,
        "total_pages": total_pages,
        "total_items": total_items,
        "limit": limit,
        "page": page,
        "status": status or "All",
        "search_keyword": search
    }
    
    return success_response(
        message="NDA requests retrieved successfully",
        data=formatted_requests,
        meta=meta
    )


@router.get("/approved-list")
async def get_approved_ndas():
    """
    Get a lightweight list of approved NDAs for dropdown selection.
    Used during employee creation to pre-fill details.
    """
    approved_ndas, err = await NDAService.get_approved()
    if err:
        return error_response(message=err, status_code=500)
    return success_response(
        message="Approved NDAs retrieved successfully",
        data=[NDAService.format_nda_response(nda) for nda in (approved_ndas or [])]
    )


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

        nda_request, err = await NDAService.get_by_token(token)
        if err or not nda_request:
            raise HTTPException(status_code=404, detail="NDA request not found")
        
        # Check if rejected
        if nda_request.get("status") == "Rejected":
            raise HTTPException(status_code=403, detail="NDA request has been rejected. Please contact HR.")

        # Check if expired
        expires_at = nda_request.get("expires_at")
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
        
        if expires_at and expires_at.tzinfo is not None:
            expires_at = expires_at.replace(tzinfo=None)
        
        if expires_at and datetime.utcnow() > expires_at:
            await NDAService.update_by_token(token, {"status": "Expired"})
            raise HTTPException(status_code=410, detail="NDA link has expired")

        # Verify Email
        stored_email = nda_request.get("email")
        if not stored_email or stored_email.lower().strip() != email.lower().strip():
            raise HTTPException(status_code=403, detail="Invalid Email Address")

        # Render template content using helper (Full Access)
        current_date = datetime.utcnow()
        formatted_date = nda_request.get("nda_date") or current_date.strftime("%d/%m/%Y")
        
        html_content = render_nda_template({
            "request": nda_request,
            "first_name": nda_request.get("first_name"),
            "last_name": nda_request.get("last_name"),
            "employee_name": f"{nda_request.get('first_name', '')} {nda_request.get('last_name', '')}".strip(),
            "designation": nda_request.get("designation"),
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
                "nda": NDAService.format_nda_response(nda_request)
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
        nda_request, err = await NDAService.get_by_token(token)
        if err or not nda_request:
            raise HTTPException(status_code=404, detail="NDA request not found")
        
        # Check if rejected
        if nda_request.get("status") == "Rejected":
            raise HTTPException(status_code=403, detail="NDA request has been rejected")

        # Check if expired
        expires_at = nda_request.get("expires_at")
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
        
        if expires_at and expires_at.tzinfo is not None:
            expires_at = expires_at.replace(tzinfo=None)
        
        if expires_at and datetime.utcnow() > expires_at:
            await NDAService.update_by_token(token, {"status": "Expired"})
            raise HTTPException(status_code=410, detail="NDA link has expired")
        
        safe_data = {
            "first_name": nda_request.get("first_name"),
            "last_name": nda_request.get("last_name"),
            "status": nda_request.get("status"),
            "requires_auth": True 
        }

        return success_response(
            message="NDA request found",
            data={
                "nda": safe_data
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
        nda_request, err = await NDAService.get_by_token(token)
        if err or not nda_request:
            return error_response(message="NDA request not found", status_code=404)
        
        update_dict = {k: v for k, v in update_data.dict().items() if v is not None}
        updated_nda, err = await NDAService.update_by_token(token, update_dict)
        if err or not updated_nda:
            return error_response(message=err or "Failed to update NDA details", status_code=500)
        
        # Render updated template content
        current_date = datetime.utcnow()
        formatted_date = updated_nda.get("nda_date") or current_date.strftime("%d/%m/%Y")
        
        html_content = render_nda_template({
            "request": updated_nda,
            "first_name": updated_nda.get("first_name"),
            "last_name": updated_nda.get("last_name"),
            "employee_name": f"{updated_nda.get('first_name', '')} {updated_nda.get('last_name', '')}".strip(),
            "designation": updated_nda.get("designation"),
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
                "nda": NDAService.format_nda_response(updated_nda)
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
        nda_request, err = await NDAService.get_by_token(token)
        if err or not nda_request:
            return error_response(message="NDA request not found", status_code=404)
        
        # Check if expired
        expires_at = nda_request.get("expires_at")
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
        
        if expires_at and expires_at.tzinfo is not None:
            expires_at = expires_at.replace(tzinfo=None)
        
        if expires_at and datetime.utcnow() > expires_at:
            return error_response(message="NDA link has expired", status_code=410)
        
        if len(files) != len(names):
            return error_response(message="Number of files and names must match", status_code=400)

        uploaded_results = await file_handler.upload_files(files)
        
        new_documents = []
        for i, result in enumerate(uploaded_results):
            new_documents.append({
                "document_name": names[i],
                "document_proof": result["url"],
                "file_type": files[i].content_type
            })
        
        existing_docs = nda_request.get("documents", []) or []
        existing_docs.extend(new_documents)
        
        updated_nda, err = await NDAService.update_by_token(token, {
            "documents": existing_docs,
            "status": "Document Uploaded"
        })
        if err:
            return error_response(message=err, status_code=500)
        
        return success_response(
            message="Documents uploaded successfully",
            data=NDAService.format_nda_response(updated_nda)
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
        nda_request, err = await NDAService.get_by_token(token)
        if err or not nda_request:
            return error_response(message="NDA request not found", status_code=404)
        
        expires_at = nda_request.get("expires_at")
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
        
        if expires_at and expires_at.tzinfo is not None:
            expires_at = expires_at.replace(tzinfo=None)
        
        if expires_at and datetime.utcnow() > expires_at:
            return error_response(message="NDA link has expired", status_code=410)
        
        ip_address = request_body.ip_address
        if not ip_address and request.client:
            ip_address = request.client.host
            
        # Update signature and status
        await NDAService.update_by_token(token, {
            "signature": request_body.signature,
            "status": "Signed",
            "browser": request_body.browser,
            "os": request_body.os,
            "device_type": request_body.device_type,
            "user_agent": request_body.user_agent,
            "ip_address": ip_address
        })
        
        # Fetch updated request with signature
        nda_request, _ = await NDAService.get_by_token(token)
        
        # Generate PDF
        pdf_bytes = generate_pdf_from_request(nda_request)
        
        first_name = nda_request.get("first_name", "Employee")
        last_name = nda_request.get("last_name", "")
        employee_name = f"{first_name}_{last_name}".strip("_")
        filename = f"NDA_{employee_name.replace(' ', '_')}_{token[:8]}.pdf"
        upload_result = await file_handler.upload_bytes(
            file_data=pdf_bytes,
            filename=filename,
            content_type="application/pdf"
        )
        
        # Update NDA request with PDF path
        updated_nda, err = await NDAService.update_by_token(token, {
            "signed_pdf_path": {
                "document_name": filename,
                "document_proof": upload_result["url"],
                "file_type": "application/pdf"
            }
        })
        if err:
            return error_response(message=err, status_code=500)
        
        # Notify Admin in background
        background_tasks.add_task(
            _notify_admin_nda_signed, 
            updated_nda.get("first_name"), 
            updated_nda.get("last_name"), 
            updated_nda.get("email")
        )

        return success_response(
            message="NDA signed successfully and PDF stored",
            data=NDAService.format_nda_response(updated_nda)
        )
    except Exception as e:
        return error_response(message=str(e), status_code=500)


@router.get("/download/{token}")
async def download_nda_pdf(token: str):
    nda_request, err = await NDAService.get_by_token(token)
    if err or not nda_request:
        raise HTTPException(status_code=404, detail="Request not found")

    pdf_bytes = generate_pdf_from_request(nda_request)
    
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=NDA_{nda_request.get('first_name', 'Signed')}_{nda_request.get('last_name', '')}.pdf"}
    )


@router.patch("/{nda_id}/status")
async def update_nda_status(nda_id: str, status_update: NDAStatusUpdate, background_tasks: BackgroundTasks):
    """
    Admin endpoint to approve or reject an NDA.
    """
    try:
        if status_update.status not in ["Approved", "Rejected"]:
            return error_response(message="Status must be Approved or Rejected", status_code=400)
            
        updated_nda, err = await NDAService.update_status_by_id(
            nda_id=nda_id,
            status=status_update.status,
            rejection_reason=status_update.rejection_reason if status_update.status == "Rejected" else None
        )
        
        if err or not updated_nda:
            status_code = 404 if err and ("not found" in err.lower() or "invalid" in err.lower()) else 500
            return error_response(message=err or "NDA request not found", status_code=status_code)
        
        # Notify employee in background
        background_tasks.add_task(
            _send_nda_status_email, 
            updated_nda.get("email"), 
            updated_nda.get("first_name"), 
            status_update.status,
            status_update.rejection_reason if status_update.status == "Rejected" else None
        )

        # If approved, regenerate and re-upload the PDF
        if status_update.status == "Approved":
            pdf_bytes = generate_pdf_from_request(updated_nda)
            
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
            
            updated_nda, _ = await NDAService.update_by_token(token, {
                "signed_pdf_path": {
                    "document_name": filename,
                    "document_proof": upload_result["url"],
                    "file_type": "application/pdf"
                }
            })
            
        return success_response(
            message=f"NDA status updated to {status_update.status} and email sent",
            data=NDAService.format_nda_response(updated_nda)
        )
    except Exception as e:
        return error_response(message=str(e), status_code=500)
