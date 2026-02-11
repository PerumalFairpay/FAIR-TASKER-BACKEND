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

permissions_data = [ 
    # Employee Management -seeder updated
    {"name": "View Employees", "slug": "employee:view", "module": "Employee", "description": "Can see the list of all staff members"},
    {"name": "Submit Employee", "slug": "employee:submit", "module": "Employee", "description": "Create, edit, and delete employee records"},
    
    # Roles & Permissions -seeder updated
    {"name": "View Roles", "slug": "role:view", "module": "Access Control", "description": "View system roles"},
    {"name": "Submit Roles", "slug": "role:submit", "module": "Access Control", "description": "Create, Edit, and Delete system roles"},
    {"name": "View Permissions", "slug": "permission:view", "module": "Access Control", "description": "View available permissions"},
    {"name": "Submit Permissions", "slug": "permission:submit", "module": "Access Control", "description": "Manage permissions list"},
     
    # Leave Management -seeder updated
    {"name": "View Leave Requests", "slug": "leave:view", "module": "Leave", "description": "See leave applications"},
    {"name": "Approve Leaves", "slug": "leave:approve", "module": "Leave", "description": "Approve or reject team leave requests"},
     
    # Project Management -seeder updated
    {"name": "View Projects", "slug": "project:view", "module": "Projects", "description": "Access project details and status"},
    {"name": "Submit Project", "slug": "project:submit", "module": "Projects", "description": "Create and manage project lifecycles"},
    
    # expense -seeder updated
    {"name": "View Expenses", "slug": "expense:view", "module": "Finance", "description": "View expense records"},
    {"name": "Submit Expense", "slug": "expense:submit", "module": "Finance", "description": "Submit personal expense claims"},
    {"name": "Approve Expenses", "slug": "expense:approve", "module": "Finance", "description": "Financial approval of expense claims"},
    
    # Assets -seeder updated
    {"name": "View Assets", "slug": "asset:view", "module": "Assets", "description": "View list of assigned or available assets"},
    {"name": "Submit Asset Request", "slug": "asset:submit", "module": "Assets", "description": "Request new assets or return existing ones"},
    
    # Document Management -seeder updated
    {"name": "View Documents", "slug": "document:view", "module": "Documents", "description": "View company documents"},
    {"name": "Submit Document", "slug": "document:submit", "module": "Documents", "description": "Upload and manage documents"},
     
    # Navigation (Sidebar) Permissions
    {"name": "Nav Milestone", "slug": "nav:milestone", "module": "Navigation", "description": "View Milestone Roadmap menu in sidebar"},
]

async def seed_permissions():
    client = AsyncMongoClient(DATABASE_URL)
    db = client[DATABASE_NAME]
    collection = db["permissions"]
    
    print(f"Connecting to {DATABASE_URL}...")

    for perm in permissions_data:
        # Update if exists (by slug), insert if not
        result = await collection.update_one(
            {"slug": perm["slug"]},
            {"$setOnInsert": perm},
            upsert=True
        )
        if result.upserted_id:
            print(f"Inserted: {perm['slug']}")
        else:
            print(f"Skipped (Exists): {perm['slug']}")
            
    print("\nPermissions seeding completed.")

    # Seed Roles
    roles_collection = db["roles"]
    
    # Get all permission slugs to IDs mapping
    cursor = collection.find({})
    perm_map = {}
    async for p in cursor:
        perm_map[p["slug"]] = str(p["_id"])

    roles_data = [
        {
            "name": "admin",
            "description": "Full system access",
            "permissions": list(perm_map.values()) # Admin gets everything
        },
        {
            "name": "employee",
            "description": "Standard employee access",
            "permissions": [  
                perm_map.get("project:view"),
                perm_map.get("expense:submit"),
                perm_map.get("asset:view"),
                perm_map.get("employee:view"), 
                perm_map.get("document:view"),
                
                # Nav Permissions
                # perm_map.get("nav:milestone"),
            ]
        }
    ]

    # Filter out None values from permissions
    for role in roles_data:
        role["permissions"] = [p for p in role["permissions"] if p]

    for role in roles_data:
        await roles_collection.update_one(
            {"name": role["name"]},
            {"$setOnInsert": role},
            upsert=True
        )
        print(f"Role checked/seeded: {role['name']}")
            
    print("\nAll seeding completed successfully!")
    await client.close()

if __name__ == "__main__":
    asyncio.run(seed_permissions())
