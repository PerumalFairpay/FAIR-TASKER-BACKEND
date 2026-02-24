import asyncio
from pymongo import AsyncMongoClient
import os
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()

# Database Config
DATABASE_URL = os.getenv("DATABASE_URL", "mongodb://localhost:27017")

# Only replace 'db' with 'localhost' if we are NOT running inside a docker container
if not os.path.exists("/.dockerenv") and "mongodb://db:" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("mongodb://db:", "mongodb://localhost:")

DATABASE_NAME = os.getenv("DATABASE_NAME", "fairpay_hrm_db")

settings_data = [
    {
        "key": "company_name",
        "label": "Company Name",
        "value": "FairPay",
        "input_type": "text",
        "group": "General",
        "is_public": True,
    },
    {
        "key": "contact_email",
        "label": "Contact Email",
        "value": "",
        "input_type": "text",
        "group": "General",
        "is_public": False,
    },
    
    {
        "key": "work_start_time",
        "label": "Work Start Time",
        "value": "09:00",
        "input_type": "time",
        "group": "Attendance",
        "is_public": True,
    },
    {
        "key": "work_end_time",
        "label": "Work End Time",
        "value": "18:00",
        "input_type": "time",
        "group": "Attendance",
        "is_public": True,
    },
    {
        "key": "late_grace_period_minutes",
        "label": "Late Grace Period (Minutes)",
        "value": 15,
        "input_type": "number",
        "group": "Attendance",
        "is_public": True,
    },
    {
        "key": "work_days",
        "label": "Work Days",
        "value": ["Mon", "Tue", "Wed", "Thu", "Fri","sat"],
        "input_type": "multiselect",
        "options": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        "group": "Attendance",
        "is_public": False,
    },
]


async def seed_settings():
    client = AsyncMongoClient(DATABASE_URL)
    db = client[DATABASE_NAME]
    collection = db["system_configurations"]

    print(f"Connecting to {DATABASE_URL}...")

    for setting in settings_data:
        # Update if exists (by key), insert if not
        result = await collection.update_one(
            {"key": setting["key"]},
            {"$setOnInsert": {**setting, "created_at": datetime.utcnow()}},
            upsert=True,
        )
        if result.upserted_id:
            print(f"Inserted: {setting['key']}")
        else:
            print(f"Skipped (Exists): {setting['key']}")

    print("\nSettings seeding completed successfully!")
    await client.close()


if __name__ == "__main__":
    asyncio.run(seed_settings())
