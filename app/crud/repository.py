from app.database import db
from app.models import (
    DepartmentCreate,
    DepartmentUpdate,
    EmployeeCreate,
    EmployeeUpdate,
    ShiftCreate,
    ShiftUpdate,
    ExpenseCategoryCreate,
    ExpenseCategoryUpdate,
    ExpenseCreate,
    ExpenseUpdate,
    DocumentCategoryCreate,
    DocumentCategoryUpdate,
    DocumentCreate,
    DocumentUpdate,
    ClientCreate,
    ClientUpdate,
    ProjectCreate,
    ProjectUpdate,
    HolidayCreate,
    HolidayUpdate,
    AssetCategoryCreate,
    AssetCategoryUpdate,
    AssetCreate,
    AssetUpdate,
    BlogCreate,
    BlogUpdate,
    LeaveTypeCreate,
    LeaveTypeUpdate,
    LeaveRequestCreate,
    LeaveRequestUpdate,
    TaskCreate,
    TaskUpdate,
    EODReportItem,
    AttendanceCreate,
    AttendanceUpdate,
    AttendanceAdminEdit,
    EmployeeChecklistTemplateCreate,
    EmployeeChecklistTemplateUpdate,
    BiometricLogItem,
    SystemConfigurationCreate,
    SystemConfigurationUpdate,
    NDARequestCreate,
    NDARequestUpdate,
    PayslipCreate,
    PayslipComponentCreate,
    PayslipComponentUpdate,
    FeedbackCreate,
    FeedbackUpdate,
    MilestoneRoadmapCreate,
    MilestoneRoadmapUpdate,
)
from app.utils import normalize, get_password_hash, get_employee_basic_details
from bson import ObjectId
from datetime import datetime, timedelta
from typing import List, Optional
import asyncio
from app.services.vector_store import vector_store_service


