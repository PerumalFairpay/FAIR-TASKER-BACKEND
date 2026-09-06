import os
import math
import calendar
from io import BytesIO
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from bson import ObjectId
from fastapi.templating import Jinja2Templates
from app.database import payslips_collection, employees_collection
from app.models import PayslipCreate, PayslipUpdate
from app.helper.file_handler import file_handler
from app.helper.pdf_helper import generate_pdf_from_html, encrypt_pdf, decrypt_pdf
from app.core.config import API_URL
from app.utils import normalize
import traceback

templates_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "templates")
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
            if n == 0:
                return ""

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
    except Exception:
        return f"Rupees {num}"


class PayslipService:

    @staticmethod
    def _extract_password_from_dob(employee: dict) -> Tuple[Optional[str], Optional[str]]:
        if "date_of_birth" not in employee or not employee["date_of_birth"]:
            return None, "Employee Date of Birth is required to generate/manage payslip. Please update employee profile."
        try:
            dob = employee["date_of_birth"]
            if "-" in dob:
                parts = dob.split("-")
                password = f"{parts[2]}{parts[1]}{parts[0]}"
            else:
                password = dob.replace("/", "").replace("-", "")
            return password, None
        except Exception:
            return None, "Invalid Date of Birth format. Please update employee profile with valid DOB (YYYY-MM-DD)."

    @staticmethod
    async def generate(payslip: PayslipCreate) -> Tuple[Optional[dict], Optional[str]]:
        try:
            if not ObjectId.is_valid(payslip.employee_id):
                return None, "Invalid employee ID"

            employee = await employees_collection.find_one({
                "_id": ObjectId(payslip.employee_id),
                "is_deleted": {"$ne": True}
            })
            if not employee:
                return None, "Employee not found"

            existing = await payslips_collection.find_one({
                "employee_id": payslip.employee_id,
                "month": payslip.month,
                "year": payslip.year,
                "is_deleted": {"$ne": True}
            })
            if existing:
                return None, f"Payslip already exists for {payslip.month} {payslip.year}"

            password, pass_err = PayslipService._extract_password_from_dob(employee)
            if pass_err:
                return None, pass_err

            earnings = payslip.earnings or {}
            deductions = payslip.deductions or {}

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
                paid_days = 30

            template_data = {
                "employee": normalize(employee),
                "month_year": f"{payslip.month} {payslip.year}",
                "earnings": earnings,
                "deductions": deductions,
                "payslip_rows": payslip_rows,
                "total_earnings": total_earnings,
                "total_deductions": total_deductions,
                "net_pay": net_pay,
                "net_pay_words": num_to_words(net_pay),
                "paid_days": paid_days,
                "leaves": {}
            }

            template = templates.get_template("payslip.html")
            html_content = template.render(template_data)

            pdf_bytes = generate_pdf_from_html(html_content, base_url=str(templates_dir))
            encrypted_pdf = encrypt_pdf(pdf_bytes, password)

            filename = f"Payslip_{employee.get('name', 'Emp').replace(' ', '_')}_{payslip.month}_{payslip.year}.pdf"
            upload_result = await file_handler.upload_bytes(
                file_data=encrypted_pdf,
                filename=filename,
                content_type="application/pdf"
            )

            payslip_dict = payslip.dict()
            payslip_dict["file_path"] = upload_result["url"]
            payslip_dict["generated_at"] = datetime.utcnow()
            payslip_dict["status"] = "Generated"
            payslip_dict["is_deleted"] = False
            payslip_dict["deleted_at"] = None

            result = await payslips_collection.insert_one(payslip_dict)
            payslip_dict["id"] = str(result.inserted_id)

            payslip_norm = normalize(payslip_dict)
            payslip_norm["employee_name"] = employee.get("name")
            payslip_norm["employee_email"] = employee.get("email")
            payslip_norm["employee_mobile"] = employee.get("mobile")

            return payslip_norm, None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def list(
        page: int = 1,
        limit: int = 10,
        employee_id: Optional[str] = None,
        month: Optional[str] = None,
        year: Optional[str] = None,
        search: Optional[str] = None
    ) -> Tuple[Optional[List[dict]], Optional[dict], Optional[str]]:
        try:
            query = {"is_deleted": {"$ne": True}}
            if employee_id:
                query["employee_id"] = employee_id
            if month and month != "All":
                query["month"] = month
            if year and year != "All":
                try:
                    query["year"] = int(year)
                except ValueError:
                    query["year"] = year

            if search:
                regex_pattern = {"$regex": search, "$options": "i"}
                matched_employees = await employees_collection.find({
                    "$or": [
                        {"name": regex_pattern},
                        {"employee_no_id": regex_pattern},
                        {"email": regex_pattern}
                    ],
                    "is_deleted": {"$ne": True}
                }, {"_id": 1}).to_list(length=None)

                matched_ids = [str(emp["_id"]) for emp in matched_employees]

                if employee_id:
                    if employee_id in matched_ids:
                        query["employee_id"] = employee_id
                    else:
                        meta = {
                            "current_page": page,
                            "total_pages": 0,
                            "total_items": 0,
                            "limit": limit
                        }
                        return [], meta, None
                else:
                    query["employee_id"] = {"$in": matched_ids}

            skip = (page - 1) * limit
            total_items = await payslips_collection.count_documents(query)

            payslips = (
                await payslips_collection.find(query)
                .sort("generated_at", -1)
                .skip(skip)
                .limit(limit)
                .to_list(length=limit)
            )

            results = []
            for p in payslips:
                p_norm = normalize(p)
                if ObjectId.is_valid(p_norm.get("employee_id", "")):
                    emp = await employees_collection.find_one({"_id": ObjectId(p_norm["employee_id"])})
                    if emp:
                        p_norm["employee_name"] = emp.get("name")
                        p_norm["employee_email"] = emp.get("email")
                        p_norm["employee_mobile"] = emp.get("mobile")
                results.append(p_norm)

            total_pages = (total_items + limit - 1) // limit if limit > 0 else 0
            meta = {
                "current_page": page,
                "total_pages": total_pages,
                "total_items": total_items,
                "limit": limit
            }

            return results, meta, None
        except Exception as e:
            traceback.print_exc()
            return None, None, str(e)

    @staticmethod
    async def get_latest(employee_id: str) -> Tuple[Optional[dict], Optional[str]]:
        try:
            payslip = await payslips_collection.find_one(
                {"employee_id": employee_id, "is_deleted": {"$ne": True}},
                sort=[("year", -1), ("generated_at", -1)]
            )
            if not payslip:
                return None, "No previous payslip found for this employee"

            return {
                "earnings": payslip.get("earnings", {}),
                "deductions": payslip.get("deductions", {}),
                "month": payslip.get("month"),
                "year": payslip.get("year"),
            }, None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def get(payslip_id: str) -> Tuple[Optional[dict], Optional[str]]:
        try:
            if not ObjectId.is_valid(payslip_id):
                return None, "Invalid payslip ID"

            payslip = await payslips_collection.find_one({
                "_id": ObjectId(payslip_id),
                "is_deleted": {"$ne": True}
            })
            if not payslip:
                return None, "Payslip not found"

            p_norm = normalize(payslip)
            if ObjectId.is_valid(p_norm.get("employee_id", "")):
                emp = await employees_collection.find_one({"_id": ObjectId(p_norm["employee_id"])})
                if emp:
                    p_norm["employee_name"] = emp.get("name")
                    p_norm["employee_email"] = emp.get("email")
                    p_norm["employee_mobile"] = emp.get("mobile")

            return p_norm, None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def get_decrypted_pdf(payslip_id: str) -> Tuple[Optional[bytes], Optional[str], Optional[str]]:
        try:
            if not ObjectId.is_valid(payslip_id):
                return None, None, "Invalid payslip ID"

            payslip = await payslips_collection.find_one({
                "_id": ObjectId(payslip_id),
                "is_deleted": {"$ne": True}
            })
            if not payslip:
                return None, None, "Payslip not found"

            employee = await employees_collection.find_one({"_id": ObjectId(payslip["employee_id"])})
            if not employee:
                return None, None, "Employee not found"

            password, pass_err = PayslipService._extract_password_from_dob(employee)
            if pass_err:
                return None, None, pass_err

            file_url = payslip.get("file_path", "")
            file_id = file_url.split("/")[-1]
            file_data = file_handler.get_file(file_id)
            if not file_data:
                return None, None, "PDF file not found"

            decrypted_pdf = decrypt_pdf(file_data["Body"].read(), password)
            filename = f"Payslip_{employee.get('name', 'Emp').replace(' ', '_')}_{payslip['month']}_{payslip['year']}.pdf"
            return decrypted_pdf, filename, None
        except Exception as e:
            traceback.print_exc()
            return None, None, str(e)

    @staticmethod
    async def update(payslip_id: str, payslip_update: PayslipUpdate) -> Tuple[Optional[dict], Optional[str]]:
        try:
            if not ObjectId.is_valid(payslip_id):
                return None, "Invalid payslip ID"

            existing = await payslips_collection.find_one({
                "_id": ObjectId(payslip_id),
                "is_deleted": {"$ne": True}
            })
            if not existing:
                return None, "Payslip not found"

            update_dict = {k: v for k, v in payslip_update.dict().items() if v is not None}
            merged_data = {**existing, **update_dict}

            employee = await employees_collection.find_one({"_id": ObjectId(merged_data["employee_id"])})
            if not employee:
                return None, "Employee not found"

            password, pass_err = PayslipService._extract_password_from_dob(employee)
            if pass_err:
                return None, pass_err

            earnings = merged_data.get("earnings", {})
            deductions = merged_data.get("deductions", {})

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
            net_pay = merged_data.get("net_pay", total_earnings - total_deductions)

            try:
                month_map = {m: i for i, m in enumerate(calendar.month_name) if m}
                month_num = month_map.get(merged_data["month"].capitalize(), 1)
                _, num_days = calendar.monthrange(merged_data["year"], month_num)
                paid_days = num_days
            except Exception:
                paid_days = 30

            template_data = {
                "employee": normalize(employee),
                "month_year": f"{merged_data['month']} {merged_data['year']}",
                "earnings": earnings,
                "deductions": deductions,
                "payslip_rows": payslip_rows,
                "total_earnings": total_earnings,
                "total_deductions": total_deductions,
                "net_pay": net_pay,
                "net_pay_words": num_to_words(net_pay),
                "paid_days": paid_days,
                "leaves": {}
            }

            template = templates.get_template("payslip.html")
            html_content = template.render(template_data)

            pdf_bytes = generate_pdf_from_html(html_content, base_url=str(templates_dir))
            encrypted_pdf = encrypt_pdf(pdf_bytes, password)

            filename = f"Payslip_{employee.get('name', 'Emp').replace(' ', '_')}_{merged_data['month']}_{merged_data['year']}.pdf"
            upload_result = await file_handler.upload_bytes(
                file_data=encrypted_pdf,
                filename=filename,
                content_type="application/pdf"
            )

            update_dict["file_path"] = upload_result["url"]
            update_dict["updated_at"] = datetime.utcnow()

            await payslips_collection.update_one(
                {"_id": ObjectId(payslip_id)},
                {"$set": update_dict}
            )

            return await PayslipService.get(payslip_id)
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def delete(payslip_id: str) -> Tuple[bool, Optional[str]]:
        try:
            if not ObjectId.is_valid(payslip_id):
                return False, "Invalid payslip ID"

            result = await payslips_collection.update_one(
                {"_id": ObjectId(payslip_id), "is_deleted": {"$ne": True}},
                {"$set": {"is_deleted": True, "deleted_at": datetime.utcnow()}}
            )
            if result.matched_count == 0:
                return False, "Payslip not found"

            return True, None
        except Exception as e:
            traceback.print_exc()
            return False, str(e)
