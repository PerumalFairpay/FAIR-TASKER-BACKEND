import asyncio
from pymongo import AsyncMongoClient
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database Config
DATABASE_URL = os.getenv("DATABASE_URL", "mongodb://localhost:27017")
if not os.path.exists("/.dockerenv") and "mongodb://db:" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("mongodb://db:", "mongodb://localhost:")

DATABASE_NAME = os.getenv("DATABASE_NAME", "fairpay_hrm_db")

async def delete_sandwich_rule():
    client = AsyncMongoClient(DATABASE_URL)
    db = client[DATABASE_NAME]
    collection = db["system_configurations"]
    
    print(f"Connecting to {DATABASE_URL}...")
    
    result = await collection.delete_one({"key": "sandwich_rule"})
    
    if result.deleted_count > 0:
        print("Successfully deleted 'sandwich_rule' from system_configurations.")
    else:
        print("'sandwich_rule' not found in system_configurations.")
        
    await client.close()

if __name__ == "__main__":
    asyncio.run(delete_sandwich_rule())