class Repository:
    """
    Repository class for all CRUD operations.
    """

    def __init__(self):
        self.db = db
        self.departments = self.db["departments"]
        self.shifts = self.db["shifts"]
        self.employees = self.db["employees"]
        self.users = self.db["users"]
        self.expense_categories = self.db["expense_categories"]
        self.expenses = self.db["expenses"]
        self.document_categories = self.db["document_categories"]
        self.documents = self.db["documents"]
        self.clients = self.db["clients"]
        self.projects = self.db["projects"]
        self.holidays = self.db["holidays"]
        self.asset_categories = self.db["asset_categories"]
        self.assets = self.db["assets"]
        self.blogs = self.db["blogs"]
        self.leave_types = self.db["leave_types"]
        self.leave_requests = self.db["leave_requests"]

        self.tasks = self.db["tasks"]
        self.attendance = self.db["attendance"]
        self.system_configurations = self.db["system_configurations"]
        self.nda_requests = self.db["nda_requests"]
        self.payslips = self.db["payslips"]
        self.payslip_components = self.db["payslip_components"]
        self.milestones_roadmaps = self.db["milestones_roadmaps"]

    async def create_employee(
        self, employee: EmployeeCreate, profile_picture_path: str = None
    ) -> dict:
        try:
            # Check if user already exists
            existing_user = await self.users.find_one(
                {
                    "$or": [
                        {"email": employee.email},
                        {"employee_id": employee.employee_no_id},
                    ]
                }
            )
            if existing_user:
                raise ValueError("User with this email or Employee ID already exists")

            if employee.personal_email:
                existing_personal = await self.employees.find_one({"personal_email": employee.personal_email})
                if existing_personal:
                    raise ValueError(f"User with personal email {employee.personal_email} already exists")

            # Prepare Employee Data
            employee_data = employee.dict()
            hashed_password = get_password_hash(employee.password)
            employee_data["password"] = hashed_password

            # Auto-populate Onboarding Checklist
            if not employee_data.get("onboarding_checklist"):
                default_templates = (
                    await self.db["checklist_templates"]
                    .find({"type": "Onboarding", "is_default": True})
                    .to_list(length=None)
                )
                checklist = []
                for t in default_templates:
                    checklist.append(
                        {
                            "name": t["name"],
                            "status": "Pending",
                            "completed_at": None,
                            "task_id": str(t["_id"]),  # Link back to template if useful
                        }
                    )
                employee_data["onboarding_checklist"] = checklist

            # Transfer NDA Documents if personal_email matches
            if employee_data.get("personal_email"):
                nda_request = await self.nda_requests.find_one(
                    {"email": employee_data["personal_email"], "status": "Signed"},
                    sort=[("created_at", -1)] # Get the latest one if multiple
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

            if "documents" in employee_data and employee_data["documents"]:
                employee_data["documents"] = [
                    doc if isinstance(doc, dict) else doc.dict()
                    for doc in employee_data["documents"]
                ]

            employee_data["created_at"] = datetime.utcnow()

            # Create User Entry
            # User fields: employee_no_id, biometric_id, name, email, mobile, hashed_password
            user_data = {
                "employee_no_id": employee.employee_no_id,
                "biometric_id": employee.biometric_id,  # Default to biometric_id
                "name": employee.name,
                "email": employee.email,
                "mobile": employee.mobile,
                "address": employee.address,
                "hashed_password": hashed_password,
                "role": employee.role or "employee",
                "created_at": datetime.utcnow(),
            }

            # Insert Employee
            # Remove plain password from storage if we only want hashed
            if "password" in employee_data:
                del employee_data["password"]  # Remove plain text
            employee_data["hashed_password"] = hashed_password

            emp_result = await self.employees.insert_one(employee_data)
            employee_data["id"] = str(emp_result.inserted_id)

            # Insert User
            await self.users.insert_one(user_data)

            return normalize(employee_data)
        except Exception as e:
            raise e

    async def get_employees(
        self,
        page: int = 1,
        limit: int = 10,
        search: Optional[str] = None,
        status: Optional[str] = None,
        role: Optional[str] = None,
        work_mode: Optional[str] = None,
    ) -> (List[dict], int):
        try:
            query = {}

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
                    {"first_name": regex_pattern},
                    {"last_name": regex_pattern},
                    {"mobile": regex_pattern},
                ]

            skip = (page - 1) * limit
            total_items = await self.employees.count_documents(query)

            employees = (
                await self.employees.find(query)
                .skip(skip)
                .limit(limit)
                .to_list(length=limit)
            )

            # Remove sensitive data like password
            for emp in employees:
                if "hashed_password" in emp:
                    del emp["hashed_password"]
                if "password" in emp:
                    del emp["password"]

            return [normalize(emp) for emp in employees], total_items
        except Exception as e:
            raise e

    async def get_all_employees_summary(self) -> List[dict]:
        try:
            # Projection to fetch only necessary fields
            projection = {
                "employee_no_id": 1,
                "profile_picture": 1,
                "name": 1,
                "email": 1,
                "status": 1,
                "biometric_id": 1,
            }
            employees = await self.employees.find({}, projection).to_list(length=None)

            return [normalize(emp) for emp in employees]
        except Exception as e:
            raise e

    async def get_employee(self, employee_id: str) -> dict:
        try:
            employee = await self.employees.find_one({"_id": ObjectId(employee_id)})
            if employee and "hashed_password" in employee:
                del employee["hashed_password"]
            return normalize(employee)
        except Exception as e:
            raise e

    async def get_employee_basic_details(self, employee_id: str) -> dict:
        """Returns a lightweight employee profile for embedding in other resources."""
        try:
            employee = await self.employees.find_one({"_id": ObjectId(employee_id)})
            if not employee:
                return None
            return {
                "id": str(employee["_id"]),
                "name": employee.get("name", ""),
                "profile_picture": employee.get("profile_picture"),
                "designation": employee.get("designation"),
                "department": employee.get("department"),
                "employee_no_id": employee.get("employee_no_id"),
                "email": employee.get("email"),
            }
        except Exception:
            return None

    async def get_employee_leave_balances(self, employee_id: str) -> dict:
        try:
            employee = await self.get_employee(employee_id)
            if not employee:
                return None

            leave_types = await self.leave_types.find().to_list(length=None)
            query = {
                "employee_id": employee.get("employee_no_id") or employee.get("id"),
                "status": {"$in": ["Approved", "Pending"]}
            }
            leave_requests = await self.leave_requests.find(query).to_list(length=None)

            balance_summary = {
                "total_allocated": 0,
                "used": 0,
                "available": 0,
                "pending_approval": 0,
                "breakdown": []
            }

            for lt in leave_types:
                allocated = float(lt.get("days_allowed", 0))
                type_id = str(lt["_id"])
                
                used_count = 0.0
                pending_count = 0.0
                
                for lr in leave_requests:
                    if str(lr.get("leave_type_id")) == type_id:
                        days = float(lr.get("total_days", 0))
                        if lr.get("status") == "Approved":
                            used_count += days
                        elif lr.get("status") == "Pending":
                            pending_count += days
                
                balance_summary["breakdown"].append({
                    "type": lt.get("type_name"),
                    "allocated": allocated,
                    "used": used_count,
                    "pending": pending_count,
                    "available": max(0, allocated - used_count)
                })

                balance_summary["total_allocated"] += allocated
                balance_summary["used"] += used_count
                balance_summary["pending_approval"] += pending_count
                balance_summary["available"] += max(0, allocated - used_count)

            return balance_summary
        except Exception as e:
            print(f"Error in get_employee_leave_balances: {e}")
            return {"total_allocated": 0, "used": 0, "available": 0, "pending_approval": 0, "breakdown": []}

    async def get_employee_task_metrics(self, employee_id: str) -> dict:
        try:
            employee = await self.get_employee(employee_id)
            if not employee:
                return {}

            identifiers = [employee.get("id"), employee.get("name"), employee.get("employee_no_id")]
            identifiers = [i for i in identifiers if i]  

            query = {
                "assigned_to": {"$in": identifiers}
            }
            tasks = await self.tasks.find(query).to_list(length=None)

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
                if status == "Done" or status == "Completed":
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
                    except:
                        pass

            if metrics["total_assigned"] > 0:
                metrics["completion_rate"] = round((metrics["completed"] / metrics["total_assigned"]) * 100, 2)

            return metrics
        except Exception as e:
             print(f"Error in get_employee_task_metrics: {e}")
             return {}


    async def get_employee_attendance_stats(self, employee_id: str) -> dict:
        try:
            employee = await self.get_employee(employee_id)
            if not employee:
                return {}
            
            identifier = employee.get("id")
            return await self.get_dashboard_metrics(employee_id=identifier)
            
        except Exception as e:
            print(f"Error in get_employee_attendance_stats: {e}")
            return {}

    async def get_employee_assigned_projects(self, employee_id: str) -> List[dict]:
        try:
            employee = await self.get_employee(employee_id)
            if not employee:
                return []
             
            emp_id = str(employee.get("id"))
            
            query = {
                "$or": [
                    {"project_manager_ids": emp_id},
                    {"team_leader_ids": emp_id},
                    {"team_member_ids": emp_id}
                ]
            }
            
            projects = await self.projects.find(query).to_list(length=None)
            
            result = []
            for p in projects:
                p_norm = normalize(p)
                if p_norm.get("client_id"):
                    client = await self.clients.find_one({"_id": ObjectId(p_norm["client_id"])})
                    if client:
                        p_norm["client_name"] = client.get("name")
                        p_norm["client_company"] = client.get("company_name")
                result.append(p_norm)
                
            return result
        except Exception as e:
            print(f"Error in get_employee_assigned_projects: {e}")
            return []

    async def update_employee(
        self,
        employee_id: str,
        employee: EmployeeUpdate,
        profile_picture_path: str = None,
    ) -> dict:
        try:
            update_data = {k: v for k, v in employee.dict().items() if v is not None}
            if profile_picture_path:
                update_data["profile_picture"] = profile_picture_path

            if "personal_email" in update_data and update_data["personal_email"]:
                existing_personal = await self.employees.find_one(
                    {"personal_email": update_data["personal_email"], "_id": {"$ne": ObjectId(employee_id)}}
                )
                if existing_personal:
                    raise ValueError(f"User with personal email {update_data['personal_email']} already exists")

            if "documents" in update_data and update_data["documents"]:
                update_data["documents"] = [
                    doc if isinstance(doc, dict) else doc.dict()
                    for doc in update_data["documents"]
                ]

            # Transfer NDA Documents if personal_email (or email acting as personal) is updated
            # User specifically asked for this on creation, but updating is also a valid workflow
            email_key = "personal_email" if "personal_email" in update_data else None
            
            if email_key and update_data[email_key]:
                nda_request = await self.nda_requests.find_one(
                    {"email": update_data[email_key], "status": "Signed"},
                    sort=[("created_at", -1)]
                )
                
                if nda_request:
                    # Get existing documents if not already in update_data
                    if "documents" not in update_data:
                        current_emp = await self.employees.find_one({"_id": ObjectId(employee_id)})
                        existing_docs = current_emp.get("documents", []) if current_emp else []
                    else:
                        existing_docs = update_data["documents"]

                    existing_proofs = {d.get("document_proof") for d in existing_docs}

                    # Append NDA documents
                    if "documents" in nda_request and nda_request["documents"]:
                        for doc in nda_request["documents"]:
                            if doc.get("document_proof") not in existing_proofs:
                                existing_docs.append({
                                    "document_name": doc.get("document_name", "NDA Document"),
                                    "document_proof": doc.get("document_proof"),
                                    "file_type": doc.get("file_type")
                                })
                                existing_proofs.add(doc.get("document_proof"))
                            
                    if "signed_pdf_path" in nda_request and nda_request["signed_pdf_path"]:
                        pdf_doc = nda_request["signed_pdf_path"]
                        if pdf_doc.get("document_proof") not in existing_proofs:
                            existing_docs.append({
                                "document_name": pdf_doc.get("document_name", "Signed NDA"),
                                "document_proof": pdf_doc.get("document_proof"),
                                "file_type": pdf_doc.get("file_type", "application/pdf")
                            })
                            existing_proofs.add(pdf_doc.get("document_proof"))
                    
                    update_data["documents"] = existing_docs

            if update_data:
                update_data["updated_at"] = datetime.utcnow()
                await self.employees.update_one(
                    {"_id": ObjectId(employee_id)}, {"$set": update_data}
                )

                # Also update User if critical fields changed (email, name, mobile)
                user_update = {}
                if "email" in update_data:
                    user_update["email"] = update_data["email"]
                if "name" in update_data:
                    user_update["name"] = update_data["name"]
                if "mobile" in update_data:
                    user_update["mobile"] = update_data["mobile"]
                if "address" in update_data:
                    user_update["address"] = update_data["address"]
                if "role" in update_data:
                    user_update["role"] = update_data["role"]

                if user_update:
                    # Find user by employee_id link
                    current_emp = await self.get_employee(employee_id)
                    if current_emp and "employee_no_id" in current_emp:
                        await self.users.update_one(
                            {"employee_no_id": current_emp["employee_no_id"]},
                            {"$set": user_update},
                        )

            return await self.get_employee(employee_id)
        except Exception as e:
            raise e

    async def delete_employee(self, employee_id: str) -> bool:
        try:
            # Get employee to find associated user
            employee = await self.employees.find_one({"_id": ObjectId(employee_id)})

            result = await self.employees.delete_one({"_id": ObjectId(employee_id)})

            if result.deleted_count > 0 and employee:
                # Delete User too? "if i create a employee it will also store in the user table" -> implication is strict 1:1 sync.
                # I will soft delete or delete user. Let's delete for now to keep it clean CRUD.
                if "employee_no_id" in employee:
                    await self.users.delete_one(
                        {"employee_no_id": employee["employee_no_id"]}
                    )

            return result.deleted_count > 0
        except Exception as e:
            raise e

    async def update_user_permissions(
        self, employee_id: str, permissions: List[str]
    ) -> bool:
        try:
            # 1. Find Employee by _id (Primary ID)
            employee = await self.employees.find_one({"_id": ObjectId(employee_id)})
            if not employee:
                return False

            # 2. Get the business key (employee_no_id) used in User table
            emp_no_id = employee.get("employee_no_id")

            # 3. Update User
            result = await self.users.update_one(
                {"employee_no_id": emp_no_id},
                {"$set": {"permissions": permissions, "updated_at": datetime.utcnow()}},
            )
            return result.matched_count > 0
        except Exception as e:
            raise e

    async def get_user_permissions(self, employee_id: str) -> dict:
        try:
            # 1. Find Employee by _id (Primary ID)
            employee = await self.employees.find_one({"_id": ObjectId(employee_id)})
            if not employee:
                return {"role_permissions": [], "direct_permissions": []}

            # 2. Get the business key
            emp_no_id = employee.get("employee_no_id")

            user = await self.users.find_one({"employee_no_id": emp_no_id})
            if not user:
                return {"role_permissions": [], "direct_permissions": []}

            # 3. Get Direct Permissions (already slugs)
            direct_permissions = user.get("permissions", [])

            # 4. Get Role Permissions (IDs)
            role_permissions = []
            role_name = user.get("role")
            if role_name:
                role = await self.db["roles"].find_one({"name": role_name})
                if role and "permissions" in role:
                    # Role permissions are stored as list of IDs (strings or objects)
                    role_permissions = [str(pid) for pid in role["permissions"]]

            return {
                "role_permissions": role_permissions,
                "direct_permissions": direct_permissions,  # Already IDs
            }
        except Exception as e:
            raise e

    async def create_department(self, department: DepartmentCreate) -> dict:
        try:
            department_data = department.dict()
            department_data["created_at"] = datetime.utcnow()
            result = await self.departments.insert_one(department_data)
            department_data["id"] = str(result.inserted_id)
            return normalize(department_data)
        except Exception as e:
            raise e

    async def get_departments(self) -> List[dict]:
        try:
            departments = await self.departments.find().to_list(length=None)
            return [normalize(dept) for dept in departments]
        except Exception as e:
            raise e

    async def get_department(self, department_id: str) -> dict:
        try:
            department = await self.departments.find_one(
                {"_id": ObjectId(department_id)}
            )
            return normalize(department)
        except Exception as e:
            raise e

    async def update_department(
        self, department_id: str, department: DepartmentUpdate
    ) -> dict:
        try:
            update_data = {k: v for k, v in department.dict().items() if v is not None}
            if update_data:
                update_data["updated_at"] = datetime.utcnow()
                await self.departments.update_one(
                    {"_id": ObjectId(department_id)}, {"$set": update_data}
                )
            return await self.get_department(department_id)
        except Exception as e:
            raise e

    async def delete_department(self, department_id: str) -> bool:
        try:
            result = await self.departments.delete_one({"_id": ObjectId(department_id)})
            return result.deleted_count > 0
        except Exception as e:
            raise e

    # Shift CRUD
    async def create_shift(self, shift: ShiftCreate) -> dict:
        try:
            shift_data = shift.dict()
            shift_data["created_at"] = datetime.utcnow()
            result = await self.shifts.insert_one(shift_data)
            shift_data["id"] = str(result.inserted_id)
            return normalize(shift_data)
        except Exception as e:
            raise e

    async def get_shifts(self) -> List[dict]:
        try:
            shifts = await self.shifts.find().to_list(length=None)
            return [normalize(s) for s in shifts]
        except Exception as e:
            raise e

    async def get_shift(self, shift_id: str) -> dict:
        try:
            shift = await self.shifts.find_one({"_id": ObjectId(shift_id)})
            return normalize(shift)
        except Exception as e:
            raise e

    async def update_shift(self, shift_id: str, shift: ShiftUpdate) -> dict:
        try:
            update_data = {k: v for k, v in shift.dict().items() if v is not None}
            if update_data:
                update_data["updated_at"] = datetime.utcnow()
                await self.shifts.update_one(
                    {"_id": ObjectId(shift_id)}, {"$set": update_data}
                )
            return await self.get_shift(shift_id)
        except Exception as e:
            raise e

    async def delete_shift(self, shift_id: str) -> bool:
        try:
            result = await self.shifts.delete_one({"_id": ObjectId(shift_id)})
            return result.deleted_count > 0
        except Exception as e:
            raise e

    async def create_expense_category(self, category: ExpenseCategoryCreate) -> dict:
        try:
            category_data = category.dict()
            category_data["created_at"] = datetime.utcnow()
            result = await self.expense_categories.insert_one(category_data)
            category_data["id"] = str(result.inserted_id)
            return normalize(category_data)
        except Exception as e:
            raise e

    async def get_expense_categories(self) -> List[dict]:
        try:
            categories = await self.expense_categories.find().to_list(length=None)
            return [normalize(cat) for cat in categories]
        except Exception as e:
            raise e

    async def get_expense_category(self, category_id: str) -> dict:
        try:
            category = await self.expense_categories.find_one(
                {"_id": ObjectId(category_id)}
            )
            return normalize(category)
        except Exception as e:
            raise e

    async def update_expense_category(
        self, category_id: str, category: ExpenseCategoryUpdate
    ) -> dict:
        try:
            update_data = {k: v for k, v in category.dict().items() if v is not None}
            if update_data:
                update_data["updated_at"] = datetime.utcnow()
                await self.expense_categories.update_one(
                    {"_id": ObjectId(category_id)}, {"$set": update_data}
                )
            return await self.get_expense_category(category_id)
        except Exception as e:
            raise e

    async def delete_expense_category(self, category_id: str) -> bool:
        try:
            result = await self.expense_categories.delete_one(
                {"_id": ObjectId(category_id)}
            )
            return result.deleted_count > 0
        except Exception as e:
            raise e

    async def create_expense(
        self, expense: ExpenseCreate, attachment_path: str = None
    ) -> dict:
        try:
            expense_data = expense.dict()
            if attachment_path:
                expense_data["attachment"] = attachment_path

            expense_data["created_at"] = datetime.utcnow()
            result = await self.expenses.insert_one(expense_data)
            expense_data["id"] = str(result.inserted_id)
            return await self.get_expense(expense_data["id"])
        except Exception as e:
            raise e

    async def get_expenses(self) -> List[dict]:
        try:
            expenses = await self.expenses.find().to_list(length=None)
            categories = await self.expense_categories.find().to_list(length=None)
            category_map = {str(cat["_id"]): cat["name"] for cat in categories}

            result = []
            for exp in expenses:
                exp_norm = normalize(exp)
                exp_norm["category_name"] = category_map.get(
                    exp_norm.get("expense_category_id"), "Unknown"
                )
                exp_norm["subcategory_name"] = category_map.get(
                    exp_norm.get("expense_subcategory_id")
                )
                result.append(exp_norm)
            return result
        except Exception as e:
            raise e

    async def get_expense(self, expense_id: str) -> dict:
        try:
            expense = await self.expenses.find_one({"_id": ObjectId(expense_id)})
            if not expense:
                return None

            exp_norm = normalize(expense)

            # Fetch category names
            if exp_norm.get("expense_category_id"):
                cat = await self.expense_categories.find_one(
                    {"_id": ObjectId(exp_norm["expense_category_id"])}
                )
                exp_norm["category_name"] = cat["name"] if cat else "Unknown"

            if exp_norm.get("expense_subcategory_id"):
                subcat = await self.expense_categories.find_one(
                    {"_id": ObjectId(exp_norm["expense_subcategory_id"])}
                )
                exp_norm["subcategory_name"] = subcat["name"] if subcat else None

            return exp_norm
        except Exception as e:
            raise e

    async def update_expense(
        self, expense_id: str, expense: ExpenseUpdate, attachment_path: str = None
    ) -> dict:
        try:
            update_data = {k: v for k, v in expense.dict().items() if v is not None}
            if attachment_path:
                update_data["attachment"] = attachment_path

            if update_data:
                update_data["updated_at"] = datetime.utcnow()
                await self.expenses.update_one(
                    {"_id": ObjectId(expense_id)}, {"$set": update_data}
                )
            return await self.get_expense(expense_id)
        except Exception as e:
            raise e

    async def delete_expense(self, expense_id: str) -> bool:
        try:
            result = await self.expenses.delete_one({"_id": ObjectId(expense_id)})
            return result.deleted_count > 0
        except Exception as e:
            raise e

    # Document Category CRUD
    async def create_document_category(self, category: DocumentCategoryCreate) -> dict:
        try:
            category_data = category.dict()
            category_data["created_at"] = datetime.utcnow()
            result = await self.document_categories.insert_one(category_data)
            category_data["id"] = str(result.inserted_id)
            return normalize(category_data)
        except Exception as e:
            raise e

    async def get_document_categories(self) -> List[dict]:
        try:
            categories = await self.document_categories.find().to_list(length=None)
            return [normalize(cat) for cat in categories]
        except Exception as e:
            raise e

    async def get_document_category(self, category_id: str) -> dict:
        try:
            category = await self.document_categories.find_one(
                {"_id": ObjectId(category_id)}
            )
            return normalize(category)
        except Exception as e:
            raise e

    async def update_document_category(
        self, category_id: str, category: DocumentCategoryUpdate
    ) -> dict:
        try:
            update_data = {k: v for k, v in category.dict().items() if v is not None}
            if update_data:
                update_data["updated_at"] = datetime.utcnow()
                await self.document_categories.update_one(
                    {"_id": ObjectId(category_id)}, {"$set": update_data}
                )
            return await self.get_document_category(category_id)
        except Exception as e:
            raise e

    async def delete_document_category(self, category_id: str) -> bool:
        try:
            result = await self.document_categories.delete_one(
                {"_id": ObjectId(category_id)}
            )
            return result.deleted_count > 0
        except Exception as e:
            raise e

    # Document CRUD
    async def create_document(
        self, document: DocumentCreate, file_path: str = None
    ) -> dict:
        try:
            document_data = document.dict()
            if file_path:
                document_data["file_path"] = file_path

            document_data["created_at"] = datetime.utcnow()
            result = await self.documents.insert_one(document_data)
            document_data["id"] = str(result.inserted_id)
            
            # Index document in vector store for AI analysis
            if file_path:
                asyncio.create_task(
                    vector_store_service.index_document(
                        file_url=file_path,
                        metadata={
                            "document_id": document_data["id"],
                            "name": document_data["name"],
                            "category_id": document_data.get("document_category_id"),
                        },
                        file_type=document_data.get("file_type")
                    )
                )

            return normalize(document_data)
        except Exception as e:
            raise e

    async def get_documents(self, status: str = None, search: str = None) -> List[dict]:
        try:
            query = {}
            if status:
                query["status"] = status
            if search:
                query["name"] = {"$regex": search, "$options": "i"}
            documents = await self.documents.find(query).to_list(length=None)
            return [normalize(doc) for doc in documents]
        except Exception as e:
            raise e

    async def get_document(self, document_id: str) -> dict:
        try:
            document = await self.documents.find_one({"_id": ObjectId(document_id)})
            return normalize(document)
        except Exception as e:
            raise e

    async def update_document(
        self, document_id: str, document: DocumentUpdate, file_path: str = None
    ) -> dict:
        try:
            update_data = {k: v for k, v in document.dict().items() if v is not None}
            if file_path:
                update_data["file_path"] = file_path

            if update_data:
                update_data["updated_at"] = datetime.utcnow()
                await self.documents.update_one(
                    {"_id": ObjectId(document_id)}, {"$set": update_data}
                )
                
                # Re-index if file changed
                if file_path:
                    # Clean up old vectors first
                    asyncio.create_task(vector_store_service.delete_document(document_id))
                    # Index new content
                    asyncio.create_task(
                        vector_store_service.index_document(
                            file_url=file_path,
                            metadata={
                                "document_id": document_id,
                                "name": update_data.get("name") or document.name,
                                "category_id": update_data.get("document_category_id") or document.document_category_id,
                            },
                            file_type=update_data.get("file_type") or document.file_type
                        )
                    )
            return await self.get_document(document_id)
        except Exception as e:
            raise e

    async def update_document_status(self, document_id: str, status: str) -> dict:
        try:
            await self.documents.update_one(
                {"_id": ObjectId(document_id)},
                {"$set": {"status": status, "updated_at": datetime.utcnow()}}
            )
            return await self.get_document(document_id)
        except Exception as e:
            raise e

    async def delete_document(self, document_id: str) -> bool:
        try:
            result = await self.documents.delete_one({"_id": ObjectId(document_id)})
            
            if result.deleted_count > 0:
                # Clean up vectors
                asyncio.create_task(vector_store_service.delete_document(document_id))
                
            return result.deleted_count > 0
        except Exception as e:
            raise e

    # Client CRUD
    async def create_client(self, client: ClientCreate, logo_path: str = None) -> dict:
        try:
            client_data = client.dict()
            if logo_path:
                client_data["logo"] = logo_path

            client_data["created_at"] = datetime.utcnow()
            result = await self.clients.insert_one(client_data)
            client_data["id"] = str(result.inserted_id)
            return normalize(client_data)
        except Exception as e:
            raise e

    async def get_clients(self) -> List[dict]:
        try:
            clients = await self.clients.find().to_list(length=None)
            return [normalize(c) for c in clients]
        except Exception as e:
            raise e

    async def get_client(self, client_id: str) -> dict:
        try:
            client = await self.clients.find_one({"_id": ObjectId(client_id)})
            return normalize(client)
        except Exception as e:
            raise e

    async def update_client(
        self, client_id: str, client: ClientUpdate, logo_path: str = None
    ) -> dict:
        try:
            update_data = {k: v for k, v in client.dict().items() if v is not None}
            if logo_path:
                update_data["logo"] = logo_path

            if update_data:
                update_data["updated_at"] = datetime.utcnow()
                await self.clients.update_one(
                    {"_id": ObjectId(client_id)}, {"$set": update_data}
                )
            return await self.get_client(client_id)
        except Exception as e:
            raise e

    async def delete_client(self, client_id: str) -> bool:
        try:
            result = await self.clients.delete_one({"_id": ObjectId(client_id)})
            return result.deleted_count > 0
        except Exception as e:
            raise e

    # Project CRUD
    async def create_project(
        self, project: ProjectCreate, logo_path: str = None
    ) -> dict:
        try:
            project_data = project.dict()
            if logo_path:
                project_data["logo"] = logo_path

            project_data["created_at"] = datetime.utcnow()
            result = await self.projects.insert_one(project_data)
            project_data["id"] = str(result.inserted_id)
            return normalize(project_data)
        except Exception as e:
            raise e

    async def get_projects(self) -> List[dict]:
        try:
            projects = await self.projects.find().to_list(length=None)

            # Fetch all clients and employees for mapping
            clients = await self.clients.find().to_list(length=None)
            employees = await self.employees.find().to_list(length=None)

            client_map = {str(c["_id"]): normalize(c) for c in clients}

            # Prepare employee map with sensitive fields removed
            employee_map = {}
            for e in employees:
                emp_norm = normalize(e)
                if "hashed_password" in emp_norm:
                    del emp_norm["hashed_password"]
                if "password" in emp_norm:
                    del emp_norm["password"]
                employee_map[emp_norm["id"]] = emp_norm

            result = []
            for p in projects:
                p_norm = normalize(p)
                p_norm["client"] = client_map.get(str(p_norm.get("client_id")))

                # Fetch members details
                p_norm["project_managers"] = [
                    employee_map.get(eid)
                    for eid in p_norm.get("project_manager_ids", [])
                    if eid in employee_map
                ]
                p_norm["team_leaders"] = [
                    employee_map.get(eid)
                    for eid in p_norm.get("team_leader_ids", [])
                    if eid in employee_map
                ]
                p_norm["team_members"] = [
                    employee_map.get(eid)
                    for eid in p_norm.get("team_member_ids", [])
                    if eid in employee_map
                ]

                result.append(p_norm)

            return result
        except Exception as e:
            raise e


    async def get_projects_summary(self) -> List[dict]:
        try:
            projection = {
                "name": 1,
                "status": 1,
                "logo": 1
            }
            projects = await self.projects.find({}, projection).to_list(length=None)
            return [normalize(p) for p in projects]
        except Exception as e:
            raise e

    async def get_project(self, project_id: str) -> dict:
        try:
            project = await self.projects.find_one({"_id": ObjectId(project_id)})
            if not project:
                return None

            p_norm = normalize(project)

            # Fetch client
            client = await self.clients.find_one(
                {"_id": ObjectId(p_norm.get("client_id"))}
            )
            p_norm["client"] = normalize(client) if client else None

            # Fetch members
            all_emp_ids = set()
            all_emp_ids.update(p_norm.get("project_manager_ids", []))
            all_emp_ids.update(p_norm.get("team_leader_ids", []))
            all_emp_ids.update(p_norm.get("team_member_ids", []))

            # Convert string IDs to ObjectIds for query
            obj_ids = []
            for eid in all_emp_ids:
                try:
                    obj_ids.append(ObjectId(eid))
                except:
                    continue

            employees = await self.employees.find({"_id": {"$in": obj_ids}}).to_list(
                length=None
            )
            employee_map = {}
            for e in employees:
                emp_norm = normalize(e)
                if "hashed_password" in emp_norm:
                    del emp_norm["hashed_password"]
                if "password" in emp_norm:
                    del emp_norm["password"]
                employee_map[emp_norm["id"]] = emp_norm

            p_norm["project_managers"] = [
                employee_map.get(eid)
                for eid in p_norm.get("project_manager_ids", [])
                if eid in employee_map
            ]
            p_norm["team_leaders"] = [
                employee_map.get(eid)
                for eid in p_norm.get("team_leader_ids", [])
                if eid in employee_map
            ]
            p_norm["team_members"] = [
                employee_map.get(eid)
                for eid in p_norm.get("team_member_ids", [])
                if eid in employee_map
            ]

            return p_norm
        except Exception as e:
            raise e

    async def update_project(
        self, project_id: str, project: ProjectUpdate, logo_path: str = None
    ) -> dict:
        try:
            update_data = {k: v for k, v in project.dict().items() if v is not None}
            if logo_path:
                update_data["logo"] = logo_path
            if update_data:
                update_data["updated_at"] = datetime.utcnow()
                await self.projects.update_one(
                    {"_id": ObjectId(project_id)}, {"$set": update_data}
                )
            return await self.get_project(project_id)
        except Exception as e:
            raise e

    async def delete_project(self, project_id: str) -> bool:
        try:
            result = await self.projects.delete_one({"_id": ObjectId(project_id)})
            return result.deleted_count > 0
        except Exception as e:
            raise e

    # Holiday CRUD
    async def create_holiday(self, holiday: HolidayCreate) -> dict:
        try:
            holiday_data = holiday.dict()
            holiday_data["created_at"] = datetime.utcnow()
            result = await self.holidays.insert_one(holiday_data)
            holiday_data["id"] = str(result.inserted_id)
            return normalize(holiday_data)
        except Exception as e:
            raise e

    async def get_holidays(self) -> List[dict]:
        try:
            holidays = await self.holidays.find().to_list(length=None)
            return [normalize(h) for h in holidays]
        except Exception as e:
            raise e

    async def get_holiday(self, holiday_id: str) -> dict:
        try:
            holiday = await self.holidays.find_one({"_id": ObjectId(holiday_id)})
            return normalize(holiday) if holiday else None
        except Exception as e:
            raise e

    async def update_holiday(self, holiday_id: str, holiday: HolidayUpdate) -> dict:
        try:
            update_data = {k: v for k, v in holiday.dict().items() if v is not None}
            if update_data:
                update_data["updated_at"] = datetime.utcnow()
                await self.holidays.update_one(
                    {"_id": ObjectId(holiday_id)}, {"$set": update_data}
                )
            return await self.get_holiday(holiday_id)
        except Exception as e:
            raise e

    async def delete_holiday(self, holiday_id: str) -> bool:
        try:
            result = await self.holidays.delete_one({"_id": ObjectId(holiday_id)})
            return result.deleted_count > 0
        except Exception as e:
            raise e

    # Asset Category CRUD
    async def create_asset_category(self, category: AssetCategoryCreate) -> dict:
        try:
            category_data = category.dict()
            category_data["created_at"] = datetime.utcnow()
            result = await self.asset_categories.insert_one(category_data)
            category_data["id"] = str(result.inserted_id)
            return normalize(category_data)
        except Exception as e:
            raise e

    async def get_asset_categories(self) -> List[dict]:
        try:
            categories = await self.asset_categories.find().to_list(length=None)
            return [normalize(cat) for cat in categories]
        except Exception as e:
            raise e

    async def get_asset_category(self, category_id: str) -> dict:
        try:
            category = await self.asset_categories.find_one(
                {"_id": ObjectId(category_id)}
            )
            return normalize(category) if category else None
        except Exception as e:
            raise e

    async def update_asset_category(
        self, category_id: str, category: AssetCategoryUpdate
    ) -> dict:
        try:
            update_data = {k: v for k, v in category.dict().items() if v is not None}
            if update_data:
                update_data["updated_at"] = datetime.utcnow()
                await self.asset_categories.update_one(
                    {"_id": ObjectId(category_id)}, {"$set": update_data}
                )
            return await self.get_asset_category(category_id)
        except Exception as e:
            raise e

    async def delete_asset_category(self, category_id: str) -> bool:
        try:
            result = await self.asset_categories.delete_one(
                {"_id": ObjectId(category_id)}
            )
            return result.deleted_count > 0
        except Exception as e:
            raise e

    # Asset CRUD
    async def create_asset(self, asset: AssetCreate, images: List[str] = []) -> dict:
        try:
            asset_data = asset.dict()
            if images:
                asset_data["images"] = images

            asset_data["created_at"] = datetime.utcnow()
            result = await self.assets.insert_one(asset_data)
            asset_data["id"] = str(result.inserted_id)
            return normalize(asset_data)
        except Exception as e:
            raise e

    async def get_assets(self) -> List[dict]:
        try:
            assets = (
                await self.assets.find().sort("created_at", -1).to_list(length=None)
            )

            # Map categories and employees
            categories = await self.asset_categories.find().to_list(length=None)
            employees = await self.employees.find().to_list(length=None)

            cat_map = {str(c["_id"]): normalize(c) for c in categories}
            emp_map = {
                str(e["_id"]): normalize(e) for e in employees
            }  # Mapping by _id (Primary Key)

            result = []
            for a in assets:
                a_norm = normalize(a)
                a_norm["category"] = cat_map.get(str(a_norm.get("asset_category_id")))
                a_norm["assigned_to_details"] = emp_map.get(
                    str(a_norm.get("assigned_to"))
                )
                result.append(a_norm)

            return result
        except Exception as e:
            raise e

    async def get_asset(self, asset_id: str) -> dict:
        try:
            asset = await self.assets.find_one({"_id": ObjectId(asset_id)})
            if not asset:
                return None

            a_norm = normalize(asset)

            # Category
            category = await self.asset_categories.find_one(
                {"_id": ObjectId(a_norm.get("asset_category_id"))}
            )
            a_norm["category"] = normalize(category) if category else None

            # Employee
            assigned_to = a_norm.get("assigned_to")
            if assigned_to:
                try:
                    employee = await self.employees.find_one(
                        {"_id": ObjectId(assigned_to)}
                    )
                except:
                    employee = None
                a_norm["assigned_to_details"] = (
                    normalize(employee) if employee else None
                )

            return a_norm
        except Exception as e:
            raise e

    async def update_asset(
        self, asset_id: str, asset: AssetUpdate, images: List[str] = []
    ) -> dict:
        try:
            update_data = {k: v for k, v in asset.dict().items() if v is not None}
            if images:
                update_data["images"] = images

            if update_data:
                update_data["updated_at"] = datetime.utcnow()
                await self.assets.update_one(
                    {"_id": ObjectId(asset_id)}, {"$set": update_data}
                )
            return await self.get_asset(asset_id)
        except Exception as e:
            raise e

    async def delete_asset(self, asset_id: str) -> bool:
        try:
            result = await self.assets.delete_one({"_id": ObjectId(asset_id)})
            return result.deleted_count > 0
        except Exception as e:
            raise e

    async def manage_asset_assignment(
        self, asset_id: str, employee_id: Optional[str] = None
    ) -> dict:
        try:
            # Verify asset exists
            asset = await self.assets.find_one({"_id": ObjectId(asset_id)})
            if not asset:
                raise ValueError("Asset not found")

            update_data = {}

            if employee_id:
                # Verify employee exists
                employee = await self.employees.find_one({"_id": ObjectId(employee_id)})
                if not employee:
                    raise ValueError("Employee not found")

                # Assign asset
                update_data["assigned_to"] = employee_id
                update_data["status"] = "Assigned"
            else:
                # Unassign asset
                update_data["assigned_to"] = None
                update_data["status"] = "Available"

            update_data["updated_at"] = datetime.utcnow()

            await self.assets.update_one(
                {"_id": ObjectId(asset_id)}, {"$set": update_data}
            )

            return await self.get_asset(asset_id)
        except Exception as e:
            raise e

    async def get_assets_by_employee(self, employee_id: str) -> List[dict]:
        try:
            # Verify employee exists
            employee = await self.employees.find_one({"_id": ObjectId(employee_id)})
            if not employee:
                raise ValueError("Employee not found")

            # Get all assets assigned to this employee
            assets = await self.assets.find({"assigned_to": employee_id}).to_list(
                length=None
            )

            # Map categories
            categories = await self.asset_categories.find().to_list(length=None)
            cat_map = {str(c["_id"]): normalize(c) for c in categories}

            result = []
            for a in assets:
                a_norm = normalize(a)
                a_norm["category"] = cat_map.get(str(a_norm.get("asset_category_id")))
                a_norm["assigned_to_details"] = normalize(employee)
                result.append(a_norm)

            return result
        except Exception as e:
            raise e

    # Blog CRUD Operations
    async def create_blog(self, blog: BlogCreate) -> dict:
        try:
            blog_data = blog.dict()
            blog_data["created_at"] = datetime.utcnow()
            blog_data["deleted"] = False
            result = await self.blogs.insert_one(blog_data)
            blog_data["id"] = str(result.inserted_id)
            return normalize(blog_data)
        except Exception as e:
            raise e

    async def get_blogs(
        self, page: int = 1, limit: int = 10, search: str = None
    ) -> dict:
        try:
            query = {"deleted": False}
            if search:
                query["title"] = {"$regex": search, "$options": "i"}

            total = await self.blogs.count_documents(query)
            cursor = (
                self.blogs.find(query)
                .sort("created_at", -1)
                .skip((page - 1) * limit)
                .limit(limit)
            )
            blogs_list = await cursor.to_list(length=limit)

            data = [normalize(b) for b in blogs_list]
            return {
                "data": data,
                "meta": {
                    "current_page": page,
                    "last_page": (total + limit - 1) // limit if limit > 0 else 0,
                    "per_page": limit,
                    "total": total,
                },
            }
        except Exception as e:
            raise e

    async def get_blog(self, blog_id: str) -> dict:
        try:
            query = {"deleted": False}
            if ObjectId.is_valid(blog_id):
                query["_id"] = ObjectId(blog_id)
            else:
                query["slug"] = blog_id

            blog = await self.blogs.find_one(query)
            if not blog:
                return None

            blog_norm = normalize(blog)

            # Recommendations Logic
            recommendations = []
            rec_filters = []
            if blog_norm.get("category"):
                rec_filters.append({"category": blog_norm["category"]})
            
            if blog_norm.get("tags") and isinstance(blog_norm["tags"], list) and len(blog_norm["tags"]) > 0:
                rec_filters.append({"tags": {"$in": blog_norm["tags"]}})

            if rec_filters:
                rec_query = {
                    "deleted": False,
                    "_id": {"$ne": ObjectId(blog_norm["id"])},
                    "$or": rec_filters
                }
                cursor = self.blogs.find(rec_query).sort("created_at", -1).limit(3)
                recs = await cursor.to_list(length=3)
                recommendations = [normalize(r) for r in recs]

            blog_norm["recommendations"] = recommendations
            return blog_norm
        except Exception as e:
            raise e

    async def update_blog(self, blog_id: str, blog: BlogUpdate) -> dict:
        try:
            update_data = {k: v for k, v in blog.dict().items() if v is not None}
            if update_data:
                update_data["updated_at"] = datetime.utcnow()
                await self.blogs.update_one(
                    {"_id": ObjectId(blog_id)}, {"$set": update_data}
                )
            return await self.get_blog(blog_id)
        except Exception as e:
            raise e

    async def delete_blog(self, blog_id: str) -> bool:
        try:
            result = await self.blogs.update_one(
                {"_id": ObjectId(blog_id)},
                {"$set": {"deleted": True, "deleted_at": datetime.utcnow()}},
            )
            return result.modified_count > 0
        except Exception as e:
            raise e

    # Leave Type CRUD operations
    async def create_leave_type(self, leave_type: LeaveTypeCreate) -> dict:
        try:
            leave_type_data = leave_type.dict()
            leave_type_data["created_at"] = datetime.utcnow()
            result = await self.leave_types.insert_one(leave_type_data)
            leave_type_data["id"] = str(result.inserted_id)
            return normalize(leave_type_data)
        except Exception as e:
            raise e

    async def get_leave_types(self) -> List[dict]:
        try:
            leave_types = await self.leave_types.find().to_list(length=None)
            return [normalize(lt) for lt in leave_types]
        except Exception as e:
            raise e

    async def get_leave_type(self, leave_type_id: str) -> dict:
        try:
            leave_type = await self.leave_types.find_one(
                {"_id": ObjectId(leave_type_id)}
            )
            return normalize(leave_type) if leave_type else None
        except Exception as e:
            raise e

    async def update_leave_type(
        self, leave_type_id: str, leave_type: LeaveTypeUpdate
    ) -> dict:
        try:
            update_data = {k: v for k, v in leave_type.dict().items() if v is not None}
            if update_data:
                update_data["updated_at"] = datetime.utcnow()
                await self.leave_types.update_one(
                    {"_id": ObjectId(leave_type_id)}, {"$set": update_data}
                )
            return await self.get_leave_type(leave_type_id)
        except Exception as e:
            raise e

    async def delete_leave_type(self, leave_type_id: str) -> bool:
        try:
            result = await self.leave_types.delete_one({"_id": ObjectId(leave_type_id)})
            return result.deleted_count > 0
        except Exception as e:
            raise e

    # Leave Request CRUD operations
    async def create_leave_request(
        self, leave_request: LeaveRequestCreate, attachment_path: str = None
    ) -> dict:
        try:
            leave_request_data = leave_request.dict()

            # Check for overlapping leave requests
            existing_leave = await self.leave_requests.find_one(
                {
                    "employee_id": leave_request.employee_id,
                    "status": {"$in": ["Approved", "Pending"]},
                    "$or": [
                        {
                            "start_date": {"$lte": leave_request.end_date},
                            "end_date": {"$gte": leave_request.start_date},
                        }
                    ],
                }
            )

            if existing_leave:
                raise ValueError(
                    f"A leave request already exists for the selected dates (Status: {existing_leave.get('status')})"
                )

            if attachment_path:
                leave_request_data["attachment"] = attachment_path

            leave_request_data["created_at"] = datetime.utcnow()
            result = await self.leave_requests.insert_one(leave_request_data)
            leave_request_id = str(result.inserted_id)
            return await self.get_leave_request(leave_request_id)
        except Exception as e:
            raise e

    async def get_employee_leave_balances(self, employee_id: str) -> List[dict]:
        try:
            leave_types = await self.leave_types.find({"status": "Active"}).to_list(
                length=None
            )
            current_year = str(datetime.utcnow().year)
            requests = await self.leave_requests.find(
                {
                    "employee_id": employee_id,
                    "status": "Approved",
                    "start_date": {"$regex": f"^{current_year}"},
                }
            ).to_list(length=None)

            balances = []
            for lt in leave_types:
                lt_id = str(lt["_id"])
                used = sum(
                    [
                        float(r.get("total_days", 0))
                        for r in requests
                        if r.get("leave_type_id") == lt_id
                    ]
                )
                total_allowed = lt.get("number_of_days", 0)
                balances.append(
                    {
                        "leave_type": lt.get("name"),
                        "code": lt.get("code"),
                        "total_allowed": total_allowed,
                        "used": used,
                        "available": max(0, total_allowed - used),
                        "allowed_hours": lt.get("allowed_hours", 0),
                    }
                )
            return balances
        except Exception as e:
            print(f"Error calculating leave balances: {str(e)}")
            return []

    async def get_leave_requests(
        self, employee_id: str = None, status: str = None
    ) -> List[dict]:
        try:
            query = {}
            if employee_id:
                query["employee_id"] = employee_id
            if status and status != "All":
                query["status"] = status

            requests = await self.leave_requests.find(query).to_list(length=None)

            # Map details
            employees = await self.employees.find().to_list(length=None)
            leave_types = await self.leave_types.find().to_list(length=None)

            emp_map = {str(e["_id"]): normalize(e) for e in employees}
            lt_map = {str(lt["_id"]): normalize(lt) for lt in leave_types}

            result = []
            for r in requests:
                r_norm = normalize(r)
                emp_norm = emp_map.get(str(r_norm.get("employee_id")))
                r_norm["employee_details"] = get_employee_basic_details(emp_norm) if emp_norm else None
                r_norm["leave_type_details"] = lt_map.get(
                    str(r_norm.get("leave_type_id"))
                )
                result.append(r_norm)

            return result
        except Exception as e:
            raise e

    async def get_leave_request(self, leave_request_id: str) -> dict:
        try:
            request = await self.leave_requests.find_one(
                {"_id": ObjectId(leave_request_id)}
            )
            if not request:
                return None

            r_norm = normalize(request)

            # Fetch Employee
            employee = await self.employees.find_one(
                {"_id": ObjectId(r_norm.get("employee_id"))}
            )
            r_norm["employee_details"] = get_employee_basic_details(normalize(employee)) if employee else None

            # Fetch Leave Type
            leave_type = await self.leave_types.find_one(
                {"_id": ObjectId(r_norm.get("leave_type_id"))}
            )
            r_norm["leave_type_details"] = normalize(leave_type) if leave_type else None

            return r_norm
        except Exception as e:
            raise e

    async def update_leave_request(
        self,
        leave_request_id: str,
        leave_request: LeaveRequestUpdate,
        attachment_path: str = None,
    ) -> dict:
        try:
            # Fetch current state before update to check for status changes
            old_req = await self.get_leave_request(leave_request_id)

            update_data = {
                k: v for k, v in leave_request.dict().items() if v is not None
            }
            if attachment_path:
                update_data["attachment"] = attachment_path

            if update_data:
                update_data["updated_at"] = datetime.utcnow()
                await self.leave_requests.update_one(
                    {"_id": ObjectId(leave_request_id)}, {"$set": update_data}
                )

            updated_req = await self.get_leave_request(leave_request_id)

            if not updated_req or not old_req:
                return updated_req

            old_status = old_req.get("status")
            new_status = updated_req.get("status")

            # Logic 1: Status changed TO Approved
            if new_status == "Approved" and old_status != "Approved":
                await self.handle_approved_leave_impact(updated_req)

            # Logic 2: Status changed FROM Approved TO something else (Cancellation/Rejection)
            elif old_status == "Approved" and new_status != "Approved":
                await self.cleanup_leave_attendance_records(old_req)

            return updated_req
        except Exception as e:
            raise e

    async def cleanup_leave_attendance_records(self, leave_req: dict):
        """
        Removes system-generated "Leave" attendance records for a given leave request.
        Used when a leave is cancelled, rejected, or deleted.
        """
        try:
            start_date = leave_req.get("start_date")
            end_date = leave_req.get("end_date")
            emp_mongo_id = leave_req.get("employee_id")

            employee = await self.employees.find_one({"_id": ObjectId(emp_mongo_id)})
            if not employee:
                return

            emp_no_id = str(employee.get("_id"))

            # 1. Remove "Leave" records for this employee in the date range
            # ONLY if they haven't clocked in (clock_in is None)
            await self.attendance.delete_many(
                {
                    "employee_id": emp_no_id,
                    "date": {"$gte": start_date, "$lte": end_date},
                    "status": "Leave",
                    "clock_in": None,
                }
            )
            
            # 2. Revert "Permission" and "Half Day" detailed status back to "Present"
            # if they are checked in (status = "Present")
            await self.attendance.update_many(
                {
                    "employee_id": emp_no_id,
                    "date": {"$gte": start_date, "$lte": end_date},
                    "status": "Present",
                    "attendance_status": {"$in": ["Permission", "Half Day"]}
                },
                {
                    "$set": {
                        "attendance_status": "Present",
                        "is_half_day": False,
                        "notes": "",
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            # 3. Revert "Leave" records back to "Present" if they have a clock-in
            # This handles the case where a Full Day leave is rejected AFTER an employee clocked in
            await self.attendance.update_many(
                {
                    "employee_id": emp_no_id,
                    "date": {"$gte": start_date, "$lte": end_date},
                    "status": "Leave",
                    "clock_in": {"$ne": None},
                },
                {
                    "$set": {
                        "status": "Present",
                        "attendance_status": "Present",
                        "notes": "Reverted Leave to Present after leave rejection",
                        "updated_at": datetime.utcnow()
                    }
                }
            )
        except Exception as e:
            print(f"Error cleaning up leave attendance: {e}")

    async def handle_approved_leave_impact(self, leave_req: dict):
        """
        If a leave is approved for TODAY, immediately create/update the attendance record.
        This provides instant feedback on the dashboard.
        """
        try:
            start_date = leave_req.get("start_date")
            end_date = leave_req.get("end_date")
            emp_mongo_id = leave_req.get("employee_id")
            reason = leave_req.get("reason", "On Leave")

            today = datetime.utcnow().strftime("%Y-%m-%d")

            # Check if today is covered by the leave
            if start_date <= today <= end_date:
                duration_type = leave_req.get("leave_duration_type")

                # Fetch leave type code
                leave_type_code = None
                lt_id = leave_req.get("leave_type_id")
                if lt_id:
                    try:
                        lt = await self.leave_types.find_one({"_id": ObjectId(lt_id)})
                        if lt:
                            leave_type_code = lt.get("code")
                    except:
                        pass

                # Derive detailed status
                attendance_status = leave_type_code or "Leave"
                is_half_day = False
                if duration_type == "Half Day":
                    attendance_status = "Half Day"
                    is_half_day = True
                elif duration_type == "Permission":
                    attendance_status = "Permission"

                # Need to find the employee (standardizing on mongo _id string as employee_id)
                employee = await self.employees.find_one(
                    {"_id": ObjectId(emp_mongo_id)}
                )
                if not employee:
                    return

                emp_standard_id = str(employee.get("_id"))

                # Check existing attendance for today
                existing = await self.attendance.find_one(
                    {"employee_id": emp_standard_id, "date": today}
                )

                if not existing:
                    # Create Leave record (Skip for Permission since it's a partial absence and they should show up)
                    if duration_type == "Permission":
                        return 
                        
                    await self.attendance.insert_one(
                        {
                            "employee_id":       emp_standard_id,
                            "date":              today,
                            "status":            "Leave",
                            "attendance_status": attendance_status,
                            "is_half_day":       is_half_day,
                            "leave_type_code":   leave_type_code,
                            "notes":             reason,
                            "clock_in":          None,
                            "clock_out":         None,
                            "total_work_hours":  0.0,
                            "overtime_hours":    0.0,
                            "device_type":       "Auto Sync",
                            "created_at":        datetime.utcnow(),
                        }
                    )
                else:
                    current_status = existing.get("status")
                    update_fields = {
                        "device_type": "Auto Sync",
                        "updated_at": datetime.utcnow()
                    }
                    
                    if current_status == "Absent":
                        if duration_type != "Permission":
                            update_fields["status"] = "Leave"
                            
                    if duration_type == "Permission":
                        update_fields["attendance_status"] = "Permission"
                        update_fields["notes"] = f"Approved Permission: {reason}"
                    elif duration_type == "Half Day":
                        update_fields["is_half_day"] = True
                        update_fields["attendance_status"] = "Half Day"
                        update_fields["notes"] = f"Approved Half Day: {reason}" # Changed from 'Approved Leave' to 'Approved Half Day' for clarity
                    else:
                        update_fields["status"] = "Leave"
                        update_fields["attendance_status"] = attendance_status
                        update_fields["is_half_day"] = False
                        update_fields["leave_type_code"] = leave_type_code
                        update_fields["notes"] = f"Approved Leave: {reason}"
                        
                    await self.attendance.update_one(
                        {"_id": existing["_id"]},
                        {"$set": update_fields}
                    )

        except Exception as e:
            # We don't want to fail the whole request if this background task fails
            print(f"Error handling leave impact: {e}")

    async def delete_leave_request(self, leave_request_id: str) -> bool:
        try:
            # Fetch the request first so we know what to cleanup
            leave_req = await self.get_leave_request(leave_request_id)
            if not leave_req:
                return False

            result = await self.leave_requests.delete_one(
                {"_id": ObjectId(leave_request_id)}
            )

            if result.deleted_count > 0 and leave_req.get("status") == "Approved":
                # If it was approved, cleanup the attendance records for its dates
                await self.cleanup_leave_attendance_records(leave_req)

            return result.deleted_count > 0
        except Exception as e:
            raise e

    # Task CRUD
    async def create_task(self, task: TaskCreate) -> dict:
        try:
            task_data = task.dict()
            task_data["created_at"] = datetime.utcnow()
            task_data["eod_history"] = []
            result = await self.tasks.insert_one(task_data)
            task_data["id"] = str(result.inserted_id)
            return normalize(task_data)
        except Exception as e:
            raise e

    async def get_tasks(
        self,
        project_id: Optional[str] = None,
        assigned_to: Optional[str] = None,
        start_date: Optional[str] = None,
        date: Optional[str] = None,
        status: Optional[str] = None,
        priority: Optional[str] = None,
    ) -> List[dict]:
        try:
            query = {}
            if project_id:
                query["project_id"] = project_id
            if assigned_to:
                # Matches if employee ID is in the list
                query["assigned_to"] = assigned_to
            
            if status:
                query["status"] = status
            
            if priority:
                query["priority"] = priority

            if date:
                # Determine the cutoff date for overdue calculation.
                # If the filter date is in the future (e.g., Tomorrow), we shouldn't mark "Today's" tasks as overdue yet.
                # So "Overdue" is always strictly relative to "Now" (Today), unless we are looking at the past.
                today_str = datetime.utcnow().strftime("%Y-%m-%d")
                overdue_cutoff = date if date < today_str else today_str

                # Active tasks on this specific date OR Overdue tasks
                # Overdue = end_date < overdue_cutoff AND status != Completed
                query["$or"] = [
                    # 1. Active on date: start_date <= date AND (end_date >= date OR end_date is None)
                    {
                        "$and": [
                            {"start_date": {"$lte": date}},
                            {
                                "$or": [
                                    {"end_date": {"$gte": date}},
                                    {"end_date": None},
                                    {"end_date": ""},
                                    {"end_date": {"$exists": False}},
                                ]
                            },
                        ]
                    },
                    # 2. Overdue: end_date < overdue_cutoff AND status != Completed
                    {
                        "$and": [
                            {"end_date": {"$lt": overdue_cutoff}},
                            {"status": {"$ne": "Completed"}},
                            {"end_date": {"$ne": None}},
                            {"end_date": {"$ne": ""}},
                        ]
                    },
                ]
            elif start_date:
                # Fallback to exact start date match if no specific 'date' view requested
                query["start_date"] = start_date

            tasks = await self.tasks.find(query).to_list(length=None)

            results = []
            for t in tasks:
                norm_task = normalize(t)

                # Calculate is_overdue flag
                is_overdue = False
                if (
                    date
                    and norm_task.get("end_date")
                    and norm_task.get("status") != "Completed"
                ):
                    # Use the same cutoff logic for the flag
                    today_str = datetime.utcnow().strftime("%Y-%m-%d")
                    cutoff = date if date < today_str else today_str

                    if norm_task["end_date"] < cutoff:
                        is_overdue = True

                norm_task["is_overdue"] = is_overdue
                results.append(norm_task)

            return results
        except Exception as e:
            raise e

    async def get_task(self, task_id: str) -> dict:
        try:
            task = await self.tasks.find_one({"_id": ObjectId(task_id)})
            return normalize(task) if task else None
        except Exception as e:
            raise e

    async def update_task(self, task_id: str, task: TaskUpdate) -> dict:
        try:
            update_data = {k: v for k, v in task.dict().items() if v is not None}
            if update_data:
                update_data["updated_at"] = datetime.utcnow()
                await self.tasks.update_one(
                    {"_id": ObjectId(task_id)}, {"$set": update_data}
                )
            return await self.get_task(task_id)
        except Exception as e:
            raise e

    async def process_eod_report(self, items: List[EODReportItem]) -> List[dict]:
        results = []
        for item in items:
            task_id = item.task_id
            existing_task = await self.get_task(task_id)
            if not existing_task:
                continue

            # Update existing task history and status
            eod_entry = {
                "date": datetime.utcnow().strftime("%Y-%m-%d"),
                "status": "Moved" if item.move_to_tomorrow else item.status,
                "progress": item.progress,
                "summary": item.eod_summary,
                "attachments": [a.dict() for a in item.new_attachments],
                "timestamp": datetime.utcnow(),
            }

            update_fields = {"progress": item.progress, "updated_at": datetime.utcnow()}

            if item.move_to_tomorrow:
                # Visual Rollover: Mark as rolled over today
                today_str = datetime.utcnow().strftime("%Y-%m-%d")
                update_fields["last_rollover_date"] = today_str

                # Smart Rollover: Preserve future deadlines
                # Only update end_date if the current deadline is BEFORE tomorrow
                from datetime import timedelta

                tomorrow_dt = datetime.utcnow() + timedelta(days=1)
                tomorrow_str = tomorrow_dt.strftime("%Y-%m-%d")

                existing_end_date = existing_task.get("end_date")

                # If no end date or end date is earlier than tomorrow, extend it to tomorrow
                if not existing_end_date or existing_end_date < tomorrow_str:
                    update_fields["end_date"] = tomorrow_str

                # Always keep status as "In Progress" for rollover
                update_fields["status"] = "In Progress"
            else:
                update_fields["status"] = item.status

            # Add to history and update fields
            await self.tasks.update_one(
                {"_id": ObjectId(task_id)},
                {"$set": update_fields, "$push": {"eod_history": eod_entry}},
            )

            updated_task = await self.get_task(task_id)
            results.append(updated_task)

        return results

    async def get_eod_reports(
        self,
        project_id: Optional[str] = None,
        assigned_to: Optional[str] = None,
        date: Optional[str] = None,
        priority: Optional[str] = None,
        search: Optional[str] = None,
    ) -> List[dict]:
        try:
            query = {"eod_history": {"$exists": True, "$not": {"$size": 0}}}
            if project_id:
                query["project_id"] = project_id
            if assigned_to:
                query["assigned_to"] = assigned_to
            if priority:
                query["priority"] = priority

            tasks = await self.tasks.find(query).to_list(length=None)

            # Fetch all employees and projects for naming
            employees = await self.employees.find().to_list(length=None)
            projects = await self.projects.find().to_list(length=None)

            emp_map = {
                str(e.get("employee_no_id")): e.get("name")
                for e in employees
                if e.get("employee_no_id")
            }
            id_to_name_map = {str(e.get("_id")): e.get("name") for e in employees}
            proj_map = {str(p.get("_id")): p.get("name") for p in projects}

            reports = []
            for task in tasks:
                task_norm = normalize(task)
                proj_name = proj_map.get(task_norm.get("project_id"), "Unknown Project")

                # assigned_to is a list of IDs. We'll take the first one or join them
                assigned_ids = task_norm.get("assigned_to", [])
                assigned_names = [
                    emp_map.get(eid) or id_to_name_map.get(eid) or eid
                    for eid in assigned_ids
                ]
                employee_display = ", ".join(filter(None, assigned_names))

                for entry in task_norm.get("eod_history", []):
                    if date and entry.get("date") != date:
                        continue
                    
                    # Search Filtering
                    if search:
                        search_lower = search.lower()
                        task_name = (task_norm.get("task_name") or task_norm.get("name") or "").lower()
                        summary = (entry.get("summary") or "").lower()
                        emp_name = employee_display.lower()
                        
                        if (
                            search_lower not in task_name
                            and search_lower not in summary
                            and search_lower not in emp_name
                        ):
                            continue

                    report_entry = {
                        "task_id": task_norm["id"],
                        "task_name": task_norm.get("task_name")
                        or task_norm.get("name")
                        or "Untitled Task",
                        "project_id": task_norm.get("project_id"),
                        "project_name": proj_name,
                        "assigned_to": task_norm.get("assigned_to", []),
                        "employee_name": employee_display,
                        **entry,
                    }
                    reports.append(report_entry)

            reports.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            return reports
        except Exception as e:
            raise e

    async def delete_task(self, task_id: str) -> bool:
        try:
            result = await self.tasks.delete_one({"_id": ObjectId(task_id)})
            return result.deleted_count > 0
        except Exception as e:
            raise e

    async def bulk_import_attendance(self, records: List[dict]) -> dict:
        try:
            if not records:
                return {"success": True, "count": 0}

            # To avoid duplicates, we can check for existing (employee_id, date)
            # For simplicity in import, we might want to either skip or overwrite.
            # User request says "import from excel", usually this implies sync or overwrite.
            # Let's perform upserts.

            operations = []
            from pymongo import UpdateOne

            for rec in records:
                # Ensure date is string
                dt = rec.get("date")
                emp_id = rec.get("employee_id")

                if dt and emp_id:
                    operations.append(
                        UpdateOne(
                            {"employee_id": emp_id, "date": dt},
                            {"$set": {**rec, "updated_at": datetime.utcnow()}},
                            upsert=True,
                        )
                    )

            if operations:
                result = await self.attendance.bulk_write(operations)
                return {
                    "success": True,
                    "matched": result.matched_count,
                    "upserted": result.upserted_count,
                    "modified": result.modified_count,
                }

            return {"success": True, "count": 0}
        except Exception as e:
            raise e

    # Attendance CRUD

    async def edit_attendance_record(self, attendance_id: str, data: "AttendanceAdminEdit") -> dict:
        """Admin-only: patch an existing attendance record by its _id."""
        try:
            from bson import ObjectId as _ObjId
            record = await self.attendance.find_one({"_id": _ObjId(attendance_id)})
            if not record:
                raise ValueError("Attendance record not found")

            update_fields = {k: v for k, v in data.dict().items() if v is not None}

            # Auto-recalculate total_work_hours when possible
            clock_in_str  = update_fields.get("clock_in")  or record.get("clock_in")
            clock_out_str = update_fields.get("clock_out") or record.get("clock_out")

            if clock_in_str and clock_out_str:
                try:
                    ci = datetime.fromisoformat(clock_in_str.replace("Z", "+00:00"))
                    co = datetime.fromisoformat(clock_out_str.replace("Z", "+00:00"))
                    diff = (co - ci).total_seconds() / 3600
                    if diff > 0:
                        update_fields["total_work_hours"] = round(diff, 2)
                except Exception:
                    pass

            update_fields["updated_at"] = datetime.utcnow()
            await self.attendance.update_one(
                {"_id": _ObjId(attendance_id)},
                {"$set": update_fields}
            )

            updated = await self.attendance.find_one({"_id": _ObjId(attendance_id)})
            r_norm = normalize(updated)

            # Embed employee_details
            emp = None
            emp_id = r_norm.get("employee_id")
            if emp_id:
                emp = await self.employees.find_one({
                    "$or": [
                        {"_id": _ObjId(emp_id) if _ObjId.is_valid(emp_id) else "000000000000000000000000"},
                        {"employee_no_id": emp_id},
                    ]
                })
            if emp:
                r_norm["employee_details"] = get_employee_basic_details(normalize(emp))
            else:
                r_norm["employee_details"] = None

            return r_norm
        except Exception as e:
            raise e

    async def clock_in(self, attendance: AttendanceCreate, employee_id: str) -> dict:
        try:
            # Resolve to MongoDB _id to ensure consistency
            target_emp_id = employee_id
            
            # Try finding the employee to get stable _id
            emp = await self.employees.find_one({
                "$or": [
                     {"employee_no_id": employee_id},
                     {"_id": ObjectId(employee_id) if ObjectId.is_valid(employee_id) else "000000000000000000000000"}
                ]
            })
            
            if emp:
                target_emp_id = str(emp["_id"])

            # Check if already has an attendance record for this date
            existing = await self.attendance.find_one(
                {"employee_id": target_emp_id, "date": attendance.date}
            )

            attendance_data = attendance.dict()
            attendance_data["employee_id"] = target_emp_id
            attendance_data["updated_at"] = datetime.utcnow()
            
            # --- SHIFT & LATE CALCULATION START ---
            
            # 1. Get Shift Details
            shift = None
            shift_id = emp.get("shift_id") if emp else None
            
            if shift_id:
                shift = await self.shifts.find_one({"_id": ObjectId(shift_id)})
            
            # 2. Fallback to Department Default Shift if no personal shift
            if not shift and emp and emp.get("department"):
                dept = await self.departments.find_one({"name": emp.get("department")})
                if dept and dept.get("default_shift_id"):
                    shift = await self.shifts.find_one({"_id": ObjectId(dept["default_shift_id"])})
            
            # 3. Determine Work Start Time, End Time & Grace Period
            work_start_time = "09:00"  # Default
            work_end_time = "18:00"    # Default
            late_grace_period = 15     # Default minutes
            
            if shift:
                work_start_time = shift.get("start_time", "09:00")
                work_end_time = shift.get("end_time", "18:00")
                late_grace_period = shift.get("late_threshold_minutes", 15)
            else:
                work_start_time_config = await self.system_configurations.find_one({"key": "work_start_time"})
                late_grace_period_config = await self.system_configurations.find_one({"key": "late_grace_period_minutes"})
                if work_start_time_config:
                    work_start_time = work_start_time_config.get("value", "09:00")
                if late_grace_period_config:
                    late_grace_period = late_grace_period_config.get("value", 15)

            # 4. Parse Times
            from datetime import timedelta as _timedelta

            clock_in_dt = datetime.fromisoformat(attendance.clock_in.replace("Z", "+00:00"))
            ist_offset = _timedelta(hours=5, minutes=30)
            clock_in_ist = clock_in_dt + ist_offset
            clock_in_time = clock_in_ist.time()

            def _parse_time(t_str, fallback="09:00"):
                for fmt in ("%H:%M", "%H:%M:%S"):
                    try:
                        return datetime.strptime(t_str, fmt).time()
                    except ValueError:
                        pass
                return datetime.strptime(fallback, "%H:%M").time()

            work_start = _parse_time(work_start_time, "09:00")
            work_end   = _parse_time(work_end_time,   "18:00")

            # 5. Calculate Mid-Shift time for Half Day
            start_minutes = work_start.hour * 60 + work_start.minute
            end_minutes   = work_end.hour * 60 + work_end.minute
            mid_minutes   = start_minutes + (end_minutes - start_minutes) // 2
            mid_shift_hour, mid_shift_min = divmod(mid_minutes, 60)
            from datetime import time as _time
            mid_shift_time = _time(mid_shift_hour, mid_shift_min)

            # 6. Fetch Approved Leave Request for this employee & date
            approved_leave = await self.leave_requests.find_one({
                "employee_id": target_emp_id,
                "status": "Approved",
                "start_date": {"$lte": attendance.date},
                "end_date":   {"$gte": attendance.date},
            })

            leave_duration_type = approved_leave.get("leave_duration_type") if approved_leave else None
            half_day_session    = approved_leave.get("half_day_session") if approved_leave else None

            # Determine leave_type_code from the leave type document
            leave_type_code = None
            if approved_leave and approved_leave.get("leave_type_id"):
                lt = await self.leave_types.find_one({"_id": ObjectId(approved_leave["leave_type_id"])})
                if lt:
                    leave_type_code = lt.get("code")

            # 7. Effective start time (adjusted for Half Day)
            effective_start = work_start
            if leave_duration_type == "Half Day" and half_day_session == "First Half":
                # Employee on leave for morning → expected in for afternoon
                effective_start = mid_shift_time

            # 8. Compute Late
            is_late = False
            clock_in_minutes = clock_in_time.hour * 60 + clock_in_time.minute
            eff_start_minutes = effective_start.hour * 60 + effective_start.minute

            if clock_in_minutes > eff_start_minutes:
                minutes_late = clock_in_minutes - eff_start_minutes
                if minutes_late > late_grace_period:
                    is_late = True

            # 9. Derive detailed status
            is_permission = False
            is_half_day   = False
            attendance_status = "Ontime"

            if leave_duration_type == "Permission":
                is_permission     = True
                attendance_status = "Permission"
            elif leave_duration_type == "Half Day":
                is_half_day       = True
                attendance_status = "Half Day"
            elif is_late:
                attendance_status = "Late"
            else:
                attendance_status = "Ontime"

            status = "Present"

            # --- SHIFT & LATE CALCULATION END ---
            
            attendance_data["is_late"]          = is_late
            attendance_data["is_permission"]     = is_permission
            attendance_data["is_half_day"]       = is_half_day
            attendance_data["attendance_status"] = attendance_status
            attendance_data["leave_type_code"]   = leave_type_code
            attendance_data["status"]            = status

            if existing:
                # If they are already marked "Present", "Late", or "Overtime", don't allow double clock-in
                if existing.get("status") in ["Present", "Late", "Overtime"]:
                    raise ValueError("Already clocked in for this date")

                # Option C: If the employee has a Full Day approved leave,
                # preserve the Leave status (to keep leave balance deducted)
                # but still record their clock-in time for work-hour tracking.
                is_full_day_leave = (
                    existing.get("status") == "Leave"
                    and leave_duration_type not in ["Half Day", "Permission"]
                )

                if is_full_day_leave:
                    # Keep Leave status, just record the clock-in time
                    await self.attendance.update_one(
                        {"_id": existing["_id"]},
                        {
                            "$set": {
                                "clock_in":    attendance_data["clock_in"],
                                "device_type": attendance_data["device_type"],
                                "is_late":     is_late,
                                "notes":       f"Employee clocked in while on Full Day Leave – leave balance remains deducted",
                                "updated_at":  datetime.utcnow(),
                            }
                        },
                    )
                else:
                    # Absent / Holiday / Half Day / Permission: override to Present
                    await self.attendance.update_one(
                        {"_id": existing["_id"]},
                        {
                            "$set": {
                                "clock_in":          attendance_data["clock_in"],
                                "device_type":       attendance_data["device_type"],
                                "status":            status,
                                "attendance_status": attendance_status,
                                "is_late":           is_late,
                                "is_permission":     is_permission,
                                "is_half_day":       is_half_day,
                                "leave_type_code":   leave_type_code,
                                "notes": f"Overrode {existing.get('status')} - Employee clocked in ({attendance_status})",
                                "updated_at": datetime.utcnow(),
                            }
                        },
                    )
                attendance_data["id"] = str(existing["_id"])
                res = {**existing, **attendance_data}
                if emp:
                    res["employee_details"] = get_employee_basic_details(emp)
                return normalize(res)

            # No existing record, create new one
            attendance_data["created_at"] = datetime.utcnow()
            result = await self.attendance.insert_one(attendance_data)
            attendance_data["id"] = str(result.inserted_id)
            if emp:
                attendance_data["employee_details"] = get_employee_basic_details(emp)
            return normalize(attendance_data)
        except Exception as e:
            raise e


    async def clock_out(
        self, attendance: AttendanceUpdate, employee_id: str, date: str
    ) -> dict:
        try:
            # Resolve to MongoDB _id to ensure consistency
            target_emp_id = employee_id
            
            # Try finding the employee to get stable _id
            emp = await self.employees.find_one({
                "$or": [
                     {"employee_no_id": employee_id},
                     {"_id": ObjectId(employee_id) if ObjectId.is_valid(employee_id) else "000000000000000000000000"}
                ]
            })
            
            if emp:
                target_emp_id = str(emp["_id"])

            existing = await self.attendance.find_one(
                {"employee_id": target_emp_id, "date": date}
            )
            if not existing:
                # Fallback: Try searching with the original ID just in case it was a legacy record 
                # (though dashboard should handle migration, this is safety for active sessions)
                existing = await self.attendance.find_one(
                    {"employee_id": employee_id, "date": date}
                )
            
            if not existing:
                raise ValueError("No clock-in record found for this date")

            update_data = {k: v for k, v in attendance.dict().items() if v is not None}

            # Calculate work hours logic could be added here or in frontend.
            # Simple duration calc if formats allow.
            # Ideally calculation happens here.

            start_str = existing.get("clock_in")
            end_str = update_data.get("clock_out")

            # --- OVERTIME CALCULATION START ---
            if start_str and end_str:
                try:
                    # Parse Times
                    start_dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                    end_dt = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
                    duration = (end_dt - start_dt).total_seconds() / 3600
                    
                    total_work_hours = round(duration, 2)
                    update_data["total_work_hours"] = total_work_hours
                    
                    # Get Shift for Overtime Calculation
                    shift = None
                    if emp and emp.get("shift_id"):
                        shift = await self.shifts.find_one({"_id": ObjectId(emp["shift_id"])})
                    
                    if not shift and emp and emp.get("department"):
                        dept = await self.departments.find_one({"name": emp.get("department")})
                        if dept and dept.get("default_shift_id"):
                            shift = await self.shifts.find_one({"_id": ObjectId(dept["default_shift_id"])})
                    
                    # Calculate Expected Shift Duration
                    shift_duration = 9.00 # Default fallback (9 hours)
                    
                    if shift:
                        try:
                            s_start = datetime.strptime(shift.get("start_time", "09:00"), "%H:%M")
                            s_end = datetime.strptime(shift.get("end_time", "18:00"), "%H:%M")
                            
                            # Handle crossing midnight (e.g. 20:00 - 05:00)
                            if s_end < s_start:
                                s_end += timedelta(days=1)
                                
                            shift_duration = (s_end - s_start).total_seconds() / 3600
                        except:
                            shift_duration = 9.00
                            
                    # Calculate Overtime
                    # Logic: Overtime = Work Hours - Shift Duration
                    overtime = max(0.0, total_work_hours - shift_duration)
                    update_data["overtime_hours"] = round(overtime, 2)
                    
                    # Optional: Update status to "Overtime" if significant overtime?
                    # valid statuses: Present, Late, Absent, Leave, Holiday, Overtime
                    # If already Late, keep it Late? Or upgrade to Overtime?
                    # Requirements usually keep "Late" entry status but maybe show OT flag.
                    # For now, if overtime > 1 hour, maybe update status?
                    # Let's keep status as is (Present/Late) unless specific requirement to change status.
                    # update_data["status"] = "Overtime" if overtime > 0 else ...
                    
                except Exception as e:
                    print(f"Error calculating OT: {e}")
                    pass 
            # --- OVERTIME CALCULATION END ---

            update_data["updated_at"] = datetime.utcnow()

            await self.attendance.update_one(
                {"_id": existing["_id"]}, {"$set": update_data}
            )

            updated_record = await self.attendance.find_one({"_id": existing["_id"]})
            res = normalize(updated_record)
            if emp:
                res["employee_details"] = get_employee_basic_details(emp)
            return res
        except Exception as e:
            raise e




    async def get_employee_attendance(
        self, employee_id: str, start_date: str = None, end_date: str = None
    ) -> dict:
        try:
            # If no dates provided, default to current month
            if not start_date or not end_date:
                now = datetime.utcnow()
                start_date = now.replace(day=1).strftime("%Y-%m-%d")
                # Last day of month
                if now.month == 12:
                    last_day = now.replace(
                        year=now.year + 1, month=1, day=1
                    ) - timedelta(days=1)
                else:
                    last_day = now.replace(month=now.month + 1, day=1) - timedelta(
                        days=1
                    )
                end_date = last_day.strftime("%Y-%m-%d")

            return await self.get_all_attendance(
                start_date=start_date, end_date=end_date, employee_id=employee_id
            )
        except Exception as e:
            raise e

    async def get_all_attendance(
        self,
        date: str = None,
        start_date: str = None,
        end_date: str = None,
        employee_id: str = None,
        status: str = None,
        page: int = 1,
        limit: int = 20,
    ) -> dict:
        try:
            query = {}
            if date:
                query["date"] = date
            elif start_date and end_date:
                query["date"] = {"$gte": start_date, "$lte": end_date}
            elif start_date:
                query["date"] = {"$gte": start_date}

            if employee_id:
                # Try to find employee to get both IDs
                emp = await self.employees.find_one(
                    {
                        "$or": [
                            {
                                "_id": ObjectId(employee_id)
                                if ObjectId.is_valid(employee_id)
                                else "000000000000000000000000"
                            },
                            {"employee_no_id": employee_id},
                        ]
                    }
                )

                if emp:
                    # Search by both Mongo ID (str) and Biometric ID (str or int)
                    emp_mongo_id = str(emp.get("_id"))
                    emp_bio_id = str(emp.get("employee_no_id"))
                    query["employee_id"] = {"$in": [emp_mongo_id, emp_bio_id]}
                else:
                    query["employee_id"] = employee_id

            # Status filter for all attendance statuses
            if status:
                query["status"] = status

            # Pagination Logic
            skip = (page - 1) * limit
            total_count = await self.attendance.count_documents(query)

            records = (
                await self.attendance.find(query)
                .sort("date", -1)
                .skip(skip)
                .limit(limit)
                .to_list(length=limit)
            )

            # Fetch employee details for mapping
            employees = await self.employees.find().to_list(length=None)
            emp_map = {}
            for e in employees:
                e_norm = normalize(e)
                # Map by ID (ObjectId string)
                if e_norm.get("id"):
                    emp_map[str(e_norm["id"])] = e_norm
                # Map by Employee No ID (Biometric ID)
                if e_norm.get("employee_no_id"):
                    emp_map[str(e_norm["employee_no_id"])] = e_norm

            result = []

            for r in records:
                r_norm = normalize(r)
                emp_details = emp_map.get(r_norm.get("employee_id"))
                
                # OPTIMIZATION: Use helper to get only basic details
                if emp_details:
                    r_norm["employee_details"] = get_employee_basic_details(emp_details)
                else:
                    r_norm["employee_details"] = None
                    
                result.append(r_norm)

            # Sort by date and employee name (already sorted by date in DB query, secondary sort in memory if needed but DB sort is better)
            # result.sort(...) -> DB sort is sufficient for date.

            # Dashboard Metrics (Global or User Specific)
            metrics = await self.get_dashboard_metrics(
                employee_id=query.get("employee_id")
            )

            pagination = {
                "total_records": total_count,
                "current_page": page,
                "limit": limit,
                "total_pages": (total_count + limit - 1) // limit if limit > 0 else 0,
            }

            return {"data": result, "metrics": metrics, "pagination": pagination}
        except Exception as e:
            print(f"Error in get_all_attendance: {e}")
            raise e

    async def get_dashboard_metrics(self, employee_id: str = None) -> dict:
        try:
            today = datetime.now().date()
            start_of_today = today.strftime("%Y-%m-%d")

            start_of_month = today.replace(day=1).strftime("%Y-%m-%d")

            # Simple assumption for start of year
            start_of_year = today.replace(month=1, day=1).strftime("%Y-%m-%d")

            # Helper to run aggregation
            async def aggregate_stats(start_date: str, end_date: str = None):
                match_query = {"date": {"$gte": start_date}}
                if end_date:
                    match_query["date"]["$lte"] = end_date

                if employee_id:
                    match_query["employee_id"] = employee_id

                # Group by primary status
                pipeline_status = [
                    {"$match": match_query},
                    {"$group": {"_id": "$status", "count": {"$sum": 1}}},
                ]
                # Group by detailed attendance_status
                pipeline_detail = [
                    {"$match": match_query},
                    {"$group": {"_id": "$attendance_status", "count": {"$sum": 1}}},
                ]

                status_cursor = await self.attendance.aggregate(pipeline_status)
                detail_cursor = await self.attendance.aggregate(pipeline_detail)

                # --- Primary counters ---
                present_total = 0
                absent        = 0
                leave         = 0
                holiday       = 0

                async for doc in status_cursor:
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

                # --- Detailed sub-status counters ---
                on_time    = 0
                late       = 0
                permission = 0
                half_day   = 0

                async for doc in detail_cursor:
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
                    # Primary totals
                    "total_present": present_total,
                    "absent":        absent,
                    "leave":         leave,
                    "holiday":       holiday,
                    # Detailed Present breakdown
                    "on_time":       on_time,
                    "late":          late,
                    "permission":    permission,
                    "half_day":      half_day,
                }


            # Run aggregations
            # Today: Exact match on date, not range
            today_stats = await aggregate_stats(start_of_today, start_of_today)
            month_stats = await aggregate_stats(start_of_month)
            year_stats = await aggregate_stats(start_of_year)

            return {"today": today_stats, "month": month_stats, "year": year_stats}
        except Exception as e:
            print(f"Error calculating metrics: {e}")
            return {}

    # Checklist Template CRUD
    async def create_checklist_template(
        self, template: EmployeeChecklistTemplateCreate
    ) -> dict:
        try:
            template_data = template.dict()
            template_data["created_at"] = datetime.utcnow()
            result = await self.db["checklist_templates"].insert_one(template_data)
            template_data["id"] = str(result.inserted_id)
            return normalize(template_data)
        except Exception as e:
            raise e

    async def get_checklist_templates(self) -> List[dict]:
        try:
            templates = await self.db["checklist_templates"].find().to_list(length=None)
            return [normalize(t) for t in templates]
        except Exception as e:
            raise e

    async def update_checklist_template(
        self, template_id: str, template: EmployeeChecklistTemplateUpdate
    ) -> dict:
        try:
            update_data = {k: v for k, v in template.dict().items() if v is not None}
            if update_data:
                update_data["updated_at"] = datetime.utcnow()
                await self.db["checklist_templates"].update_one(
                    {"_id": ObjectId(template_id)}, {"$set": update_data}
                )
            # Find and return
            t = await self.db["checklist_templates"].find_one(
                {"_id": ObjectId(template_id)}
            )
            return normalize(t) if t else None
        except Exception as e:
            raise e

    async def delete_checklist_template(self, template_id: str) -> bool:
        try:
            result = await self.db["checklist_templates"].delete_one(
                {"_id": ObjectId(template_id)}
            )
            return result.deleted_count > 0
        except Exception as e:
            raise e

    async def bulk_sync_biometric_logs(self, logs: List[BiometricLogItem]) -> dict:
        try:
            processed_count = 0
            errors = []

            sorted_logs = sorted(logs, key=lambda x: x.timestamp)

            for log in sorted_logs:
                try:
                    try:
                        log_time = datetime.fromisoformat(log.timestamp)
                    except:
                        try:
                            log_time = datetime.strptime(
                                log.timestamp, "%Y-%m-%d %H:%M:%S"
                            )
                        except:
                            if "T" in log.timestamp:
                                # Fallback manual parse if needed
                                pass
                            continue  # Skip invalid dates

                    date_str = log_time.strftime("%Y-%m-%d")
                    time_str = log_time.isoformat()

                    # Strict Match: Look for employee with this biometric_id
                    # We treat log.user_id as the biometric_id (e.g. "101")
                    # It might be coming as int or str, so we try both strict string match or conversion if needed.
                    # Since we store biometric_id as String in DB (based on model), we cast log.user_id to string.
                    
                    bio_id_str = str(log.user_id).strip()
                    
                    employee = await self.employees.find_one(
                        {"biometric_id": bio_id_str}
                    )
                    
                    if not employee:
                        continue

                    # Use MongoDB ObjectId as the standard employee_id
                    employee_id = str(employee["_id"])

                    attendance = await self.attendance.find_one(
                        {"employee_id": employee_id, "date": date_str}
                    )

                    # --- UNIFIED CLOCK IN / OVERRIDE LOGIC ---
                    # We handle clock-in if:
                    # 1. No record exists yet.
                    # 2. A record exists (e.g. "Leave") but has no clock_in time.
                    if not attendance or not attendance.get("clock_in"):
                        # 1. Get Shift Details
                        shift = None
                        shift_id = employee.get("shift_id")
                        
                        if shift_id:
                            shift = await self.shifts.find_one({"_id": ObjectId(shift_id)})
                        
                        # 2. Fallback to Department Default Shift if no personal shift
                        if not shift and employee.get("department"):
                            dept = await self.departments.find_one({"name": employee.get("department")})
                            if dept and dept.get("default_shift_id"):
                                shift = await self.shifts.find_one({"_id": ObjectId(dept["default_shift_id"])})
                        
                        # 3. Determine Work Start Time, End Time & Grace Period
                        work_start_time_config = await self.system_configurations.find_one({"key": "work_start_time"})
                        late_grace_period_config = await self.system_configurations.find_one({"key": "late_grace_period_minutes"})
                        
                        work_start_time = "09:00"  # Default
                        work_end_time   = "18:00"  # Default
                        late_grace_period = 15     # Default

                        if shift:
                            work_start_time   = shift.get("start_time", "09:00")
                            work_end_time     = shift.get("end_time", "18:00")
                            late_grace_period = shift.get("late_threshold_minutes", 15)
                        else:
                            if work_start_time_config:
                                work_start_time = work_start_time_config.get("value", "09:00")
                            if late_grace_period_config:
                                late_grace_period = late_grace_period_config.get("value", 15)

                        def _bio_parse_time(t_str, fallback="09:00"):
                            for fmt in ("%H:%M", "%H:%M:%S"):
                                try:
                                    return datetime.strptime(t_str, fmt).time()
                                except ValueError:
                                    pass
                            return datetime.strptime(fallback, "%H:%M").time()

                        work_start = _bio_parse_time(work_start_time, "09:00")
                        work_end   = _bio_parse_time(work_end_time, "18:00")

                        # 4. Calculate Mid-Shift for Half Day
                        s_min  = work_start.hour * 60 + work_start.minute
                        e_min  = work_end.hour * 60 + work_end.minute
                        mid_min = s_min + (e_min - s_min) // 2
                        mid_h, mid_m = divmod(mid_min, 60)
                        from datetime import time as _btime
                        mid_shift_time = _btime(mid_h, mid_m)

                        clock_in_time = log_time.time()

                        # 5. Fetch Approved Leave Request for this employee & date
                        approved_leave = await self.leave_requests.find_one({
                            "employee_id": employee_id,
                            "status": "Approved",
                            "start_date": {"$lte": date_str},
                            "end_date":   {"$gte": date_str},
                        })

                        leave_duration_type = approved_leave.get("leave_duration_type") if approved_leave else None
                        half_day_session    = approved_leave.get("half_day_session") if approved_leave else None

                        # Determine leave_type_code
                        leave_type_code = None
                        if approved_leave and approved_leave.get("leave_type_id"):
                            lt = await self.leave_types.find_one({"_id": ObjectId(approved_leave["leave_type_id"])})
                            if lt:
                                leave_type_code = lt.get("code")

                        # 6. Effective start time (adjusted for First Half Leave)
                        effective_start = work_start
                        if leave_duration_type == "Half Day" and half_day_session == "First Half":
                            effective_start = mid_shift_time

                        # 7. Compute Late
                        is_late = False
                        ci_min  = clock_in_time.hour * 60 + clock_in_time.minute
                        es_min  = effective_start.hour * 60 + effective_start.minute
                        if ci_min > es_min:
                            minutes_late = ci_min - es_min
                            if minutes_late > late_grace_period:
                                is_late = True

                        # 8. Derive detailed attendance_status
                        is_permission = False
                        is_half_day   = False

                        if leave_duration_type == "Permission":
                            is_permission     = True
                            attendance_status = "Permission"
                        elif leave_duration_type == "Half Day":
                            is_half_day       = True
                            attendance_status = "Half Day"
                        elif is_late:
                            attendance_status = "Late"
                        else:
                            attendance_status = "Ontime"

                        # --- UPDATE OR INSERT ---
                        if attendance:
                            # Option C: If the employee has a Full Day Leave,
                            # preserve the Leave status but record the clock-in time.
                            is_full_day_leave_bio = (
                                attendance.get("status") == "Leave"
                                and leave_duration_type not in ["Half Day", "Permission"]
                            )

                            if is_full_day_leave_bio:
                                await self.attendance.update_one(
                                    {"_id": attendance["_id"]},
                                    {
                                        "$set": {
                                            "clock_in":    time_str,
                                            "device_type": "Biometric",
                                            "is_late":     is_late,
                                            "notes":       "Employee clocked in while on Full Day Leave – leave balance remains deducted",
                                            "updated_at":  datetime.utcnow(),
                                        }
                                    }
                                )
                            else:
                                # Absent / Holiday / Half Day / Permission: override to Present
                                await self.attendance.update_one(
                                    {"_id": attendance["_id"]},
                                    {
                                        "$set": {
                                            "clock_in":          time_str,
                                            "status":            "Present",
                                            "attendance_status": attendance_status,
                                            "is_late":           is_late,
                                            "is_permission":     is_permission,
                                            "is_half_day":       is_half_day,
                                            "leave_type_code":   leave_type_code,
                                            "device_type":       "Biometric",
                                            "updated_at":        datetime.utcnow(),
                                        }
                                    }
                                )
                        else:
                            # No existing record → create new Present record
                            new_record = {
                                "employee_id":       employee_id,
                                "date":              date_str,
                                "clock_in":          time_str,
                                "device_type":       "Biometric",
                                "status":            "Present",
                                "attendance_status": attendance_status,
                                "is_late":           is_late,
                                "is_permission":     is_permission,
                                "is_half_day":       is_half_day,
                                "leave_type_code":   leave_type_code,
                                "created_at":        datetime.utcnow(),
                            }
                            await self.attendance.insert_one(new_record)
                        
                        processed_count += 1

                    else: 
                        # --- CLOCK OUT LOGIC ---
                        # Only process if this log is later than the existing clock_in
                        # Note: We use the existing clock_in string from the record
                        clock_in_time_dt = datetime.fromisoformat(attendance["clock_in"])

                        if log_time > clock_in_time_dt:
                            should_update = True
                            if attendance.get("clock_out"):
                                current_clock_out = datetime.fromisoformat(
                                    attendance["clock_out"]
                                )
                                if log_time <= current_clock_out:
                                    should_update = False  

                            if should_update:
                                work_duration = log_time - clock_in_time_dt
                                total_hours = round(
                                    work_duration.total_seconds() / 3600, 2
                                )

                                await self.attendance.update_one(
                                    {"_id": attendance["_id"]},
                                    {
                                        "$set": {
                                            "clock_out": time_str,
                                            "total_work_hours": total_hours,
                                            "device_type": "Biometric",  
                                            "updated_at": datetime.utcnow(),
                                        }
                                    },
                                )
                                processed_count += 1


                except Exception as e:
                    errors.append(f"Error processing log for {log.user_id}: {str(e)}")
                    continue

            return {
                "processed": processed_count,
                "total_received": len(logs),
                "errors": errors,
            }
        except Exception as e:
            raise e

    # System Configuration CRUD
    async def get_system_configurations(self) -> List[dict]:
        try:
            configs = await self.system_configurations.find().to_list(length=None)
            return [normalize(conf) for conf in configs]
        except Exception as e:
            raise e

    async def update_system_configurations(self, settings: dict) -> List[dict]:
        try:
            for key, value in settings.items():
                # Handle is_public fields separately
                if key.endswith("_is_public"):
                    actual_key = key.replace("_is_public", "")
                    existing = await self.system_configurations.find_one({"key": actual_key})
                    if existing:
                        await self.system_configurations.update_one(
                            {"key": actual_key},
                            {"$set": {"is_public": value, "updated_at": datetime.utcnow()}},
                        )
                else:
                    # Regular value update
                    existing = await self.system_configurations.find_one({"key": key})
                    if existing:
                        await self.system_configurations.update_one(
                            {"key": key},
                            {"$set": {"value": value, "updated_at": datetime.utcnow()}},
                        )
            return await self.get_system_configurations()
        except Exception as e:
            raise e

    async def get_public_system_configurations(self) -> List[dict]:
        try:
            configs = await self.system_configurations.find(
                {"is_public": True}
            ).to_list(length=None)
            return [normalize(conf) for conf in configs]
        except Exception as e:
            raise e


    # NDA Request CRUD
    async def create_nda_request(self, nda_request: "NDARequestCreate", token: str, expires_at: datetime) -> dict:
        try:
            nda_data = nda_request.dict()
            nda_data["token"] = token
            nda_data["status"] = "Pending"
            nda_data["expires_at"] = expires_at
            nda_data["created_at"] = datetime.utcnow()
            nda_data["documents"] = []
            nda_data["signature"] = None

            result = await self.nda_requests.insert_one(nda_data)
            nda_data["id"] = str(result.inserted_id)
            return normalize(nda_data)
        except Exception as e:
            raise e

    async def get_nda_requests(
        self,
        page: int = 1,
        limit: int = 10,
        search: Optional[str] = None,
        status: Optional[str] = None,
    ) -> (List[dict], int):
        try:
            query = {}

            if status and status != "All":
                query["status"] = status

            if search:
                regex_pattern = {"$regex": search, "$options": "i"}
                query["$or"] = [
                    {"employee_name": regex_pattern},
                    {"email": regex_pattern},
                    {"token": regex_pattern},
                ]

            skip = (page - 1) * limit
            total_items = await self.nda_requests.count_documents(query)

            nda_requests = (
                await self.nda_requests.find(query)
                .sort("created_at", -1)
                .skip(skip)
                .limit(limit)
                .to_list(length=limit)
            )

            return [normalize(req) for req in nda_requests], total_items
        except Exception as e:
            raise e

    async def get_nda_request_by_token(self, token: str) -> dict:
        try:
            nda_request = await self.nda_requests.find_one({"token": token})
            return normalize(nda_request) if nda_request else None
        except Exception as e:
            raise e

    async def update_nda_request(self, token: str, update_data: dict) -> dict:
        try:
            if update_data:
                update_data["updated_at"] = datetime.utcnow()
                await self.nda_requests.update_one(
                    {"token": token}, {"$set": update_data}
                )
            return await self.get_nda_request_by_token(token)
        except Exception as e:
            raise e

    async def regenerate_nda_token(self, nda_id: str, new_token: str, expires_at: datetime) -> dict:
        try:
            update_data = {
                "token": new_token,
                "expires_at": expires_at,
                "status": "Pending", 
                "updated_at": datetime.utcnow()
            }
            
            await self.nda_requests.update_one(
                {"_id": ObjectId(nda_id)},
                {"$set": update_data}
            )
             
            updated_doc = await self.nda_requests.find_one({"_id": ObjectId(nda_id)})
            return normalize(updated_doc)
        except Exception as e:
            raise e

    async def delete_nda_request(self, nda_id: str) -> bool:
        try:
            result = await self.nda_requests.delete_one({"_id": ObjectId(nda_id)})
            return result.deleted_count > 0
        except Exception as e:
            raise e


    # Payslip CRUD
    async def create_payslip(self, payslip_data: dict, file_path: str) -> dict:
        try:
            # payslip_data includes month, year, earnings, deductions, net_pay, employee_id
            payslip_data["file_path"] = file_path
            payslip_data["generated_at"] = datetime.utcnow()
            payslip_data["status"] = "Generated"
            
            result = await self.payslips.insert_one(payslip_data)
            payslip_data["id"] = str(result.inserted_id)
             
            emp = await self.employees.find_one({"_id": ObjectId(payslip_data["employee_id"])})
            payslip_norm = normalize(payslip_data)
            if emp:
                payslip_norm["employee_name"] = emp.get("name")
                payslip_norm["employee_email"] = emp.get("email")
                payslip_norm["employee_mobile"] = emp.get("mobile")
            
            return payslip_norm
        except Exception as e:
            raise e

    async def get_payslips(
        self,
        page: int = 1,
        limit: int = 10,
        employee_id: Optional[str] = None,
        month: Optional[str] = None,
        year: Optional[str] = None,
        search: Optional[str] = None,
    ) -> (List[dict], int):
        try:
            query = {}
            if employee_id:
                query["employee_id"] = employee_id
            if month and month != "All":
                query["month"] = month
            if year and year != "All":
                query["year"] = int(year)

            if search:
                regex_pattern = {"$regex": search, "$options": "i"}
                matched_employees = await self.employees.find({
                    "$or": [
                        {"name": regex_pattern},
                        {"employee_no_id": regex_pattern},
                        {"email": regex_pattern}
                    ]
                }, {"_id": 1}).to_list(length=None)
                
                matched_ids = [str(emp["_id"]) for emp in matched_employees]
                
                if employee_id:
                    # If specific employee_id is already filtered, ensure it matches search
                    if employee_id in matched_ids:
                        query["employee_id"] = employee_id
                    else:
                        # No intersection, return empty
                        return [], 0
                else:
                    query["employee_id"] = {"$in": matched_ids}

            skip = (page - 1) * limit
            total_items = await self.payslips.count_documents(query)
            
            payslips = (
                await self.payslips.find(query)
                .sort("generated_at", -1)
                .skip(skip)
                .limit(limit)
                .to_list(length=limit)
            )

            results = []
            for p in payslips:
                p_norm = normalize(p)
                # Fetch employee details
                emp = await self.employees.find_one({"_id": ObjectId(p_norm["employee_id"])})
                if emp:
                    p_norm["employee_name"] = emp.get("name")
                    p_norm["employee_email"] = emp.get("email")
                    p_norm["employee_mobile"] = emp.get("mobile")
                results.append(p_norm)
            
            return results, total_items
        except Exception as e:
            raise e

    async def get_latest_payslip(self, employee_id: str) -> Optional[dict]:
        try:
            # Sort by year desc, then by generated_at desc to get the most recent
            payslip = await self.payslips.find_one(
                {"employee_id": employee_id},
                sort=[("year", -1), ("generated_at", -1)]
            )
            if not payslip:
                return None
            return normalize(payslip)
        except Exception as e:
            raise e

    async def get_payslip(self, payslip_id: str) -> dict:
        try:
            payslip = await self.payslips.find_one({"_id": ObjectId(payslip_id)})
            return normalize(payslip)
        except Exception as e:
            raise e

    async def update_payslip(self, payslip_id: str, update_data: dict) -> dict:
        try:
            if update_data:
                update_data["updated_at"] = datetime.utcnow()
                await self.payslips.update_one(
                    {"_id": ObjectId(payslip_id)},
                    {"$set": update_data}
                )
            
            updated_payslip = await self.payslips.find_one({"_id": ObjectId(payslip_id)})
            if not updated_payslip:
                return None
                
            # Fetch employee details
            emp = await self.employees.find_one({"_id": ObjectId(updated_payslip["employee_id"])})
            payslip_norm = normalize(updated_payslip)
            if emp:
                payslip_norm["employee_name"] = emp.get("name")
                payslip_norm["employee_email"] = emp.get("email")
                payslip_norm["employee_mobile"] = emp.get("mobile")
            
            return payslip_norm
        except Exception as e:
            raise e


    async def get_payslip(self, payslip_id: str) -> dict:
        try:
            doc = await self.payslips.find_one({"_id": ObjectId(payslip_id)})
            return normalize(doc)
        except Exception as e:
            raise e
            
    async def update_payslip(self, payslip_id: str, update_data: dict) -> dict:
        try:
            update_data["updated_at"] = datetime.utcnow()
            await self.payslips.update_one(
                {"_id": ObjectId(payslip_id)}, {"$set": update_data}
            )
            return await self.get_payslip(payslip_id)
        except Exception as e:
            raise e

    # Payslip Component CRUD
    async def create_payslip_component(self, component: PayslipComponentCreate) -> dict:
        try:
            data = component.dict()
            data["created_at"] = datetime.utcnow()
            result = await self.payslip_components.insert_one(data)
            data["id"] = str(result.inserted_id)
            return normalize(data)
        except Exception as e:
            raise e

    async def get_payslip_components(self, type: Optional[str] = None, is_active: Optional[bool] = None) -> List[dict]:
        try:
            query = {}
            if type:
                query["type"] = type
            if is_active is not None:
                query["is_active"] = is_active
            
            components = await self.payslip_components.find(query).to_list(length=None)
            return [normalize(c) for c in components]
        except Exception as e:
            raise e

    async def get_payslip_component(self, component_id: str) -> dict:
        try:
            component = await self.payslip_components.find_one({"_id": ObjectId(component_id)})
            return normalize(component)
        except Exception as e:
            raise e

    async def update_payslip_component(self, component_id: str, component: PayslipComponentUpdate) -> dict:
        try:
            update_data = {k: v for k, v in component.dict().items() if v is not None}
            if update_data:
                update_data["updated_at"] = datetime.utcnow()
                await self.payslip_components.update_one(
                    {"_id": ObjectId(component_id)}, {"$set": update_data}
                )
            return await self.get_payslip_component(component_id)
        except Exception as e:
            raise e

    async def delete_payslip_component(self, component_id: str) -> bool:
        try:
            result = await self.payslip_components.delete_one({"_id": ObjectId(component_id)})
            return result.deleted_count > 0
        except Exception as e:
            raise e


    # Feedback CRUD
    
    async def get_feedback_metrics(self, employee_id: Optional[str] = None) -> dict:
        try:
            metrics_query = {"employee_id": employee_id} if employee_id else {}
            all_feedbacks = await self.db["feedback"].find(metrics_query, {"type": 1, "status": 1}).to_list(length=None)

            type_counts = {"Bug": 0, "Feature Request": 0, "General": 0}
            status_counts = {"Open": 0, "In Review": 0, "Resolved": 0, "Closed": 0}

            for f in all_feedbacks:
                t = f.get("type", "General")
                s = f.get("status", "Open")
                if t in type_counts:
                    type_counts[t] += 1
                if s in status_counts:
                    status_counts[s] += 1

            return {
                "total": len(all_feedbacks),
                "by_type": type_counts,
                "by_status": status_counts,
            }
        except Exception as e:
            raise e

    async def create_feedback(self, feedback: FeedbackCreate) -> dict:
        try:
            feedback_data = feedback.dict()
            feedback_data["created_at"] = datetime.utcnow()
            result = await self.db["feedback"].insert_one(feedback_data)
            feedback_id = str(result.inserted_id)
            
            # Fetch enriched feedback
            new_feedback = await self.get_feedback(feedback_id)
            
            # Fetch metrics after creation
            metrics = await self.get_feedback_metrics()
            
            return {"feedback": new_feedback, "metrics": metrics}
        except Exception as e:
            raise e

    async def get_feedbacks(
        self, employee_id: Optional[str] = None, status: Optional[str] = None
    ) -> dict:
        try:
            query = {}
            if employee_id:
                query["employee_id"] = employee_id
            if status:
                query["status"] = status

            # Fetch feedbacks and compute metrics in parallel
            feedbacks_cursor = self.db["feedback"].find(query).sort("created_at", -1)
            feedbacks_raw = await feedbacks_cursor.to_list(length=None)

            # Build enriched list
            result = []
            for f in feedbacks_raw:
                feedback = normalize(f)
                emp_id = feedback.get("employee_id")
                if emp_id:
                    employee_details = await self.get_employee_basic_details(emp_id)
                    if employee_details:
                        feedback["employee"] = employee_details
                result.append(feedback)

            # Compute metrics using helper
            metrics = await self.get_feedback_metrics(employee_id=employee_id)

            return {"feedbacks": result, "metrics": metrics}
        except Exception as e:
            raise e


    async def get_feedback(self, feedback_id: str) -> dict:
        try:
            feedback_raw = await self.db["feedback"].find_one({"_id": ObjectId(feedback_id)})
            if not feedback_raw:
                return None
            
            feedback = normalize(feedback_raw)
            emp_id = feedback.get("employee_id")
            if emp_id:
                employee_details = await self.get_employee_basic_details(emp_id)
                if employee_details:
                    feedback["employee"] = employee_details
            return feedback
        except Exception as e:
            raise e

    async def update_feedback(self, feedback_id: str, feedback: FeedbackUpdate) -> dict:
        try:
            update_data = {k: v for k, v in feedback.dict().items() if v is not None}
            if update_data:
                update_data["updated_at"] = datetime.utcnow()
                await self.db["feedback"].update_one(
                    {"_id": ObjectId(feedback_id)}, {"$set": update_data}
                )
            
            updated_feedback = await self.get_feedback(feedback_id)
            if not updated_feedback:
                return None
                
            # Fetch metrics after update
            metrics = await self.get_feedback_metrics()
            
            return {"feedback": updated_feedback, "metrics": metrics}
        except Exception as e:
            raise e

    async def delete_feedback(self, feedback_id: str) -> bool:
        try:
            result = await self.db["feedback"].delete_one({"_id": ObjectId(feedback_id)})
            return result.deleted_count > 0
        except Exception as e:
            raise e

    async def create_milestone_roadmap(self, item: MilestoneRoadmapCreate) -> dict:
        try:
            item_data = item.dict()
            item_data["created_at"] = datetime.utcnow()
            result = await self.milestones_roadmaps.insert_one(item_data)
            item_data["id"] = str(result.inserted_id)
            return normalize(item_data)
        except Exception as e:
            raise e

    async def get_milestones_roadmaps(
        self,
        project_id: Optional[str] = None,
        assigned_to: Optional[str] = None,
        status: Optional[str] = None,
        priority: Optional[str] = None
    ) -> List[dict]:
        try:
            query = {}
            if project_id: query["project_id"] = project_id
            if assigned_to: query["assigned_to"] = assigned_to
            if status: query["status"] = status
            if priority: query["priority"] = priority

            items = await self.milestones_roadmaps.find(query).to_list(length=None)
            return [normalize(item) for item in items]
        except Exception as e:
            raise e

    async def get_milestone_roadmap(self, item_id: str) -> dict:
        try:
            item = await self.milestones_roadmaps.find_one({"_id": ObjectId(item_id)})
            return normalize(item)
        except Exception as e:
            raise e

    async def update_milestone_roadmap(self, item_id: str, item: MilestoneRoadmapUpdate) -> dict:
        try:
            update_data = {k: v for k, v in item.dict().items() if v is not None}
            if update_data:
                update_data["updated_at"] = datetime.utcnow()
                await self.milestones_roadmaps.update_one(
                    {"_id": ObjectId(item_id)}, {"$set": update_data}
                )
            return await self.get_milestone_roadmap(item_id)
        except Exception as e:
            raise e

    async def delete_milestone_roadmap(self, item_id: str) -> bool:
        try:
            result = await self.milestones_roadmaps.delete_one({"_id": ObjectId(item_id)})
            return result.deleted_count > 0
        except Exception as e:
            raise e

repository = Repository()
