import asyncio
import sys
import os

# Add the parent directory to sys.path to import app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
import os

# Load .env file
load_dotenv()

# Override DATABASE_URL if running locally and it points to 'db'
db_url = os.getenv("DATABASE_URL")
if db_url and "mongodb://db:" in db_url:
    os.environ["DATABASE_URL"] = db_url.replace("mongodb://db:", "mongodb://localhost:")
    print(f"Updated DATABASE_URL to: {os.environ['DATABASE_URL']}")

from app.database import db, employees_collection, employee_documents_collection
from bson import ObjectId
from datetime import datetime

async def migrate():
    print("Connecting to database...")
    print("Starting migration of employee documents...")
    
    # Fetch all employees
    employees = await employees_collection.find({}).to_list(length=None)
    print(f"Found {len(employees)} employees.")
    
    migrated_count = 0
    skipped_count = 0
    
    for emp in employees:
        emp_id = str(emp["_id"])
        documents = emp.get("documents", [])
        
        if not documents:
            skipped_count += 1
            continue
            
        print(f"Migrating {len(documents)} documents for employee {emp.get('name')} ({emp_id})...")
        
        for doc in documents:
            # Check if document already exists in separate collection to avoid duplicates
            existing = await employee_documents_collection.find_one({
                "employee_id": emp_id,
                "document_proof": doc.get("document_proof")
            })
            
            if not existing:
                doc_to_insert = {
                    "employee_id": emp_id,
                    "document_name": doc.get("document_name"),
                    "document_proof": doc.get("document_proof"),
                    "file_type": doc.get("file_type"),
                    "created_at": emp.get("created_at", datetime.utcnow()),
                    "updated_at": datetime.utcnow()
                }
                await employee_documents_collection.insert_one(doc_to_insert)
                migrated_count += 1
        
        # Optional: Remove the documents field from the employee record
        await employees_collection.update_one(
            {"_id": emp["_id"]},
            {"$unset": {"documents": ""}}
        )
        
    print(f"Migration finished.")
    print(f"Total documents migrated: {migrated_count}")
    print(f"Employees processed: {len(employees)}")
    print(f"Employees with no documents: {skipped_count}")

if __name__ == "__main__":
    asyncio.run(migrate())
