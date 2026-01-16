import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv
from app.utils import get_password_hash
from datetime import datetime

# Load environment variables
load_dotenv()

# Database Config
DATABASE_URL = os.getenv("DATABASE_URL", "mongodb://localhost:27017")

# Only replace 'db' with 'localhost' if we are NOT running inside a docker container
if not os.path.exists('/.dockerenv') and "mongodb://db:" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("mongodb://db:", "mongodb://localhost:")
    
DATABASE_NAME = os.getenv("DATABASE_NAME", "fairpay_hrm_db")

admin_data = {
    "email": "admin@fairpay.com",
    "password": "admin123", # Will be hashed
    "name": "Super Admin",
    "first_name": "Super",
    "last_name": "Admin",
    "role": "admin",
    "employee_id": "ADMIN001", # Ensure this matches schema requirements if any
    "employee_no_id": "ADMIN001",
    "mobile": "0000000000",
    "status": "Active",
    "permissions": [], # Admin role usually implies all permissions, but explicitly empty here as role handles it
    "created_at": datetime.utcnow(),
    "is_verified": True
}

async def seed_admin():
    client = AsyncIOMotorClient(DATABASE_URL)
    db = client[DATABASE_NAME]
    users_collection = db["users"]
    
    print(f"Connecting to {DATABASE_URL}...")
    print(f"Target Database: {DATABASE_NAME}")

    # Check if admin already exists
    existing_admin = await users_collection.find_one({"email": admin_data["email"]})
    
    if existing_admin:
        print(f"Admin user already exists: {admin_data['email']}")
    else:
        # Pydantic model validation would happen in API, here we manually construct
        # We need to ensure we hash the password
        hashed_pwd = get_password_hash(admin_data["password"])
        
        new_admin = admin_data.copy()
        new_admin["hashed_password"] = hashed_pwd
        del new_admin["password"] # Remove plain text password
        
        # Add necessary default fields that might be expected
        new_admin["attendance_id"] = "ADMIN001" 
        
        result = await users_collection.insert_one(new_admin)
        print(f"Admin user created successfully with ID: {result.inserted_id}")
        print(f"Email: {admin_data['email']}")
        print(f"Password: {admin_data['password']}")

    client.close()

if __name__ == "__main__":
    asyncio.run(seed_admin())
