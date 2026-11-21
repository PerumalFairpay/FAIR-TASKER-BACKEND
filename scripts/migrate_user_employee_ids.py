import asyncio
import os
import sys

# Add the parent directory to sys.path so app modules can be imported
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from bson import ObjectId
from app.database import users_collection, employees_collection


async def migrate_user_employee_ids():
    print("=" * 60)
    print("Starting Migration: Backfill employee_id in Users Collection")
    print("=" * 60)

    # 1. Fetch active employees
    employees = await employees_collection.find(
        {"is_deleted": {"$ne": True}},
        {"_id": 1, "employee_no_id": 1, "email": 1, "name": 1}
    ).to_list(length=None)

    print(f"Found {len(employees)} active employee(s) in 'employees' collection.")

    total_linked = 0
    total_skipped = 0

    for emp in employees:
        emp_id = str(emp["_id"])
        emp_code = emp.get("employee_no_id")
        email = emp.get("email")
        emp_name = emp.get("name") or f"{emp.get('first_name', '')} {emp.get('last_name', '')}".strip()

        # Build query matching user by employee_no_id or email
        match_conditions = []
        if emp_code:
            match_conditions.append({"employee_no_id": emp_code})
        if email:
            match_conditions.append({"email": email})

        if not match_conditions:
            print(f"  [SKIP] Employee '{emp_name}' (ID: {emp_id}) has no employee_no_id or email. Skipped.")
            total_skipped += 1
            continue

        query = {"$or": match_conditions, "is_deleted": {"$ne": True}}

        # Update matching users
        result = await users_collection.update_many(
            query,
            {"$set": {"employee_id": emp_id}}
        )

        if result.modified_count > 0:
            total_linked += result.modified_count
            print(f"  [LINKED] Employee '{emp_name}' (code='{emp_code}', email='{email}') -> employee_id={emp_id} (Updated {result.modified_count} user doc)")
        else:
            # Check if user already had this employee_id set
            already_set = await users_collection.find_one({
                "$or": match_conditions,
                "employee_id": emp_id
            })
            if already_set:
                print(f"  [OK] User for employee '{emp_name}' already correctly linked to employee_id={emp_id}")
            else:
                print(f"  [INFO] No corresponding user document found for employee '{emp_name}' ({emp_code})")

    print("\n" + "=" * 60)
    print(f"Migration Complete:")
    print(f"  - Successfully updated users : {total_linked}")
    print(f"  - Skipped employees          : {total_skipped}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(migrate_user_employee_ids())
