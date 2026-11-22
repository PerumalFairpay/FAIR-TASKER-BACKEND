import asyncio
import os
import sys
from datetime import datetime

# Add the parent directory to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv

load_dotenv()

from app.database import (
    permissions_collection,
    roles_collection,
    role_permissions_collection,
)
from bson import ObjectId


PERMISSIONS_DATA = [
    {"code": "dashboard:view", "name": "View Dashboard", "module": "Dashboard", "description": "Can access dashboard and analytics summary"},
    {"code": "employee:view", "name": "View Employees", "module": "Employee", "description": "Can view employee directories and profiles"},
    {"code": "attendance:view", "name": "View Attendance", "module": "Attendance", "description": "Can view attendance logs and history"},
    {"code": "leave:view", "name": "View Leaves", "module": "Leave", "description": "Can view leave history and leave balances"},
    {"code": "leave:access", "name": "Leave Access (Manage)", "module": "Leave", "description": "Can manage and configure leave types and rules"},
    {"code": "payslip:view", "name": "View Payslips", "module": "Payroll", "description": "Can view and download payslips"},
    {"code": "expense:view", "name": "View Expenses", "module": "Expense", "description": "Can view expense claims and reports"},
    {"code": "asset:view", "name": "View Assets", "module": "Asset", "description": "Can view company assets and inventory"},
    {"code": "project:view", "name": "View Projects", "module": "Project", "description": "Can view projects"},
    {"code": "task:view", "name": "View Tasks", "module": "Task", "description": "Can view project tasks"},
    {"code": "document:view", "name": "View Documents", "module": "Document", "description": "Can view company documents and policies"},
    {"code": "document:access", "name": "Document Access (Manage)", "module": "Document", "description": "Can upload, edit, and delete company documents"},
    {"code": "feedback:view", "name": "View Feedback", "module": "Feedback", "description": "Can view feedback entries"},
    {"code": "shift:view", "name": "View Shifts", "module": "Shift", "description": "Can view shifts"},
    {"code": "settings:view", "name": "View Settings", "module": "Settings", "description": "Can view general organization settings"},
    {"code": "role:view", "name": "View Roles", "module": "Role", "description": "Can view roles and permissions configuration"},
    {"code": "user:view", "name": "View Users", "module": "User", "description": "Can view and manage user accounts"},
]


async def seed():
    print("=" * 60)
    print("Seeding View-Only Permissions (FLEETGLIDE Architecture)")
    print("=" * 60)

    now = datetime.utcnow()
    valid_codes = [p["code"] for p in PERMISSIONS_DATA]

    # 1. Soft-delete any permission that is not in the view-only list
    deactivated = await permissions_collection.update_many(
        {"code": {"$nin": valid_codes}, "is_deleted": {"$ne": True}},
        {"$set": {"is_deleted": True, "deleted_at": now}}
    )
    print(f"Deactivated {deactivated.modified_count} non-view permissions.")

    all_perm_ids = []
    inserted_count = 0
    updated_count = 0

    # 2. Upsert view permissions
    for item in PERMISSIONS_DATA:
        existing = await permissions_collection.find_one({"code": item["code"]})
        if existing:
            await permissions_collection.update_one(
                {"_id": existing["_id"]},
                {"$set": {
                    "name": item["name"],
                    "module": item["module"],
                    "description": item["description"],
                    "is_deleted": False,
                    "deleted_at": None,
                    "updated_at": now
                }}
            )
            all_perm_ids.append(str(existing["_id"]))
            updated_count += 1
        else:
            doc = {
                "code": item["code"],
                "name": item["name"],
                "module": item["module"],
                "description": item["description"],
                "is_deleted": False,
                "deleted_at": None,
                "created_at": now,
                "updated_at": now
            }
            res = await permissions_collection.insert_one(doc)
            all_perm_ids.append(str(res.inserted_id))
            inserted_count += 1

    print(f"View Permissions: {inserted_count} created, {updated_count} active/updated.")

    # 3. Clean up role_permissions linking to deactivated permissions
    await role_permissions_collection.update_many(
        {"permission_id": {"$nin": all_perm_ids}, "is_deleted": {"$ne": True}},
        {"$set": {"is_deleted": True, "deleted_at": now}}
    )

    # 4. Link all view permissions to 'admin' role
    admin_role = await roles_collection.find_one({
        "name": {"$regex": "^admin$", "$options": "i"},
        "is_deleted": {"$ne": True}
    })

    if admin_role:
        admin_role_id = str(admin_role["_id"])
        print(f"\nLinking all {len(all_perm_ids)} view permissions to Admin role ({admin_role_id})...")

        await role_permissions_collection.update_many(
            {"role_id": admin_role_id, "is_deleted": {"$ne": True}},
            {"$set": {"is_deleted": True, "deleted_at": now}}
        )

        admin_links = [{
            "role_id": admin_role_id,
            "permission_id": pid,
            "is_deleted": False,
            "deleted_at": None,
            "created_at": now,
            "updated_at": now
        } for pid in all_perm_ids]

        if admin_links:
            await role_permissions_collection.insert_many(admin_links)
        print("Admin role permissions successfully linked!")

    # 5. Link view permissions for employee role
    employee_role = await roles_collection.find_one({
        "name": {"$regex": "^employee$", "$options": "i"},
        "is_deleted": {"$ne": True}
    })

    if employee_role:
        emp_role_id = str(employee_role["_id"])
        employee_codes = {
            "dashboard:view",
            "attendance:view",
            "leave:view",
            "payslip:view",
            "expense:view",
            "asset:view",
            "project:view",
            "task:view",
            "document:view",
            "shift:view",
        }

        emp_perm_docs = await permissions_collection.find({
            "code": {"$in": list(employee_codes)},
            "is_deleted": {"$ne": True}
        }).to_list(length=None)

        emp_perm_ids = [str(p["_id"]) for p in emp_perm_docs]

        await role_permissions_collection.update_many(
            {"role_id": emp_role_id, "is_deleted": {"$ne": True}},
            {"$set": {"is_deleted": True, "deleted_at": now}}
        )

        emp_links = [{
            "role_id": emp_role_id,
            "permission_id": pid,
            "is_deleted": False,
            "deleted_at": None,
            "created_at": now,
            "updated_at": now
        } for pid in emp_perm_ids]

        if emp_links:
            await role_permissions_collection.insert_many(emp_links)
        print(f"Employee role linked with {len(emp_links)} view permissions!")

    print("\n" + "=" * 60)
    print("Seed process completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(seed())
