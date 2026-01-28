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
    
DATABASE_NAME = os.getenv("DATABASE_NAME", "fairpay_hrm_db")

permissions_data = [
    # Dashboard
    {"name": "View Dashboard", "slug": "dashboard:view", "module": "Dashboard", "description": "Access to the main dashboard statistics and charts"},
    
    # Employee Management
    {"name": "View Employees", "slug": "employee:view", "module": "Employee", "description": "Can see the list of all staff members"},
    {"name": "Create Employee", "slug": "employee:create", "module": "Employee", "description": "Can add new employees to the system"},
    {"name": "Edit Employee", "slug": "employee:edit", "module": "Employee", "description": "Can update existing employee details"},
    {"name": "Delete Employee", "slug": "employee:delete", "module": "Employee", "description": "Can remove employees from the system"},
    
    # Roles & Permissions
    {"name": "Manage Roles", "slug": "role:manage", "module": "Access Control", "description": "Create, Edit, and Delete system roles"},
    {"name": "Manage Permissions", "slug": "permission:manage", "module": "Access Control", "description": "Complete control over the permissions list"},
    
    # Department
    {"name": "Manage Departments", "slug": "department:manage", "module": "Organization", "description": "Manage company structural hierarchy"},
    
    # Attendance
    {"name": "View All Attendance", "slug": "attendance:view_all", "module": "Attendance", "description": "View records for all employees (Admin view)"},
    {"name": "View Own Attendance", "slug": "attendance:view_self", "module": "Attendance", "description": "View only personal personal attendance records"},
    {"name": "Manage Attendance", "slug": "attendance:manage", "module": "Attendance", "description": "Manually adjust or approve attendance logs"},
    
    # Leave Management
    {"name": "View Leave Requests", "slug": "leave:view", "module": "Leave", "description": "See leave applications"},
    {"name": "Apply for Leave", "slug": "leave:apply", "module": "Leave", "description": "Submit personal leave requests"},
    {"name": "Approve Leaves", "slug": "leave:approve", "module": "Leave", "description": "Approve or reject team leave requests"},
    {"name": "Manage Leave Types", "slug": "leave_type:manage", "module": "Leave", "description": "Configure leave types (Sick, Casual, etc.)"},
    
    # Task Management
    {"name": "View Task Board", "slug": "task:view", "module": "Tasks", "description": "Access the Kanban / Calendar task views"},
    {"name": "Create Task", "slug": "task:create", "module": "Tasks", "description": "Assign tasks to self or others"},
    {"name": "Edit Task", "slug": "task:edit", "module": "Tasks", "description": "Update task progress, status, and details"},
    {"name": "View EOD Reports", "slug": "eod:view", "module": "Tasks", "description": "View submitted End-of-Day reports"},
    
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
    
    # Miscellaneous
    {"name": "Manage Holidays", "slug": "holiday:manage", "module": "Settings", "description": "Manage the annual holiday calendar"},
    {"name": "Manage Clients", "slug": "client:manage", "module": "Settings", "description": "Create and edit client/vendor profiles"},
    {"name": "Manage Blogs", "slug": "blog:manage", "module": "Settings", "description": "Create and publish internal blog posts"},

    # Navigation (Sidebar) Permissions
    {"name": "Nav Dashboard", "slug": "nav:dashboard", "module": "Navigation", "description": "View Dashboard in sidebar"},
    {"name": "Nav Employee", "slug": "nav:employee", "module": "Navigation", "description": "View Employee menu in sidebar"},
    {"name": "Nav Attendance", "slug": "nav:attendance", "module": "Navigation", "description": "View Attendance menu in sidebar"},
    {"name": "Nav Leave", "slug": "nav:leave", "module": "Navigation", "description": "View Leave Management menu in sidebar"},
    {"name": "Nav Holiday", "slug": "nav:holiday", "module": "Navigation", "description": "View Holiday menu in sidebar"},
    {"name": "Nav Project", "slug": "nav:project", "module": "Navigation", "description": "View Project menu in sidebar"},
    {"name": "Nav Task", "slug": "nav:task", "module": "Navigation", "description": "View Task Management menu in sidebar"},
    {"name": "Nav Client", "slug": "nav:client", "module": "Navigation", "description": "View Client/Vendor menu in sidebar"},
    {"name": "Nav Asset", "slug": "nav:asset", "module": "Navigation", "description": "View Asset Management menu in sidebar"},
    {"name": "Nav Expense", "slug": "nav:expense", "module": "Navigation", "description": "View Expense Management menu in sidebar"},
    {"name": "Nav Document", "slug": "nav:document", "module": "Navigation", "description": "View Document Management menu in sidebar"},
    {"name": "Nav Blog", "slug": "nav:blog", "module": "Navigation", "description": "View Blog menu in sidebar"},
    {"name": "Nav Feeds", "slug": "nav:feeds", "module": "Navigation", "description": "View Feeds menu in sidebar"},
    {"name": "Nav Milestone", "slug": "nav:milestone", "module": "Navigation", "description": "View Milestone Roadmap menu in sidebar"},
]

async def seed_permissions():
    client = AsyncIOMotorClient(DATABASE_URL)
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
                perm_map.get("dashboard:view"),
                perm_map.get("attendance:view_self"),
                perm_map.get("leave:apply"),
                perm_map.get("task:view"),
                perm_map.get("project:view"),
                perm_map.get("expense:submit"),
                perm_map.get("asset:view"),
                perm_map.get("employee:view"), # Often employees can see the directory
                
                # Nav Permissions
                perm_map.get("nav:dashboard"),
                perm_map.get("nav:attendance"),
                perm_map.get("nav:leave"),
                perm_map.get("nav:task"),
                perm_map.get("nav:feeds"),
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
    client.close()

if __name__ == "__main__":
    asyncio.run(seed_permissions())
