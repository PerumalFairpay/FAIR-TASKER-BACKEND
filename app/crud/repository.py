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
    TaskCreate, TaskUpdate, EODReportItem
)
from app.utils import normalize, get_password_hash
from bson import ObjectId
from datetime import datetime
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

    async def create_employee(self, employee: EmployeeCreate, profile_picture_path: str = None, document_proof_path: str = None) -> dict:
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
            employee_data["password"] = hashed_password # storing hashed in employee too? User prompt implies it.
            # Usually we don't store password in Employee table if User table exists, but user asked for "fields... password" in employee table context.
            # I will store it in User table primarily. I'll remove plain password from employee_data before saving if implied, but prompt specifically listed password in payload.
            # I'll keep it hashed in both or just User. Let's put in User and Employee (for safekeeping/redundancy if requested, or just User).
            # Prompt: "if i create a employee it will also store in the user table"
            
            if profile_picture_path:
                employee_data["profile_picture"] = profile_picture_path
            if document_proof_path:
                employee_data["document_proof"] = document_proof_path
            
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

    async def get_employees(self) -> List[dict]:
        try:
            employees = await self.employees.find().to_list(length=None)
            # Remove sensitive data like password
            for emp in employees:
                if "hashed_password" in emp:
                    del emp["hashed_password"]
                if "password" in emp:
                    del emp["password"]
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

    async def update_employee(self, employee_id: str, employee: EmployeeUpdate, profile_picture_path: str = None, document_proof_path: str = None) -> dict:
        try:
            update_data = {k: v for k, v in employee.dict().items() if v is not None}
            if profile_picture_path:
                update_data["profile_picture"] = profile_picture_path
            if document_proof_path:
                update_data["document_proof"] = document_proof_path
                
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
            assets = await self.assets.find().to_list(length=None)
            
            # Map categories and employees
            categories = await self.asset_categories.find().to_list(length=None)
            employees = await self.employees.find().to_list(length=None)
            
            cat_map = {str(c["_id"]): normalize(c) for c in categories}
            emp_map = {str(e["employee_no_id"]): normalize(e) for e in employees} # Mapping by employee_no_id as per assigned_to field
            
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
                employee = await self.employees.find_one({"employee_no_id": assigned_to})
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

    async def get_leave_requests(self, employee_id: str = None) -> List[dict]:
        try:
            query = {}
            if employee_id:
                query["employee_id"] = employee_id

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

    async def get_tasks(self, project_id: Optional[str] = None, assigned_to: Optional[str] = None, start_date: Optional[str] = None) -> List[dict]:
        try:
            query = {}
            if project_id:
                query["project_id"] = project_id
            if assigned_to:
                # Matches if employee ID is in the list
                query["assigned_to"] = assigned_to 
            if start_date:
                query["start_date"] = start_date
            
            tasks = await self.tasks.find(query).to_list(length=None)
            return [normalize(t) for t in tasks]
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
                "status": item.status,
                "progress": item.progress,
                "summary": item.eod_summary,
                "timestamp": datetime.utcnow()
            }
            
            update_fields = {
                "status": "Moved" if item.move_to_tomorrow else item.status,
                "progress": item.progress,
                "updated_at": datetime.utcnow()
            }

            # Add to history
            await self.tasks.update_one(
                {"_id": ObjectId(task_id)},
                {
                    "$set": update_fields,
                    "$push": {"eod_history": eod_entry},
                    "$addToSet": {"attachments": {"$each": item.new_attachments}}
                }
            )

            # Check if we need to move to tomorrow
            if item.move_to_tomorrow:
                # Calculate tomorrow's date
                from datetime import timedelta
                try:
                    end_date_str = existing_task.get("end_date")
                    if end_date_str:
                        current_end_dt = datetime.strptime(end_date_str, "%Y-%m-%d")
                        tomorrow_dt = current_end_dt + timedelta(days=1)
                    else:
                        tomorrow_dt = datetime.utcnow() + timedelta(days=1)
                    tomorrow_str = tomorrow_dt.strftime("%Y-%m-%d")
                except:
                    # Fallback to today + 1 if format is weird or missing
                    tomorrow_str = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d")

                new_task_data = {
                    "project_id": existing_task.get("project_id"),
                    "task_name": existing_task.get("task_name") or existing_task.get("name") or "Untitled Task",
                    "description": existing_task.get("description"),
                    "start_date": tomorrow_str,
                    "end_date": tomorrow_str,
                    "priority": existing_task.get("priority", "Medium"),
                    "assigned_to": existing_task.get("assigned_to", []),
                    "attachments": existing_task.get("attachments", []) + (item.new_attachments or []),
                    "tags": existing_task.get("tags", []),
                    "status": "Todo",
                    "progress": item.progress, # Carrying forward the progress
                    "parent_task_id": task_id,
                    "eod_history": [],
                    "created_at": datetime.utcnow()
                }
                result = await self.tasks.insert_one(new_task_data)
                new_task_data["id"] = str(result.inserted_id)
                results.append(normalize(new_task_data))
            else:
                updated_task = await self.get_task(task_id)
                results.append(updated_task)
        
        return results

    async def get_eod_reports(self, project_id: Optional[str] = None, assigned_to: Optional[str] = None, date: Optional[str] = None) -> List[dict]:
        try:
            query = {"eod_history": {"$exists": True, "$not": {"$size": 0}}}
            if project_id:
                query["project_id"] = project_id
            if assigned_to:
                query["assigned_to"] = assigned_to
            
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

repository = Repository()
