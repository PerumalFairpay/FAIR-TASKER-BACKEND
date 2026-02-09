from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import Response
from fastapi.templating import Jinja2Templates
from app.models import PayslipCreate, PayslipResponse
from app.crud.repository import repository
from app.helper.response_helper import success_response, error_response
from app.helper.file_handler import file_handler
from app.helper.pdf_helper import generate_pdf_from_html, encrypt_pdf
from datetime import datetime
import os
import math
import calendar

router = APIRouter(prefix="/payslip", tags=["Payslip"])

# Setup Jinja2 templates
templates_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
templates = Jinja2Templates(directory=templates_dir)

def num_to_words(num):
    try:
        num = int(float(num))
        if num == 0:
            return "Zero"
            
        def convert_to_words(n):
            units = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine"]
            teens = ["Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
            tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]
            
            if n < 10:
                return units[n]
            elif n < 20:
                return teens[n-10]
            elif n < 100:
                return tens[n//10] + (" " + units[n%10] if n%10 != 0 else "")
            elif n < 1000:
                return units[n//100] + " Hundred" + (" " + convert_to_words(n%100) if n%100 != 0 else "")
            return ""

        def process_indian_system(n):
            if n == 0: return ""
            
            # Parts: Crore, Lakh, Thousand, Hundred+Rest
            res = ""
            if n >= 10000000:
                res += convert_to_words(n // 10000000) + " Crore "
                n %= 10000000
            if n >= 100000:
                res += convert_to_words(n // 100000) + " Lakh "
                n %= 100000
            if n >= 1000:
                res += convert_to_words(n // 1000) + " Thousand "
                n %= 1000
            if n > 0:
                res += convert_to_words(n)
                
            return res.strip()

        words = process_indian_system(num)
        return f"Rupees {words}"
    except:
        return f"Rupees {num}"    
@router.post("/generate")
async def generate_payslip(payslip: PayslipCreate):
    """
    Generate a payslip PDF, encrypt it, and store it.
    """
    try:
        # 1. Fetch Employee Details
        employee = await repository.get_employee(payslip.employee_id)
        if not employee:
            return error_response(message="Employee not found", status_code=404)

        # 2. Prepare Data for Template
        earnings = payslip.earnings or {}
        deductions = payslip.deductions or {}
        
        # Prepare Rows for Receipt style table
        payslip_rows = []
        earning_keys = list(earnings.keys())
        deduction_keys = list(deductions.keys())
        max_rows = max(len(earning_keys), len(deduction_keys))
        
        for i in range(max_rows):
            e_key = earning_keys[i] if i < len(earning_keys) else ""
            e_val = f"{earnings[e_key]:.2f}" if e_key else ""
            
            d_key = deduction_keys[i] if i < len(deduction_keys) else ""
            d_val = f"{deductions[d_key]:.2f}" if d_key else ""
            
            payslip_rows.append({
                "earning_name": e_key,
                "earning_amount": e_val,
                "deduction_name": d_key,
                "deduction_amount": d_val
            })
            
        total_earnings = sum(float(v) for v in earnings.values())
        total_deductions = sum(float(v) for v in deductions.values())
        net_pay = payslip.net_pay
         
        try:
            month_map = {m: i for i, m in enumerate(calendar.month_name) if m}
            month_num = month_map.get(payslip.month.capitalize(), 1)
            _, num_days = calendar.monthrange(payslip.year, month_num)
            paid_days = num_days
        except Exception:
            paid_days = 30 # Fallback
        
        password = ""
        if "mobile" in employee and employee["mobile"]:
            password = employee["mobile"][-4:]
        else:
            password = "0000" # Fallback
            
        if "mobile" in employee:
            password = employee["mobile"]
            
        
        # 3. Render HTML
        template_data = {
            "employee": employee,
            "month_year": f"{payslip.month} {payslip.year}",
            "earnings": earnings,
            "deductions": deductions,
            "payslip_rows": payslip_rows,
            "total_earnings": total_earnings,
            "total_deductions": total_deductions,
            "net_pay": net_pay,
            "net_pay_words": num_to_words(net_pay), # TODO: Improve this
            "paid_days": paid_days,
            "leaves": {} # Placeholder for leave data
        }
        
        template = templates.get_template("payslip.html")
        html_content = template.render(template_data)
        
        # 4. Generate & Encrypt PDF
        # Ensure base_url points to where static assets are if needed
        pdf_bytes = generate_pdf_from_html(html_content, base_url=str(templates_dir))
        encrypted_pdf = encrypt_pdf(pdf_bytes, password)
        
        # 5. Upload PDF
        filename = f"Payslip_{employee.get('name', 'Emp').replace(' ', '_')}_{payslip.month}_{payslip.year}.pdf"
        upload_result = await file_handler.upload_bytes(
            file_data=encrypted_pdf, 
            filename=filename, 
            content_type="application/pdf"
        )
        
        # 6. Save Record
        result = await repository.create_payslip(payslip.dict(), file_path=upload_result["url"])
        
        return success_response(
            message="Payslip generated successfully",
            data=result
        )
        
    except Exception as e:
        return error_response(message=str(e), status_code=500)


@router.get("/list")
async def list_payslips(
    page: int = 1, 
    limit: int = 10,
    employee_id: str = None,
    month: str = None,
    year: str = None
):
    """
    List payslips. Admin sees all (or filtered). Employee sends their ID.
    """
    try:
        data, total = await repository.get_payslips(
            page=page, limit=limit, employee_id=employee_id, month=month, year=year
        )
        
        meta = {
            "current_page": page,
            "total_pages": math.ceil(total / limit),
            "total_items": total,
            "limit": limit
        }
        
        return success_response(
            message="Payslips retrieved successfully",
            data=data,
            meta=meta
        )
    except Exception as e:
        return error_response(message=str(e), status_code=500)

@router.get("/download/{payslip_id}")
async def download_payslip(payslip_id: str):
    """
    Proxy to download the file.
    Note: The file itself is encrypted, so we can serve it directly.
    """
    try:
        payslip = await repository.get_payslip(payslip_id)
        if not payslip:
             return error_response(message="Payslip not found", status_code=404)
             
        file_url = payslip.get("file_path")
        # If it's a relative URL (local storage), we might need to construct full path or redirect
        # But file_handler returns a URL that is accessible via API usually.
        
        return success_response(
            message="Download link",
            data={"url": file_url}
        )
    except Exception as e:
        return error_response(message=str(e), status_code=500)

