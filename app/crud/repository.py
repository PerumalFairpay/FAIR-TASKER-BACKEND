from app.database import db
from app.models import (
    DepartmentCreate, DepartmentUpdate, 
    EmployeeCreate, EmployeeUpdate, 
    ExpenseCategoryCreate, ExpenseCategoryUpdate, 
    ExpenseCreate, ExpenseUpdate,
    DocumentCategoryCreate, DocumentCategoryUpdate,
    DocumentCreate, DocumentUpdate,
    ClientCreate, ClientUpdate,
    ProjectCreate, ProjectUpdate,
    HolidayCreate, HolidayUpdate,
    AssetCategoryCreate, AssetCategoryUpdate,
    AssetCreate, AssetUpdate,
    BlogCreate, BlogUpdate,
    LeaveTypeCreate, LeaveTypeUpdate,
    LeaveRequestCreate, LeaveRequestUpdate,
    TaskCreate, TaskUpdate, EODReportItem,
    AttendanceCreate, AttendanceUpdate,
    EmployeeChecklistTemplateCreate, EmployeeChecklistTemplateUpdate
)
from app.utils import normalize, get_password_hash
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
        self.attendance = self.db["attendance"]


    async def create_employee(self, employee: EmployeeCreate, profile_picture_path: str = None) -> dict:
        try:
            # Check if user already exists
            existing_user = await self.users.find_one({
                "$or": [{"email": employee.email}, {"employee_id": employee.employee_no_id}]
            })
            if existing_user:
                raise ValueError("User with this email or Employee ID already exists")

            # Prepare Employee Data
            employee_data = employee.dict()
            hashed_password = get_password_hash(employee.password)
            employee_data["password"] = hashed_password 

            # Auto-populate Onboarding Checklist
            if not employee_data.get("onboarding_checklist"):
                default_templates = await self.db["checklist_templates"].find({"type": "Onboarding", "is_default": True}).to_list(length=None)
                checklist = []
                for t in default_templates:
                    checklist.append({
                        "name": t["name"],
                        "status": "Pending",
                        "completed_at": None,
                        "task_id": str(t["_id"]) # Link back to template if useful
                    })
                employee_data["onboarding_checklist"] = checklist
            # Usually we don't store password in Employee table if User table exists, but user asked for "fields... password" in employee table context.
            # I will store it in User table primarily. I'll remove plain password from employee_data before saving if implied, but prompt specifically listed password in payload.
            # I'll keep it hashed in both or just User. Let's put in User and Employee (for safekeeping/redundancy if requested, or just User).
            # Prompt: "if i create a employee it will also store in the user table"
            
            if profile_picture_path:
                employee_data["profile_picture"] = profile_picture_path

            if "documents" in employee_data and employee_data["documents"]:
                 employee_data["documents"] = [doc if isinstance(doc, dict) else doc.dict() for doc in employee_data["documents"]]
            
            employee_data["created_at"] = datetime.utcnow()
            
            # Create User Entry
            # User fields: employee_id, attendance_id, name, email, mobile, hashed_password
            user_data = {
                "employee_id": employee.employee_no_id,
                "attendance_id": employee.employee_no_id, # Defaulting to emp_id
                "name": employee.name,
                "email": employee.email,
                "mobile": employee.mobile,
                "hashed_password": hashed_password,
                "role": employee.role or "employee",
                "created_at": datetime.utcnow()
            }
            
            # Insert Employee
            # Remove plain password from storage if we only want hashed
            if "password" in employee_data:
                del employee_data["password"] # Remove plain text
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
        work_mode: Optional[str] = None
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
                    {"mobile": regex_pattern}
                ]

            skip = (page - 1) * limit
            total_items = await self.employees.count_documents(query)
            
            employees = await self.employees.find(query).skip(skip).limit(limit).to_list(length=limit)
            
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
                "status": 1
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

    async def update_employee(self, employee_id: str, employee: EmployeeUpdate, profile_picture_path: str = None) -> dict:
        try:
            update_data = {k: v for k, v in employee.dict().items() if v is not None}
            if profile_picture_path:
                update_data["profile_picture"] = profile_picture_path

            if "documents" in update_data and update_data["documents"]:
                 update_data["documents"] = [doc if isinstance(doc, dict) else doc.dict() for doc in update_data["documents"]]
                
            if update_data:
                update_data["updated_at"] = datetime.utcnow()
                await self.employees.update_one(
                    {"_id": ObjectId(employee_id)}, {"$set": update_data}
                )
                
                # Also update User if critical fields changed (email, name, mobile)
                user_update = {}
                if "email" in update_data: user_update["email"] = update_data["email"]
                if "name" in update_data: user_update["name"] = update_data["name"]
                if "mobile" in update_data: user_update["mobile"] = update_data["mobile"]
                if "role" in update_data: user_update["role"] = update_data["role"]
                
                if user_update:
                     # Find user by employee_id link
                     current_emp = await self.get_employee(employee_id)
                     if current_emp and "employee_no_id" in current_emp:
                         await self.users.update_one(
                             {"employee_id": current_emp["employee_no_id"]},
                             {"$set": user_update}
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
                    await self.users.delete_one({"employee_id": employee["employee_no_id"]})
            
            return result.deleted_count > 0
        except Exception as e:
            raise e

    async def update_user_permissions(self, employee_id: str, permissions: List[str]) -> bool:
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
                {"$set": {"permissions": permissions, "updated_at": datetime.utcnow()}}
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
                "direct_permissions": direct_permissions # Already IDs
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
            department = await self.departments.find_one({"_id": ObjectId(department_id)})
            return normalize(department)
        except Exception as e:
            raise e

    async def update_department(self, department_id: str, department: DepartmentUpdate) -> dict:
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
            category = await self.expense_categories.find_one({"_id": ObjectId(category_id)})
            return normalize(category)
        except Exception as e:
            raise e

    async def update_expense_category(self, category_id: str, category: ExpenseCategoryUpdate) -> dict:
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
            result = await self.expense_categories.delete_one({"_id": ObjectId(category_id)})
            return result.deleted_count > 0
        except Exception as e:
            raise e


    async def create_expense(self, expense: ExpenseCreate, attachment_path: str = None) -> dict:
        try:
            expense_data = expense.dict()
            if attachment_path:
                expense_data["attachment"] = attachment_path
            
            expense_data["created_at"] = datetime.utcnow()
            result = await self.expenses.insert_one(expense_data)
            expense_data["id"] = str(result.inserted_id)
            return normalize(expense_data)
        except Exception as e:
            raise e

    async def get_expenses(self) -> List[dict]:
        try:
            expenses = await self.expenses.find().to_list(length=None)
            # Normalize and potentially fetch category name if needed, but basic normalize for now
            return [normalize(exp) for exp in expenses]
        except Exception as e:
            raise e

    async def get_expense(self, expense_id: str) -> dict:
        try:
            expense = await self.expenses.find_one({"_id": ObjectId(expense_id)})
            return normalize(expense)
        except Exception as e:
            raise e

    async def update_expense(self, expense_id: str, expense: ExpenseUpdate, attachment_path: str = None) -> dict:
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
            category = await self.document_categories.find_one({"_id": ObjectId(category_id)})
            return normalize(category)
        except Exception as e:
            raise e

    async def update_document_category(self, category_id: str, category: DocumentCategoryUpdate) -> dict:
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
            result = await self.document_categories.delete_one({"_id": ObjectId(category_id)})
            return result.deleted_count > 0
        except Exception as e:
            raise e

    # Document CRUD
    async def create_document(self, document: DocumentCreate, file_path: str = None) -> dict:
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

    async def update_document(self, document_id: str, document: DocumentUpdate, file_path: str = None) -> dict:
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

    async def update_client(self, client_id: str, client: ClientUpdate, logo_path: str = None) -> dict:
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
    async def create_project(self, project: ProjectCreate, logo_path: str = None) -> dict:
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
                if "hashed_password" in emp_norm: del emp_norm["hashed_password"]
                if "password" in emp_norm: del emp_norm["password"]
                employee_map[emp_norm["id"]] = emp_norm
            
            result = []
            for p in projects:
                p_norm = normalize(p)
                p_norm["client"] = client_map.get(str(p_norm.get("client_id")))
                
                # Fetch members details
                p_norm["project_managers"] = [employee_map.get(eid) for eid in p_norm.get("project_manager_ids", []) if eid in employee_map]
                p_norm["team_leaders"] = [employee_map.get(eid) for eid in p_norm.get("team_leader_ids", []) if eid in employee_map]
                p_norm["team_members"] = [employee_map.get(eid) for eid in p_norm.get("team_member_ids", []) if eid in employee_map]
                
                result.append(p_norm)
            
            return result
        except Exception as e:
            raise e

    async def get_project(self, project_id: str) -> dict:
        try:
            project = await self.projects.find_one({"_id": ObjectId(project_id)})
            if not project:
                return None
            
            p_norm = normalize(project)
            
            # Fetch client
            client = await self.clients.find_one({"_id": ObjectId(p_norm.get("client_id"))})
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
                except: continue
                
            employees = await self.employees.find({"_id": {"$in": obj_ids}}).to_list(length=None)
            employee_map = {}
            for e in employees:
                emp_norm = normalize(e)
                if "hashed_password" in emp_norm: del emp_norm["hashed_password"]
                if "password" in emp_norm: del emp_norm["password"]
                employee_map[emp_norm["id"]] = emp_norm
                
            p_norm["project_managers"] = [employee_map.get(eid) for eid in p_norm.get("project_manager_ids", []) if eid in employee_map]
            p_norm["team_leaders"] = [employee_map.get(eid) for eid in p_norm.get("team_leader_ids", []) if eid in employee_map]
            p_norm["team_members"] = [employee_map.get(eid) for eid in p_norm.get("team_member_ids", []) if eid in employee_map]
            
            return p_norm
        except Exception as e:
            raise e

    async def update_project(self, project_id: str, project: ProjectUpdate, logo_path: str = None) -> dict:
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
            category = await self.asset_categories.find_one({"_id": ObjectId(category_id)})
            return normalize(category) if category else None
        except Exception as e:
            raise e

    async def update_asset_category(self, category_id: str, category: AssetCategoryUpdate) -> dict:
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
            result = await self.asset_categories.delete_one({"_id": ObjectId(category_id)})
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
            assets = await self.assets.find().sort("created_at", -1).to_list(length=None)
            
            # Map categories and employees
            categories = await self.asset_categories.find().to_list(length=None)
            employees = await self.employees.find().to_list(length=None)
            
            cat_map = {str(c["_id"]): normalize(c) for c in categories}
            emp_map = {str(e["_id"]): normalize(e) for e in employees} # Mapping by _id (Primary Key)
            
            result = []
            for a in assets:
                a_norm = normalize(a)
                a_norm["category"] = cat_map.get(str(a_norm.get("asset_category_id")))
                a_norm["assigned_to_details"] = emp_map.get(str(a_norm.get("assigned_to")))
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
            category = await self.asset_categories.find_one({"_id": ObjectId(a_norm.get("asset_category_id"))})
            a_norm["category"] = normalize(category) if category else None
            
            # Employee
            assigned_to = a_norm.get("assigned_to")
            if assigned_to:
                try:
                    employee = await self.employees.find_one({"_id": ObjectId(assigned_to)})
                except:
                    employee = None
                a_norm["assigned_to_details"] = normalize(employee) if employee else None
            
            return a_norm
        except Exception as e:
            raise e

    async def update_asset(self, asset_id: str, asset: AssetUpdate, images: List[str] = []) -> dict:
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

    async def manage_asset_assignment(self, asset_id: str, employee_id: Optional[str] = None) -> dict:
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
                {"_id": ObjectId(asset_id)},
                {"$set": update_data}
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
            assets = await self.assets.find({"assigned_to": employee_id}).to_list(length=None)
            
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

    async def get_blogs(self, page: int = 1, limit: int = 10, search: str = None) -> dict:
        try:
            query = {"deleted": False}
            if search:
                query["title"] = {"$regex": search, "$options": "i"}

            total = await self.blogs.count_documents(query)
            cursor = self.blogs.find(query).sort("created_at", -1).skip((page - 1) * limit).limit(limit)
            blogs_list = await cursor.to_list(length=limit)
            
            data = [normalize(b) for b in blogs_list]
            return {
                "data": data,
                "meta": {
                    "current_page": page,
                    "last_page": (total + limit - 1) // limit if limit > 0 else 0,
                    "per_page": limit,
                    "total": total
                }
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
            
            # Recommendations Logic (like in pilot)
            recommendations = []
            if blog_norm.get("category"):
                rec_query = {
                    "deleted": False,
                    "category": blog_norm["category"],
                    "_id": {"$ne": ObjectId(blog_norm["id"])}
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
                {"_id": ObjectId(blog_id)}, {"$set": {"deleted": True, "deleted_at": datetime.utcnow()}}
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
            leave_type = await self.leave_types.find_one({"_id": ObjectId(leave_type_id)})
            return normalize(leave_type) if leave_type else None
        except Exception as e:
            raise e

    async def update_leave_type(self, leave_type_id: str, leave_type: LeaveTypeUpdate) -> dict:
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
    async def create_leave_request(self, leave_request: LeaveRequestCreate, attachment_path: str = None) -> dict:
        try:
            leave_request_data = leave_request.dict()
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
            leave_types = await self.leave_types.find({"status": "Active"}).to_list(length=None)
            current_year = str(datetime.utcnow().year)
            requests = await self.leave_requests.find({
                "employee_id": employee_id,
                "status": "Approved", 
                "start_date": {"$regex": f"^{current_year}"}
            }).to_list(length=None)
            
            balances = []
            for lt in leave_types:
                lt_id = str(lt["_id"])
                used = sum([float(r.get("total_days", 0)) for r in requests if r.get("leave_type_id") == lt_id])
                total_allowed = lt.get("number_of_days", 0)
                balances.append({
                    "leave_type": lt.get("name"),
                    "code": lt.get("code"),
                    "total_allowed": total_allowed,
                    "used": used,
                    "available": max(0, total_allowed - used)
                })
            return balances
        except Exception as e:
            print(f"Error calculating leave balances: {str(e)}")
            return []

    async def get_leave_requests(self, employee_id: str = None, status: str = None) -> List[dict]:
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
                r_norm["leave_type_details"] = lt_map.get(str(r_norm.get("leave_type_id")))
                result.append(r_norm)
                
            return result
        except Exception as e:
            raise e

    async def get_leave_request(self, leave_request_id: str) -> dict:
        try:
            request = await self.leave_requests.find_one({"_id": ObjectId(leave_request_id)})
            if not request:
                return None
            
            r_norm = normalize(request)
            
            # Fetch Employee
            employee = await self.employees.find_one({"_id": ObjectId(r_norm.get("employee_id"))})
            r_norm["employee_details"] = normalize(employee) if employee else None
            
            # Fetch Leave Type
            leave_type = await self.leave_types.find_one({"_id": ObjectId(r_norm.get("leave_type_id"))})
            r_norm["leave_type_details"] = normalize(leave_type) if leave_type else None
            
            return r_norm
        except Exception as e:
            raise e

    async def update_leave_request(self, leave_request_id: str, leave_request: LeaveRequestUpdate, attachment_path: str = None) -> dict:
        try:
            update_data = {k: v for k, v in leave_request.dict().items() if v is not None}
            if attachment_path:
                update_data["attachment"] = attachment_path
                
            if update_data:
                update_data["updated_at"] = datetime.utcnow()
                await self.leave_requests.update_one(
                    {"_id": ObjectId(leave_request_id)}, {"$set": update_data}
                )
            return await self.get_leave_request(leave_request_id)
        except Exception as e:
            raise e

    async def delete_leave_request(self, leave_request_id: str) -> bool:
        try:
            result = await self.leave_requests.delete_one({"_id": ObjectId(leave_request_id)})
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

    async def get_tasks(self, project_id: Optional[str] = None, assigned_to: Optional[str] = None, start_date: Optional[str] = None, date: Optional[str] = None) -> List[dict]:
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
                            {"$or": [
                                {"end_date": {"$gte": date}},
                                {"end_date": None},
                                {"end_date": ""},
                                {"end_date": {"$exists": False}}
                            ]}
                        ]
                    },
                    # 2. Overdue: end_date < overdue_cutoff AND status != Completed
                    {
                        "$and": [
                            {"end_date": {"$lt": overdue_cutoff}},
                            {"status": {"$ne": "Completed"}},
                            {"end_date": {"$ne": None}},
                            {"end_date": {"$ne": ""}}
                        ]
                    }
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
                 if date and norm_task.get("end_date") and norm_task.get("status") != "Completed":
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
                "timestamp": datetime.utcnow()
            }
            
            update_fields = {
                "progress": item.progress,
                "updated_at": datetime.utcnow()
            }

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
                {
                    "$set": update_fields,
                    "$push": {"eod_history": eod_entry}
                }
            )

            updated_task = await self.get_task(task_id)
            results.append(updated_task)
        
        return results

    async def get_eod_reports(self, project_id: Optional[str] = None, assigned_to: Optional[str] = None, date: Optional[str] = None, priority: Optional[str] = None) -> List[dict]:
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
            
            emp_map = {str(e.get("employee_no_id")): e.get("name") for e in employees if e.get("employee_no_id")}
            id_to_name_map = {str(e.get("_id")): e.get("name") for e in employees}
            proj_map = {str(p.get("_id")): p.get("name") for p in projects}

            reports = []
            for task in tasks:
                task_norm = normalize(task)
                proj_name = proj_map.get(task_norm.get("project_id"), "Unknown Project")
                
                # assigned_to is a list of IDs. We'll take the first one or join them
                assigned_ids = task_norm.get("assigned_to", [])
                assigned_names = [emp_map.get(eid) or id_to_name_map.get(eid) or eid for eid in assigned_ids]
                employee_display = ", ".join(filter(None, assigned_names))

                for entry in task_norm.get("eod_history", []):
                    if date and entry.get("date") != date:
                        continue
                        
                    report_entry = {
                        "task_id": task_norm["id"],
                        "task_name": task_norm.get("task_name") or task_norm.get("name") or "Untitled Task",
                        "project_id": task_norm.get("project_id"),
                        "project_name": proj_name,
                        "assigned_to": task_norm.get("assigned_to", []),
                        "employee_name": employee_display,
                        **entry
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
                    operations.append(UpdateOne(
                        {"employee_id": emp_id, "date": dt},
                        {"$set": {**rec, "updated_at": datetime.utcnow()}},
                        upsert=True
                    ))
            
            if operations:
                result = await self.attendance.bulk_write(operations)
                return {
                    "success": True, 
                    "matched": result.matched_count,
                    "upserted": result.upserted_count,
                    "modified": result.modified_count
                }
            
            return {"success": True, "count": 0}
        except Exception as e:
            raise e

    # Attendance CRUD
    async def clock_in(self, attendance: AttendanceCreate, employee_id: str) -> dict:
        try:
            # Check if already clocked in for this date
            existing = await self.attendance.find_one({
                "employee_id": employee_id,
                "date": attendance.date
            })
            if existing:
                raise ValueError("Already clocked in for this date")

            attendance_data = attendance.dict()
            attendance_data["employee_id"] = employee_id
            attendance_data["created_at"] = datetime.utcnow()
            attendance_data["status"] = "Present"
            
            result = await self.attendance.insert_one(attendance_data)
            attendance_data["id"] = str(result.inserted_id)
            return normalize(attendance_data)
        except Exception as e:
            raise e

    async def clock_out(self, attendance: AttendanceUpdate, employee_id: str, date: str) -> dict:
        try:
            existing = await self.attendance.find_one({
                "employee_id": employee_id,
                "date": date
            })
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
                     start_dt = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
                     end_dt = datetime.fromisoformat(end_str.replace('Z', '+00:00'))
                     duration = (end_dt - start_dt).total_seconds() / 3600
                     update_data["total_work_hours"] = round(duration, 2)
                except:
                     pass # Fallback or skip if format issues
            
            update_data["updated_at"] = datetime.utcnow()
            
            await self.attendance.update_one(
                {"_id": existing["_id"]},
                {"$set": update_data}
            )
            
            updated_record = await self.attendance.find_one({"_id": existing["_id"]})
            return normalize(updated_record)
        except Exception as e:
            raise e

    async def get_employee_attendance(self, employee_id: str, start_date: str = None, end_date: str = None) -> dict:
        try:
            # If no dates provided, default to current month
            if not start_date or not end_date:
                now = datetime.utcnow()
                start_date = now.replace(day=1).strftime("%Y-%m-%d")
                # Last day of month
                if now.month == 12:
                    last_day = now.replace(year=now.year + 1, month=1, day=1) - timedelta(days=1)
                else:
                    last_day = now.replace(month=now.month + 1, day=1) - timedelta(days=1)
                end_date = last_day.strftime("%Y-%m-%d")
            
            return await self.get_all_attendance(start_date=start_date, end_date=end_date, employee_id=employee_id)
        except Exception as e:
            raise e

    async def get_all_attendance(self, date: str = None, start_date: str = None, end_date: str = None, employee_id: str = None, status: str = None) -> dict:
        try:
            query = {}
            if date:
                query["date"] = date
            elif start_date and end_date:
                query["date"] = {"$gte": start_date, "$lte": end_date}
            elif start_date:
                query["date"] = {"$gte": start_date}
                
            if employee_id:
                query["employee_id"] = employee_id
                
            # Internal status check for the attendance collection
            db_status = status if status in ["Present", "Late", "Overtime"] else None
            if db_status:
                query["status"] = db_status
                
            records = await self.attendance.find(query).sort("date", -1).to_list(length=None)
            
            # Fetch employee details for mapping
            employees = await self.employees.find().to_list(length=None)
            emp_map = {str(e.get("employee_no_id")): normalize(e) for e in employees if e.get("employee_no_id")}
            id_to_emp_map = {str(e["_id"]): normalize(e) for e in employees}
            
            # Identify target date range for virtual record generation
            target_dates = []
            if date:
                target_dates = [date]
            elif start_date and end_date:
                s_dt = datetime.strptime(start_date, "%Y-%m-%d")
                e_dt = datetime.strptime(end_date, "%Y-%m-%d")
                curr = s_dt
                while curr <= e_dt:
                    target_dates.append(curr.strftime("%Y-%m-%d"))
                    curr += timedelta(days=1)
            else:
                # Default to today if no date filter is applied
                target_dates = [datetime.utcnow().strftime("%Y-%m-%d")]
            
            # If we are looking for specific virtual statuses or no status filter, 
            # we need to consider holidays and leaves.
            include_virtual = not status or status in ["Holiday", "Leave", "Absent"]

            result = []
            attendance_map = {} # (employee_id, date)
            
            for r in records:
                r_norm = normalize(r)
                emp_details = emp_map.get(r_norm.get("employee_id"))
                if emp_details:
                    if "hashed_password" in emp_details: del emp_details["hashed_password"]
                    if "password" in emp_details: del emp_details["password"]
                r_norm["employee_details"] = emp_details
                result.append(r_norm)
                attendance_map[(r_norm.get("employee_id"), r_norm.get("date"))] = r_norm

            if target_dates and include_virtual:
                # Fetch holidays and leaves for the target range
                holidays = await self.holidays.find({"date": {"$in": target_dates}}).to_list(length=None)
                holiday_map = {h["date"]: h["name"] for h in holidays}
                
                leave_query = {"status": "Approved"}
                # Leaves overlap if start_date <= target_date <= end_date
                # We fetch all approved leaves that could possibly overlap
                approved_leaves = await self.leave_requests.find(leave_query).to_list(length=None)
                
                today_str = datetime.utcnow().strftime("%Y-%m-%d")
                
                # Determine which employees to check
                employees_to_check = []
                if employee_id:
                    emp = emp_map.get(employee_id)
                    if emp: employees_to_check = [emp]
                else:
                    employees_to_check = list(emp_map.values())

                for dt in target_dates:
                    h_name = holiday_map.get(dt)
                    for emp in employees_to_check:
                        emp_no_id = emp.get("employee_no_id")
                        if (emp_no_id, dt) in attendance_map:
                            continue
                        
                        virt_status = None
                        notes = None
                        
                        if h_name:
                            virt_status = "Holiday"
                            notes = h_name
                        else:
                            # Check if employee has an approved leave for this date
                            for leaf in approved_leaves:
                                if str(leaf.get("employee_id")) == str(emp.get("id")):
                                    if leaf.get("start_date") <= dt <= leaf.get("end_date"):
                                        virt_status = "Leave"
                                        notes = leaf.get("reason")
                                        break
                            
                            if not virt_status and dt <= today_str:
                                # It's a past/current date with no attendance, holiday, or leave.
                                # Check if it's a weekend (optional but helpful)
                                dt_parsed = datetime.strptime(dt, "%Y-%m-%d")
                                if dt_parsed.weekday() < 5: # Mon-Fri
                                    virt_status = "Absent"
                        
                        if virt_status:
                            # If status filter is active, only include if it matches
                            if status and status != virt_status:
                                continue
                            
                            result.append({
                                "id": f"v_{emp_no_id}_{dt}",
                                "employee_id": emp_no_id,
                                "date": dt,
                                "status": virt_status,
                                "notes": notes,
                                "employee_details": emp,
                                "clock_in": None,
                                "clock_out": None,
                                "total_work_hours": 0.0
                            })
            
            result.sort(key=lambda x: (x.get("date", ""), (x.get("employee_details") or {}).get("name", "")), reverse=True)
            
            # Calculate metrics
            metrics = {
                "total_records": len(result),
                "present": len([r for r in result if r.get("status") == "Present"]),
                "absent": len([r for r in result if r.get("status") == "Absent"]),
                "leave": len([r for r in result if r.get("status") == "Leave"]),
                "holiday": len([r for r in result if r.get("status") == "Holiday"]),
                "late": len([r for r in result if r.get("status") == "Late"]),
                "overtime": len([r for r in result if r.get("status") == "Overtime"]),
                "total_work_hours": round(sum([float(r.get("total_work_hours") or 0) for r in result]), 2),
            }
            metrics["avg_work_hours"] = round(metrics["total_work_hours"] / metrics["present"], 2) if metrics["present"] > 0 else 0
            
            return {"data": result, "metrics": metrics}
        except Exception as e:
            raise e

    # Checklist Template CRUD
    async def create_checklist_template(self, template: EmployeeChecklistTemplateCreate) -> dict:
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

    async def update_checklist_template(self, template_id: str, template: EmployeeChecklistTemplateUpdate) -> dict:
        try:
            update_data = {k: v for k, v in template.dict().items() if v is not None}
            if update_data:
                update_data["updated_at"] = datetime.utcnow()
                await self.db["checklist_templates"].update_one(
                    {"_id": ObjectId(template_id)}, {"$set": update_data}
                )
            # Find and return
            t = await self.db["checklist_templates"].find_one({"_id": ObjectId(template_id)})
            return normalize(t) if t else None
        except Exception as e:
            raise e

    async def delete_checklist_template(self, template_id: str) -> bool:
        try:
            result = await self.db["checklist_templates"].delete_one({"_id": ObjectId(template_id)})
            return result.deleted_count > 0
        except Exception as e:
            raise e

repository = Repository()
