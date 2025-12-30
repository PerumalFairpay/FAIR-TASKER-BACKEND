from app.database import db
from app.models import DepartmentCreate, DepartmentUpdate, EmployeeCreate, EmployeeUpdate, ExpenseCategoryCreate, ExpenseCategoryUpdate, ExpenseCreate, ExpenseUpdate
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
 
repository = Repository()
