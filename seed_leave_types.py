import asyncio
from pymongo import AsyncMongoClient
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database Config
DATABASE_URL = os.getenv("DATABASE_URL", "mongodb://localhost:27017")

# Only replace 'db' with 'localhost' if we are NOT running inside a docker container
if not os.path.exists('/.dockerenv') and "mongodb://db:" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("mongodb://db:", "mongodb://localhost:")
    
DATABASE_NAME = os.getenv("DATABASE_NAME", "fairpay_hrm_db")

leave_types_data = [
    {
        "name": "Earned Leave",
        "type": "Paid",
        "code": "EL",
        "status": "Active",
        "number_of_days": 6,
        "monthly_allowed": 0, # Usually taken in blocks, but accrued monthly
        "can_carry_forward": False,
        "can_encash": True,
        "probation_period_months": 3
    },
    {
        "name": "Casual & Sick Leave",
        "type": "Paid",
        "code": "CL_SL",
        "status": "Active",
        "number_of_days": 12,
        "monthly_allowed": 2, # Max 2 consecutive without approval
        "can_carry_forward": False,
        "can_encash": False
    },
    {
        "name": "Loss of Pay",
        "type": "Unpaid",
        "code": "LOP",
        "status": "Active",
        "number_of_days": 365, # Unlimited theoretically
        "monthly_allowed": 0
    },
    {
        "name": "Maternity Leave",
        "type": "Paid",
        "code": "ML",
        "status": "Active",
        "number_of_days": 182, # 26 weeks
        "monthly_allowed": 0,
        "min_service_days": 80
    },
    {
        "name": "Paternity Leave",
        "type": "Paid",
        "code": "PTL",
        "status": "Active",
        "number_of_days": 3,
        "monthly_allowed": 0
    },
    {
        "name": "Marriage Leave",
        "type": "Paid",
        "code": "MRL",
        "status": "Active",
        "number_of_days": 6,
        "monthly_allowed": 0
    },
    {
        "name": "Bereavement Leave",
        "type": "Paid",
        "code": "BL",
        "status": "Active",
        "number_of_days": 3,
        "monthly_allowed": 0
    },
    {
        "name": "Permission",
        "type": "Paid",
        "code": "PER",
        "status": "Active",
        "number_of_days": 0, # Tracked in hours/instances
        "monthly_allowed": 2,
        "allowed_hours": 1.5,
        "can_carry_forward": False
    }
]

async def seed_leave_types():
    client = AsyncMongoClient(DATABASE_URL)
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
    await client.close()

if __name__ == "__main__":
    asyncio.run(seed_leave_types())
