from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from bson import ObjectId
from app.database import (
    employees_collection,
    users_collection,
    employee_documents_collection,
    checklist_templates_collection,
    nda_requests_collection,
    tasks_collection,
    projects_collection,
    clients_collection,
    assets_collection,
    asset_categories_collection,
    roles_collection,
    attendance_collection
)
from app.models import EmployeeCreate, EmployeeUpdate, EmployeeDocument
from app.utils import normalize, get_password_hash
from app.services.api.leave_request import LeaveRequestService
import traceback


class EmployeeService:

    @staticmethod
    async def get_dashboard_metrics(employee_id: Optional[str] = None) -> dict:
        try:
            today = datetime.now().date()
            start_of_today = today.strftime("%Y-%m-%d")
            start_of_month = today.replace(day=1).strftime("%Y-%m-%d")
            start_of_year = today.replace(month=1, day=1).strftime("%Y-%m-%d")

            async def aggregate_stats(start_date: str, end_date: str = None):
                match_query = {"date": {"$gte": start_date}}
                if end_date:
                    match_query["date"]["$lte"] = end_date

                if employee_id:
                    match_query["employee_id"] = employee_id

                pipeline_status = [
                    {"$match": match_query},
                    {"$group": {"_id": "$status", "count": {"$sum": 1}}},
                ]
                pipeline_detail = [
                    {"$match": match_query},
                    {"$group": {"_id": "$attendance_status", "count": {"$sum": 1}}},
                ]

                status_cursor = await attendance_collection.aggregate(pipeline_status).to_list(length=None)
                detail_cursor = await attendance_collection.aggregate(pipeline_detail).to_list(length=None)

                present_total = 0
                absent = 0
                leave = 0
                holiday = 0

                for doc in status_cursor:
                    sk = str(doc["_id"] or "").lower()
                    count = doc["count"]
                    if sk == "present":
                        present_total = count
                    elif sk == "absent":
                        absent = count
                    elif sk == "leave":
                        leave = count
                    elif sk == "holiday":
                        holiday = count

                on_time = 0
                late = 0
                permission = 0
                half_day = 0

                for doc in detail_cursor:
                    sk = str(doc["_id"] or "").lower()
                    count = doc["count"]
                    if sk == "ontime":
                        on_time = count
                    elif sk == "late":
                        late = count
                    elif sk == "permission":
                        permission = count
                    elif sk == "half day":
                        half_day = count

                return {
                    "total_present": present_total,
                    "absent": absent,
                    "leave": leave,
                    "holiday": holiday,
                    "on_time": on_time,
                    "late": late,
                    "permission": permission,
                    "half_day": half_day,
                }

            today_stats = await aggregate_stats(start_of_today, start_of_today)
            month_stats = await aggregate_stats(start_of_month)
            year_stats = await aggregate_stats(start_of_year)

            return {"today": today_stats, "month": month_stats, "year": year_stats}
        except Exception as e:
            traceback.print_exc()
            return {}

    @staticmethod
    async def get_employee_task_metrics(employee_id: str) -> dict:
        try:
            employee, _ = await EmployeeService.get(employee_id)
            if not employee:
                return {}

            identifiers = [employee.get("id"), employee.get("name"), employee.get("employee_no_id")]
            identifiers = [i for i in identifiers if i]

            query = {
                "assigned_to": {"$in": identifiers},
                "is_deleted": {"$ne": True}
            }
            tasks = await tasks_collection.find(query).to_list(length=None)

            metrics = {
                "total_assigned": len(tasks),
                "completed": 0,
                "in_progress": 0,
                "pending": 0,
                "overdue": 0,
                "completion_rate": 0
            }

            now = datetime.utcnow()
            for task in tasks:
                status = task.get("status", "Todo")
                if status in ["Done", "Completed"]:
                    metrics["completed"] += 1
                elif status == "In Progress":
                    metrics["in_progress"] += 1
                else:
                    metrics["pending"] += 1

                if status not in ["Done", "Completed"] and task.get("end_date"):
                    try:
                        end_date = datetime.strptime(task["end_date"], "%Y-%m-%d")
                        if end_date < now:
                            metrics["overdue"] += 1
                    except Exception:
                        pass

            if metrics["total_assigned"] > 0:
                metrics["completion_rate"] = round((metrics["completed"] / metrics["total_assigned"]) * 100, 2)

            return metrics
        except Exception as e:
            traceback.print_exc()
            return {}

    @staticmethod
    async def get_employee_assigned_projects(employee_id: str) -> List[dict]:
        try:
            employee, _ = await EmployeeService.get(employee_id)
            if not employee:
                return []

            emp_id = str(employee.get("id"))
            query = {
                "is_deleted": {"$ne": True},
                "$or": [
                    {"project_manager_ids": emp_id},
                    {"team_leader_ids": emp_id},
                    {"team_member_ids": emp_id}
                ]
            }

            projects = await projects_collection.find(query).to_list(length=None)
            result = []
            for p in projects:
                p_norm = normalize(p)
                if p_norm.get("client_id") and ObjectId.is_valid(p_norm["client_id"]):
                    client = await clients_collection.find_one({"_id": ObjectId(p_norm["client_id"])})
                    if client:
                        p_norm["client_name"] = client.get("name")
                        p_norm["client_company"] = client.get("company_name")
                result.append(p_norm)

            return result
        except Exception as e:
            traceback.print_exc()
            return []

    @staticmethod
    async def get_assets_by_employee(employee_id: str) -> List[dict]:
        try:
            employee, _ = await EmployeeService.get(employee_id)
            if not employee:
                return []

            assets = await assets_collection.find({"assigned_to": employee_id, "is_deleted": {"$ne": True}}).to_list(length=None)
            categories = await asset_categories_collection.find({"is_deleted": {"$ne": True}}).to_list(length=None)
            cat_map = {str(c["_id"]): normalize(c) for c in categories}

            result = []
            for a in assets:
                a_norm = normalize(a)
                a_norm["category"] = cat_map.get(str(a_norm.get("asset_category_id")))
                a_norm["assigned_to_details"] = employee
                result.append(a_norm)

            return result
        except Exception as e:
            traceback.print_exc()
            return []

    @staticmethod
    async def create(
        employee_in: EmployeeCreate,
        profile_picture_path: Optional[str] = None
    ) -> Tuple[Optional[dict], Optional[str]]:
        try:
            # Check unique email
            existing_user = await users_collection.find_one({
                "is_deleted": {"$ne": True},
                "email": employee_in.email
            })
            if existing_user:
                return None, f"User with email {employee_in.email} already exists"

            existing_emp_id = await users_collection.find_one({
                "is_deleted": {"$ne": True},
                "employee_no_id": employee_in.employee_no_id
            })
            if existing_emp_id:
                return None, f"User with Employee ID {employee_in.employee_no_id} already exists"

            if employee_in.personal_email:
                existing_personal = await employees_collection.find_one({
                    "is_deleted": {"$ne": True},
                    "personal_email": employee_in.personal_email
                })
                if existing_personal:
                    return None, f"User with personal email {employee_in.personal_email} already exists"

            employee_data = employee_in.dict()
            hashed_password = get_password_hash(employee_in.password)

            # Auto-assign Onboarding Checklist if not manually provided
            if not employee_data.get("onboarding_checklist"):
                templates = await checklist_templates_collection.find({"type": "onboarding", "is_deleted": {"$ne": True}}).to_list(length=None)
                checklist = []
                for t in templates:
                    checklist.append({
                        "task_name": t.get("task_name"),
                        "description": t.get("description"),
                        "status": "Pending",
                        "completed_at": None,
                        "task_id": str(t["_id"]),
                    })
                employee_data["onboarding_checklist"] = checklist

            # Transfer NDA Documents if personal_email matches
            if employee_data.get("personal_email"):
                nda_request = await nda_requests_collection.find_one(
                    {"email": employee_data["personal_email"], "status": "Approved", "is_deleted": {"$ne": True}},
                    sort=[("created_at", -1)]
                )
                if nda_request:
                    existing_docs = employee_data.get("documents", [])
                    if "documents" in nda_request and nda_request["documents"]:
                        for doc in nda_request["documents"]:
                            existing_docs.append({
                                "document_name": doc.get("document_name", "NDA Document"),
                                "document_proof": doc.get("document_proof"),
                                "file_type": doc.get("file_type")
                            })
                    if "signed_pdf_path" in nda_request and nda_request["signed_pdf_path"]:
                        pdf_doc = nda_request["signed_pdf_path"]
                        existing_docs.append({
                            "document_name": pdf_doc.get("document_name", "Signed NDA"),
                            "document_proof": pdf_doc.get("document_proof"),
                            "file_type": pdf_doc.get("file_type", "application/pdf")
                        })
                    employee_data["documents"] = existing_docs

            if profile_picture_path:
                employee_data["profile_picture"] = profile_picture_path

            documents_to_save = employee_data.pop("documents", [])
            employee_data["is_deleted"] = False
            employee_data["deleted_at"] = None
            employee_data["created_at"] = datetime.utcnow()

            user_data = {
                "employee_no_id": employee_in.employee_no_id,
                "biometric_id": employee_in.biometric_id,
                "name": employee_in.name,
                "email": employee_in.email,
                "mobile": employee_in.mobile,
                "address": employee_in.address,
                "hashed_password": hashed_password,
                "role": employee_in.role or "employee",
                "is_deleted": False,
                "deleted_at": None,
                "created_at": datetime.utcnow(),
            }

            if "password" in employee_data:
                del employee_data["password"]
            employee_data["hashed_password"] = hashed_password

            emp_result = await employees_collection.insert_one(employee_data)
            employee_id = str(emp_result.inserted_id)

            if documents_to_save:
                for doc in documents_to_save:
                    doc_dict = doc if isinstance(doc, dict) else doc.dict()
                    doc_dict["employee_id"] = employee_id
                    doc_dict["is_deleted"] = False
                    doc_dict["deleted_at"] = None
                    doc_dict["created_at"] = datetime.utcnow()
                    doc_dict["updated_at"] = datetime.utcnow()
                    await employee_documents_collection.insert_one(doc_dict)

            await users_collection.insert_one(user_data)

            return await EmployeeService.get(employee_id)
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def list(
        page: int = 1,
        limit: int = 10,
        search: Optional[str] = None,
        status: Optional[str] = None,
        role: Optional[str] = None,
        work_mode: Optional[str] = None
    ) -> Tuple[Optional[List[dict]], int, Optional[str]]:
        try:
            query = {"is_deleted": {"$ne": True}}
            if status:
                query["status"] = status
            if role:
                query["role"] = role
            if work_mode:
                query["work_mode"] = work_mode

            if search:
                regex_pattern = {"$regex": search, "$options": "i"}
                query["$or"] = [
                    {"name": regex_pattern},
                    {"email": regex_pattern},
                    {"employee_no_id": regex_pattern},
                    {"department": regex_pattern},
                    {"designation": regex_pattern},
                    {"mobile": regex_pattern},
                ]

            skip = (page - 1) * limit
            total_items = await employees_collection.count_documents(query)

            employees_cursor = (
                await employees_collection.find(query)
                .sort("created_at", -1)
                .skip(skip)
                .limit(limit)
                .to_list(length=limit)
            )

            result = []
            for emp in employees_cursor:
                norm_emp = normalize(emp)
                norm_emp.pop("hashed_password", None)
                norm_emp.pop("password", None)
                emp_id = str(emp["_id"])
                docs = await employee_documents_collection.find({"employee_id": emp_id, "is_deleted": {"$ne": True}}).to_list(length=None)
                norm_emp["documents"] = [normalize(d) for d in docs]
                result.append(norm_emp)

            return result, total_items, None
        except Exception as e:
            traceback.print_exc()
            return None, 0, str(e)

    @staticmethod
    async def get_summary() -> Tuple[Optional[List[dict]], Optional[str]]:
        try:
            projection = {
                "employee_no_id": 1,
                "profile_picture": 1,
                "name": 1,
                "email": 1,
                "status": 1,
                "biometric_id": 1,
                "weekly_off": 1,
                "marital_status": 1,
                "designation": 1,
                "department": 1,
                "employee_type": 1,
                "mobile": 1,
                "gender": 1,
                "work_mode": 1,
                "date_of_joining": 1,
                "lop_rule_01": 1,
            }
            employees = await employees_collection.find({"is_deleted": {"$ne": True}}, projection).to_list(length=None)
            return [normalize(emp) for emp in employees], None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def get(employee_id: str) -> Tuple[Optional[dict], Optional[str]]:
        try:
            if not ObjectId.is_valid(employee_id):
                return None, "Invalid employee ID"

            employee = await employees_collection.find_one({
                "_id": ObjectId(employee_id),
                "is_deleted": {"$ne": True}
            })
            if not employee:
                return None, "Employee not found"

            norm_emp = normalize(employee)
            norm_emp.pop("hashed_password", None)
            norm_emp.pop("password", None)

            docs = await employee_documents_collection.find({"employee_id": employee_id, "is_deleted": {"$ne": True}}).to_list(length=None)
            norm_emp["documents"] = [normalize(d) for d in docs]

            return norm_emp, None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def get_summary_details(employee_id: str) -> Tuple[Optional[dict], Optional[str]]:
        try:
            employee, err = await EmployeeService.get(employee_id)
            if err or not employee:
                return None, err or "Employee not found"

            leave_summary = await LeaveRequestService.get_employee_leave_balances(employee_id)
            task_metrics = await EmployeeService.get_employee_task_metrics(employee_id)
            attendance_stats = await EmployeeService.get_dashboard_metrics(employee_id=employee_id)
            assigned_projects = await EmployeeService.get_employee_assigned_projects(employee_id)
            assigned_assets = await EmployeeService.get_assets_by_employee(employee_id)

            summary_data = {
                "employee": employee,
                "leave_summary": leave_summary,
                "task_metrics": task_metrics,
                "attendance_stats": attendance_stats,
                "assigned_projects": assigned_projects,
                "assigned_assets": assigned_assets
            }
            return summary_data, None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def update(
        employee_id: str,
        employee_in: EmployeeUpdate,
        profile_picture_path: Optional[str] = None
    ) -> Tuple[Optional[dict], Optional[str]]:
        try:
            if not ObjectId.is_valid(employee_id):
                return None, "Invalid employee ID"

            current_emp = await employees_collection.find_one({"_id": ObjectId(employee_id), "is_deleted": {"$ne": True}})
            if not current_emp:
                return None, "Employee not found"

            update_data = {k: v for k, v in employee_in.dict().items() if v is not None}
            if profile_picture_path:
                update_data["profile_picture"] = profile_picture_path

            if "email" in update_data and update_data["email"] and update_data["email"] != current_emp.get("email"):
                existing_email = await users_collection.find_one({
                    "is_deleted": {"$ne": True},
                    "email": update_data["email"]
                })
                if existing_email:
                    return None, f"User with email {update_data['email']} already exists"

            if "employee_no_id" in update_data and update_data["employee_no_id"] and update_data["employee_no_id"] != current_emp.get("employee_no_id"):
                existing_id = await users_collection.find_one({
                    "is_deleted": {"$ne": True},
                    "employee_no_id": update_data["employee_no_id"]
                })
                if existing_id:
                    return None, f"User with Employee ID {update_data['employee_no_id']} already exists"

            if "personal_email" in update_data and update_data["personal_email"]:
                existing_personal = await employees_collection.find_one({
                    "is_deleted": {"$ne": True},
                    "personal_email": update_data["personal_email"],
                    "_id": {"$ne": ObjectId(employee_id)}
                })
                if existing_personal:
                    return None, f"User with personal email {update_data['personal_email']} already exists"

            if "documents" in update_data and update_data["documents"]:
                update_data["documents"] = [
                    doc if isinstance(doc, dict) else doc.dict()
                    for doc in update_data["documents"]
                ]

            documents_to_sync = update_data.pop("documents", None)

            if update_data:
                update_data["updated_at"] = datetime.utcnow()
                await employees_collection.update_one(
                    {"_id": ObjectId(employee_id)}, {"$set": update_data}
                )

            if documents_to_sync is not None:
                current_docs = await employee_documents_collection.find({"employee_id": employee_id, "is_deleted": {"$ne": True}}).to_list(length=None)
                current_proofs = {d.get("document_proof") for d in current_docs}

                for doc in documents_to_sync:
                    doc_dict = doc if isinstance(doc, dict) else doc.dict()
                    if doc_dict.get("document_proof") not in current_proofs:
                        doc_dict["employee_id"] = employee_id
                        doc_dict["is_deleted"] = False
                        doc_dict["deleted_at"] = None
                        doc_dict["created_at"] = datetime.utcnow()
                        doc_dict["updated_at"] = datetime.utcnow()
                        await employee_documents_collection.insert_one(doc_dict)
                    else:
                        await employee_documents_collection.update_one(
                            {"employee_id": employee_id, "document_proof": doc_dict["document_proof"]},
                            {"$set": {
                                "document_name": doc_dict.get("document_name"),
                                "file_type": doc_dict.get("file_type"),
                                "updated_at": datetime.utcnow()
                            }}
                        )

            # Sync user update
            user_update = {}
            for field in ["email", "name", "mobile", "address", "role", "biometric_id", "employee_no_id"]:
                if field in update_data:
                    user_update[field] = update_data[field]

            if user_update and "email" in current_emp:
                await users_collection.update_one(
                    {"email": current_emp["email"]},
                    {"$set": user_update}
                )

            return await EmployeeService.get(employee_id)
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def delete(employee_id: str) -> Tuple[bool, Optional[str]]:
        try:
            if not ObjectId.is_valid(employee_id):
                return False, "Invalid employee ID"

            employee = await employees_collection.find_one({"_id": ObjectId(employee_id), "is_deleted": {"$ne": True}})
            if not employee:
                return False, "Employee not found"

            deleted_at = datetime.utcnow()
            result = await employees_collection.update_one(
                {"_id": ObjectId(employee_id)},
                {"$set": {"is_deleted": True, "deleted_at": deleted_at}}
            )

            if result.modified_count > 0:
                await employee_documents_collection.update_many(
                    {"employee_id": employee_id},
                    {"$set": {"is_deleted": True, "deleted_at": deleted_at}}
                )

                if "employee_no_id" in employee:
                    await users_collection.update_one(
                        {"employee_no_id": employee["employee_no_id"]},
                        {"$set": {"is_deleted": True, "deleted_at": deleted_at}}
                    )

            return True, None
        except Exception as e:
            traceback.print_exc()
            return False, str(e)

    @staticmethod
    async def update_user_permissions(employee_id: str, permissions: List[str]) -> Tuple[bool, Optional[str]]:
        try:
            if not ObjectId.is_valid(employee_id):
                return False, "Invalid employee ID"

            employee = await employees_collection.find_one({"_id": ObjectId(employee_id), "is_deleted": {"$ne": True}})
            if not employee:
                return False, "Employee not found"

            emp_no_id = employee.get("employee_no_id")
            result = await users_collection.update_one(
                {"employee_no_id": emp_no_id, "is_deleted": {"$ne": True}},
                {"$set": {"permissions": permissions, "updated_at": datetime.utcnow()}},
            )
            if result.matched_count == 0:
                return False, "User not found for this employee ID"

            return True, None
        except Exception as e:
            traceback.print_exc()
            return False, str(e)

    @staticmethod
    async def get_user_permissions(employee_id: str) -> Tuple[Optional[dict], Optional[str]]:
        try:
            if not ObjectId.is_valid(employee_id):
                return None, "Invalid employee ID"

            employee = await employees_collection.find_one({"_id": ObjectId(employee_id), "is_deleted": {"$ne": True}})
            if not employee:
                return None, "Employee not found"

            emp_no_id = employee.get("employee_no_id")
            user = await users_collection.find_one({"employee_no_id": emp_no_id, "is_deleted": {"$ne": True}})
            if not user:
                return None, "User not found for this employee"

            direct_permissions = user.get("permissions", [])
            role_permissions = []
            role_name = user.get("role")
            if role_name:
                role = await roles_collection.find_one({"name": role_name, "is_deleted": {"$ne": True}})
                if role and "permissions" in role:
                    role_permissions = [str(pid) for pid in role["permissions"]]

            return {
                "id": employee_id,
                "role_permissions": role_permissions,
                "direct_permissions": direct_permissions
            }, None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)

    @staticmethod
    async def delete_employee_document(doc_id: str) -> Tuple[bool, Optional[str]]:
        try:
            if not ObjectId.is_valid(doc_id):
                return False, "Invalid document ID"

            result = await employee_documents_collection.update_one(
                {"_id": ObjectId(doc_id), "is_deleted": {"$ne": True}},
                {"$set": {"is_deleted": True, "deleted_at": datetime.utcnow()}}
            )
            if result.matched_count == 0:
                return False, "Document not found"

            return True, None
        except Exception as e:
            traceback.print_exc()
            return False, str(e)
