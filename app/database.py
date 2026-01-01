from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import DATABASE_URL, DATABASE_NAME

client = AsyncIOMotorClient(DATABASE_URL)
db = client[DATABASE_NAME]
users_collection = db["users"]
roles_collection = db["roles"]
tasks_collection = db["tasks"]
attendance_collection = db["attendance"]

