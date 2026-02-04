from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import DATABASE_URL, DATABASE_NAME

client = AsyncIOMotorClient(DATABASE_URL)
db = client[DATABASE_NAME]
users_collection = db["users"]
roles_collection = db["roles"]
permissions_collection = db["permissions"]
tasks_collection = db["tasks"]
attendance_collection = db["attendance"]
employees_collection = db["employees"]
checklist_templates_collection = db["checklist_templates"]
system_configurations_collection = db["system_configurations"]
nda_requests_collection = db["nda_requests"]
