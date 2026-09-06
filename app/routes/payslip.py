from io import BytesIO
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.responses import StreamingResponse
from app.models import PayslipCreate, PayslipUpdate
from app.services.api.payslip import PayslipService
from app.helper.response_helper import success_response, error_response
from app.auth import get_current_user, verify_token
from app.core.config import API_URL

router = APIRouter(prefix="/payslip", tags=["Payslip"])


@router.post("/generate", dependencies=[Depends(verify_token)])
async def generate_payslip(payslip: PayslipCreate):
    """
    Generate a payslip PDF, encrypt it, and store it.
    """
    data, error = await PayslipService.generate(payslip)
    if error:
        status_code = 404 if "not found" in error.lower() else (400 if "already exists" in error.lower() or "required" in error.lower() or "invalid" in error.lower() else 500)
        return error_response(message=error, status_code=status_code)
    return success_response(message="Payslip generated successfully", data=data, status_code=201)


@router.get("/list", dependencies=[Depends(verify_token)])
async def list_payslips(
    page: int = 1,
    limit: int = 10,
    employee_id: Optional[str] = None,
    month: Optional[str] = None,
    year: Optional[str] = None,
    search: Optional[str] = None
):
    """
    List payslips. Admin sees all (or filtered). Employee sends their ID.
    """
    data, meta, error = await PayslipService.list(
        page=page,
        limit=limit,
        employee_id=employee_id,
        month=month,
        year=year,
        search=search
    )
    if error:
        return error_response(message=f"Failed to fetch payslips: {error}", status_code=500)
    return success_response(
        message="Payslips retrieved successfully",
        data=data,
        meta=meta
    )


@router.get("/latest/{employee_id}", dependencies=[Depends(verify_token)])
async def get_latest_payslip(employee_id: str):
    """
    Get the most recent payslip for a specific employee.
    Returns earnings and deductions to allow copying to a new payslip.
    """
    data, error = await PayslipService.get_latest(employee_id)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(
        message="Latest payslip retrieved successfully",
        data=data
    )


@router.get("/download/{payslip_id}")
async def download_payslip(payslip_id: str, current_user: dict = Depends(get_current_user)):
    """
    Proxy to download the file.
    Note: Admin gets unencrypted view link, Employee gets encrypted file link.
    """
    payslip, error = await PayslipService.get(payslip_id)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)

    if current_user.get("role") == "admin":
        return success_response(
            message="Download link",
            data={"url": f"{API_URL}/api/payslip/admin/view/{payslip_id}"}
        )

    file_url = payslip.get("file_path")
    return success_response(
        message="Download link",
        data={"url": file_url}
    )


@router.get("/admin/view/{payslip_id}")
async def view_payslip_admin(payslip_id: str, current_user: dict = Depends(get_current_user)):
    """
    Admin only: Decrypt the payslip on-the-fly and stream it to the browser.
    """
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    decrypted_pdf, filename, error = await PayslipService.get_decrypted_pdf(payslip_id)
    if error:
        status_code = 404 if "not found" in error.lower() else (400 if "required" in error.lower() or "invalid" in error.lower() else 500)
        raise HTTPException(status_code=status_code, detail=error)

    return StreamingResponse(
        BytesIO(decrypted_pdf),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'}
    )


@router.put("/update/{payslip_id}", dependencies=[Depends(verify_token)])
async def update_payslip(payslip_id: str, payslip: PayslipUpdate):
    """
    Update an existing payslip and regenerate the PDF.
    """
    data, error = await PayslipService.update(payslip_id, payslip)
    if error:
        status_code = 404 if "not found" in error.lower() else (400 if "required" in error.lower() or "invalid" in error.lower() else 500)
        return error_response(message=error, status_code=status_code)
    return success_response(message="Payslip updated successfully", data=data)


@router.delete("/delete/{payslip_id}", dependencies=[Depends(verify_token)])
async def delete_payslip(payslip_id: str):
    success, error = await PayslipService.delete(payslip_id)
    if error:
        status_code = 404 if "not found" in error.lower() or "invalid" in error.lower() else 500
        return error_response(message=error, status_code=status_code)
    return success_response(message="Payslip deleted successfully", data=[])
