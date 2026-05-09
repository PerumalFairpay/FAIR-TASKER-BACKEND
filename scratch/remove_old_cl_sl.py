import asyncio
from pymongo import AsyncMongoClient
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "mongodb://localhost:27017")
if not os.path.exists('/.dockerenv') and "mongodb://db:" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("mongodb://db:", "mongodb://localhost:")
DATABASE_NAME = os.getenv("DATABASE_NAME", "fairpay_hrm_db")

async def remove_old_leave_type():
    client = AsyncMongoClient(DATABASE_URL)
    db = client[DATABASE_NAME]
    collection = db["leave_types"]
    
    result = await collection.delete_one({"code": "CL_SL"})
    if result.deleted_count > 0:
        print("Successfully removed old 'CL_SL' leave type.")
    else:
        print("'CL_SL' leave type not found or already removed.")
        
    await client.close()

if __name__ == "__main__":
    asyncio.run(remove_old_leave_type())
