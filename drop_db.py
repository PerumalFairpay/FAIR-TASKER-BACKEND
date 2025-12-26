from motor.motor_asyncio import AsyncIOMotorClient
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "fair_tasker_db")

async def drop_database():
    print(f"Connecting to {MONGO_URL}...")
    client = AsyncIOMotorClient(MONGO_URL)
    print(f"Dropping database: {DB_NAME}...")
    await client.drop_database(DB_NAME)
    print("Database dropped successfully.")

if __name__ == "__main__":
    asyncio.run(drop_database())
