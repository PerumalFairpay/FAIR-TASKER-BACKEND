import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database Config
DATABASE_URL = os.getenv("DATABASE_URL", "mongodb://localhost:27017")

# Only replace 'db' with 'localhost' if we are NOT running inside a docker container
if not os.path.exists('/.dockerenv') and "mongodb://db:" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("mongodb://db:", "mongodb://localhost:")
    
DATABASE_NAME = os.getenv("DATABASE_NAME", "fair_tasker_db")

leave_types_data = [
    {
        "name": "Casual Leave",
        "type": "Paid",
        "code": "CL",
        "status": "Active",
        "number_of_days": 12,
        "monthly_allowed": 1
    },
    {
        "name": "Sick Leave",
        "type": "Paid",
        "code": "SL",
        "status": "Active",
        "number_of_days": 10,
        "monthly_allowed": 1
    },
    {
        "name": "Earned Leave",
        "type": "Paid",
        "code": "EL",
        "status": "Active",
        "number_of_days": 15,
        "monthly_allowed": 2
    },
    {
        "name": "Loss of Pay",
        "type": "Unpaid",
        "code": "LOP",
        "status": "Active",
        "number_of_days": 365,
        "monthly_allowed": 0
    },
    {
        "name": "Maternity Leave",
        "type": "Paid",
        "code": "ML",
        "status": "Active",
        "number_of_days": 180,
        "monthly_allowed": 0
    },
    {
        "name": "Paternity Leave",
        "type": "Paid",
        "code": "PL",
        "status": "Active",
        "number_of_days": 5,
        "monthly_allowed": 0
    },
    {
        "name": "Compensatory Off",
        "type": "Paid",
        "code": "CO",
        "status": "Active",
        "number_of_days": 0, # Usually accrued
        "monthly_allowed": 0
    },
    {
        "name": "Permission",
        "type": "Paid",
        "code": "PER",
        "status": "Active",
        "number_of_days": 12,
        "monthly_allowed": 2
    }
]

async def seed_leave_types():
    client = AsyncIOMotorClient(DATABASE_URL)
    db = client[DATABASE_NAME]
    collection = db["leave_types"]
    
    print(f"Connecting to {DATABASE_URL}...")

    for lt in leave_types_data:
        # Update if exists (by code), insert if not
        result = await collection.update_one(
            {"code": lt["code"]},
            {"$set": lt},
            upsert=True
        )
        if result.upserted_id:
            print(f"Inserted: {lt['name']} ({lt['code']})")
        else:
            print(f"Updated: {lt['name']} ({lt['code']})")
            
    print("\nLeave Types seeding completed.")
    client.close()

if __name__ == "__main__":
    asyncio.run(seed_leave_types())
