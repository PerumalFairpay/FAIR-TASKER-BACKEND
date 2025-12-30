from app.database import db
from app.models import DepartmentCreate, DepartmentUpdate
from app.utils import normalize
from bson import ObjectId
from datetime import datetime
from typing import List, Optional

class Repository:
    """
    Repository class for all CRUD operations.
    """
    def __init__(self):
        self.db = db
        self.collection = self.db["departments"]

    async def create_department(self, department: DepartmentCreate) -> dict:
        try:
            department_data = department.dict()
            department_data["created_at"] = datetime.utcnow()
            result = await self.collection.insert_one(department_data)
            department_data["id"] = str(result.inserted_id)
            return normalize(department_data)
        except Exception as e:
            raise e

    async def get_departments(self) -> List[dict]:
        try:
            departments = await self.collection.find().to_list(length=None)
            return [normalize(dept) for dept in departments]
        except Exception as e:
            raise e

    async def get_department(self, department_id: str) -> dict:
        try:
            department = await self.collection.find_one({"_id": ObjectId(department_id)})
            return normalize(department)
        except Exception as e:
            raise e

    async def update_department(self, department_id: str, department: DepartmentUpdate) -> dict:
        try:
            update_data = {k: v for k, v in department.dict().items() if v is not None}
            if update_data:
                update_data["updated_at"] = datetime.utcnow()
                await self.collection.update_one(
                    {"_id": ObjectId(department_id)}, {"$set": update_data}
                )
            return await self.get_department(department_id)
        except Exception as e:
            raise e

    async def delete_department(self, department_id: str) -> bool:
        try:
            result = await self.collection.delete_one({"_id": ObjectId(department_id)})
            return result.deleted_count > 0
        except Exception as e:
            raise e

repository = Repository()
