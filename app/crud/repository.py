from app.database import db
from app.models import (
    DepartmentCreate,
    DepartmentUpdate,
    EmployeeCreate,
    EmployeeUpdate,
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
    EmployeeChecklistTemplateCreate,
    EmployeeChecklistTemplateUpdate,
    BiometricLogItem,
    SystemConfigurationCreate,
    SystemConfigurationUpdate,
    NDARequestCreate,
    NDARequestUpdate,
    PayslipCreate,
)
from app.utils import normalize, get_password_hash, get_employee_basic_details
from bson import ObjectId
from datetime import datetime, timedelta
from typing import List, Optional


class Repository:
    """
    Repository class for all CRUD operations.
    """

    def __init__(self):
        self.db = db
        self.departments = self.db["departments"]
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
        self.tasks = self.db["tasks"]
        self.attendance = self.db["attendance"]
        self.system_configurations = self.db["system_configurations"]
        self.nda_requests = self.db["nda_requests"]
        self.payslips = self.db["payslips"]

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
            # User fields: employee_id, attendance_id, name, email, mobile, hashed_password
            user_data = {
                "employee_id": employee.employee_no_id,
                "attendance_id": employee.employee_no_id,  # Defaulting to emp_id
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
            
            identifier = employee.get("employee_no_id") or employee.get("id")
            return await self.get_dashboard_metrics(employee_id=identifier)
            
        except Exception as e:
            print(f"Error in get_employee_attendance_stats: {e}")
            return {}

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
                            {"employee_id": current_emp["employee_no_id"]},
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
                        {"employee_id": employee["employee_no_id"]}
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
                {"employee_id": emp_no_id},
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

            user = await self.users.find_one({"employee_id": emp_no_id})
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
            return normalize(document_data)
        except Exception as e:
            raise e

    async def get_documents(self) -> List[dict]:
        try:
            documents = await self.documents.find().to_list(length=None)
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
            return await self.get_document(document_id)
        except Exception as e:
            raise e

    async def delete_document(self, document_id: str) -> bool:
        try:
            result = await self.documents.delete_one({"_id": ObjectId(document_id)})
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
                r_norm["employee_details"] = emp_map.get(str(r_norm.get("employee_id")))
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
            r_norm["employee_details"] = normalize(employee) if employee else None

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

            emp_no_id = str(employee.get("employee_no_id"))

            # Remove "Leave" records for this employee in the date range
            # ONLY if they haven't clocked in (clock_in is None)
            await self.attendance.delete_many(
                {
                    "employee_id": emp_no_id,
                    "date": {"$gte": start_date, "$lte": end_date},
                    "status": "Leave",
                    "clock_in": None,
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
                # If it's a "Permission" type (short duration), do NOT mark as "Leave" in attendance.
                if leave_req.get("leave_duration_type") == "Permission":
                    return

                # Need to find the employee_no_id (which is used in attendance collection)
                # using the mongo _id stored in leave request
                employee = await self.employees.find_one(
                    {"_id": ObjectId(emp_mongo_id)}
                )
                if not employee:
                    return

                emp_no_id = str(employee.get("employee_no_id"))

                # Check existing attendance for today
                existing = await self.attendance.find_one(
                    {"employee_id": emp_no_id, "date": today}
                )

                if not existing:
                    # Create Leave record
                    await self.attendance.insert_one(
                        {
                            "employee_id": emp_no_id,
                            "date": today,
                            "status": "Leave",
                            "notes": reason,
                            "clock_in": None,
                            "clock_out": None,
                            "total_work_hours": 0.0,
                            "overtime_hours": 0.0,
                            "device_type": "Auto Sync",
                            "created_at": datetime.utcnow(),
                        }
                    )
                elif existing.get("status") == "Absent":
                    # Update Absent record to Leave
                    await self.attendance.update_one(
                        {"_id": existing["_id"]},
                        {
                            "$set": {
                                "status": "Leave",
                                "notes": reason,
                                "device_type": "Auto Sync",
                                "updated_at": datetime.utcnow(),
                            }
                        },
                    )
                # If status is "Present" (Clocked In), we typically don't overwrite it with Leave
                # as presence usually takes precedence or requires manual fix.

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
    ) -> List[dict]:
        try:
            query = {}
            if project_id:
                query["project_id"] = project_id
            if assigned_to:
                # Matches if employee ID is in the list
                query["assigned_to"] = assigned_to

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
            
            # Fetch system settings for late calculation
            work_start_time_config = await self.system_configurations.find_one(
                {"key": "work_start_time"}
            )
            late_grace_period_config = await self.system_configurations.find_one(
                {"key": "late_grace_period_minutes"}
            )
            
            # Default values if settings not found
            work_start_time = work_start_time_config.get("value", "09:00") if work_start_time_config else "09:00"
            late_grace_period = late_grace_period_config.get("value", 15) if late_grace_period_config else 15
            
            # Parse clock_in time and convert to IST (Asia/Kolkata)
            from datetime import timezone, timedelta
            
            clock_in_dt = datetime.fromisoformat(attendance.clock_in.replace("Z", "+00:00"))
            
            # Convert UTC to IST (UTC+5:30)
            ist_offset = timedelta(hours=5, minutes=30)
            clock_in_ist = clock_in_dt + ist_offset
            clock_in_time = clock_in_ist.time()
            
            # Parse work start time
            work_start = datetime.strptime(work_start_time, "%H:%M").time()
            
            # Calculate if late
            is_late = False
            status = "Present"
            
            if clock_in_time > work_start:
                # Calculate minutes late
                clock_in_minutes = clock_in_time.hour * 60 + clock_in_time.minute
                work_start_minutes = work_start.hour * 60 + work_start.minute
                minutes_late = clock_in_minutes - work_start_minutes
                
                if minutes_late > late_grace_period:
                    is_late = True
                    status = "Late"
            
            attendance_data["is_late"] = is_late
            attendance_data["status"] = status

            if existing:
                # If they are already marked "Present", "Late", or "Overtime", don't allow double clock-in
                if existing.get("status") in ["Present", "Late", "Overtime"]:
                    raise ValueError("Already clocked in for this date")

                # If they were marked "Absent", "Leave", or "Holiday" by the system,
                # we OVERSHADOW it because the employee actually showed up to work.
                await self.attendance.update_one(
                    {"_id": existing["_id"]},
                    {
                        "$set": {
                            "clock_in": attendance_data["clock_in"],
                            "device_type": attendance_data["device_type"],
                            "status": status,
                            "is_late": is_late,
                            "notes": f"Overrode {existing.get('status')} - Employee clocked in{' (Late)' if is_late else ''}",
                            "updated_at": datetime.utcnow(),
                        }
                    },
                )
                attendance_data["id"] = str(existing["_id"])
                return normalize({**existing, **attendance_data})

            # No existing record, create new one
            attendance_data["created_at"] = datetime.utcnow()
            result = await self.attendance.insert_one(attendance_data)
            attendance_data["id"] = str(result.inserted_id)
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

            if start_str and end_str:
                try:
                    # Attempt generic ISO parsing
                    start_dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                    end_dt = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
                    duration = (end_dt - start_dt).total_seconds() / 3600
                    update_data["total_work_hours"] = round(duration, 2)
                except:
                    pass  # Fallback or skip if format issues

            update_data["updated_at"] = datetime.utcnow()

            await self.attendance.update_one(
                {"_id": existing["_id"]}, {"$set": update_data}
            )

            updated_record = await self.attendance.find_one({"_id": existing["_id"]})
            return normalize(updated_record)
        except Exception as e:
            raise e

    async def update_attendance_status(
        self, attendance_id: str, status: str, reason: str = None, notes: str = None
    ) -> dict:
        """
        Update attendance status for a specific record.
        If status is 'Leave', creates a leave request with default reason if needed.
        If status changes FROM 'Leave' to something else, deletes the associated leave request.
        """
        try:
            # Find the attendance record
            attendance_record = await self.attendance.find_one(
                {"_id": ObjectId(attendance_id)}
            )
            if not attendance_record:
                return None

            old_status = attendance_record.get("status")
            emp_no_id = attendance_record.get("employee_id")
            date = attendance_record.get("date")

            # Prepare update data
            update_data = {"status": status, "updated_at": datetime.utcnow()}

            if notes:
                update_data["notes"] = notes

            # Update the attendance record
            await self.attendance.update_one(
                {"_id": ObjectId(attendance_id)}, {"$set": update_data}
            )

            # Find employee by employee_no_id to get MongoDB _id
            employee = await self.employees.find_one({"employee_no_id": emp_no_id})
            if employee:
                emp_mongo_id = str(employee.get("_id"))

                # If status is changed FROM "Leave" to something else, reject the leave request
                if old_status == "Leave" and status != "Leave":
                    # Reject leave request that covers this specific date
                    rejection_reason = (
                        notes if notes else "Attendance status changed from Leave"
                    )

                    # Reject any approved leave that covers this date
                    await self.leave_requests.update_many(
                        {
                            "employee_id": emp_mongo_id,
                            "start_date": {"$lte": date},
                            "end_date": {"$gte": date},
                            "status": "Approved",
                        },
                        {
                            "$set": {
                                "status": "Rejected",
                                "rejection_reason": rejection_reason,
                                "updated_at": datetime.utcnow(),
                            }
                        },
                    )

                # If status is changed TO "Leave", create or update leave request
                elif status == "Leave":
                    # Check if a leave request already exists for this date (including rejected ones)
                    existing_leave = await self.leave_requests.find_one(
                        {
                            "employee_id": emp_mongo_id,
                            "start_date": {"$lte": date},
                            "end_date": {"$gte": date},
                        }
                    )

                    if existing_leave:
                        # If leave exists but is rejected, re-approve it
                        if existing_leave.get("status") == "Rejected":
                            leave_reason = (
                                reason
                                if reason
                                else existing_leave.get("reason", "Manual Leave Entry")
                            )
                            await self.leave_requests.update_one(
                                {"_id": existing_leave["_id"]},
                                {
                                    "$set": {
                                        "status": "Approved",
                                        "reason": leave_reason,
                                        "rejection_reason": None,  # Clear rejection reason
                                        "updated_at": datetime.utcnow(),
                                    }
                                },
                            )
                    else:
                        # No existing leave, create a new one
                        # Get default leave type (first active leave type)
                        default_leave_type = await self.leave_types.find_one(
                            {"status": "Active"}
                        )

                        if default_leave_type:
                            # Create leave request with default reason
                            leave_reason = reason if reason else "Manual Leave Entry"

                            leave_data = {
                                "employee_id": emp_mongo_id,
                                "leave_type_id": str(default_leave_type.get("_id")),
                                "leave_duration_type": "Single",
                                "start_date": date,
                                "end_date": date,
                                "total_days": 1.0,
                                "reason": leave_reason,
                                "status": "Approved",  # Auto-approve since it's manual entry
                                "created_at": datetime.utcnow(),
                                "updated_at": datetime.utcnow(),
                            }

                            await self.leave_requests.insert_one(leave_data)

            # Return updated record
            updated_record = await self.attendance.find_one(
                {"_id": ObjectId(attendance_id)}
            )
            return normalize(updated_record)

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
                    # If employee_id is a dict (from get_all_attendance query logic), use it directly
                    # Otherwise treat as string
                    if isinstance(employee_id, dict):
                        match_query["employee_id"] = employee_id
                    else:
                        match_query["employee_id"] = employee_id

                pipeline = [
                    {"$match": match_query},
                    {"$group": {"_id": "$status", "count": {"$sum": 1}}},
                ]
                cursor = await self.attendance.aggregate(pipeline)
                
                # Count each status separately
                on_time = 0  # "Present" status
                late = 0     # "Late" status
                absent = 0
                leave = 0
                holiday = 0
                overtime = 0
                
                async for doc in cursor:
                    status_key = str(doc["_id"]).lower()
                    count = doc["count"]
                    
                    if status_key == "present":
                        on_time = count
                    elif status_key == "late":
                        late = count
                    elif status_key == "absent":
                        absent = count
                    elif status_key == "leave":
                        leave = count
                    elif status_key == "holiday":
                        holiday = count
                    elif status_key == "overtime":
                        overtime = count
                
                # Calculate total_present as sum of on_time + late + overtime
                total_present = on_time + late + overtime
                
                return {
                    "total_present": total_present,
                    "on_time": on_time,
                    "late": late,
                    "absent": absent,
                    "leave": leave,
                    "holiday": holiday,
                    "overtime": overtime,
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

                    employee_id = str(employee["_id"])

                    attendance = await self.attendance.find_one(
                        {"employee_id": employee_id, "date": date_str}
                    )

                    if not attendance: 
                        work_start_time_config = await self.system_configurations.find_one(
                            {"key": "work_start_time"}
                        )
                        late_grace_period_config = await self.system_configurations.find_one(
                            {"key": "late_grace_period_minutes"}
                        )
                        
                        work_start_time = work_start_time_config.get("value", "09:00") if work_start_time_config else "09:00"
                        late_grace_period = late_grace_period_config.get("value", 15) if late_grace_period_config else 15
                         
                        work_start = datetime.strptime(work_start_time, "%H:%M").time()
                        
                        clock_in_time = log_time.time()
                         
                        is_late = False
                        status = "Present"
                        
                        if clock_in_time > work_start: 
                            clock_in_minutes = clock_in_time.hour * 60 + clock_in_time.minute
                            work_start_minutes = work_start.hour * 60 + work_start.minute
                            minutes_late = clock_in_minutes - work_start_minutes
                            
                            if minutes_late > late_grace_period:
                                is_late = True
                                status = "Late"
                        
                        new_record = {
                            "employee_id": employee_id,
                            "date": date_str,
                            "clock_in": time_str,
                            "device_type": "Biometric",
                            "status": status,
                            "is_late": is_late,
                            "created_at": datetime.utcnow(),
                        }
                        await self.attendance.insert_one(new_record)
                        processed_count += 1
                    else: 
                        clock_in_time = datetime.fromisoformat(attendance["clock_in"])

                        if log_time > clock_in_time:
                            should_update = True
                            if attendance.get("clock_out"):
                                current_clock_out = datetime.fromisoformat(
                                    attendance["clock_out"]
                                )
                                if log_time <= current_clock_out:
                                    should_update = (
                                        False  
                                    )

                            if should_update:
                                work_duration = log_time - clock_in_time
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


repository = Repository()
