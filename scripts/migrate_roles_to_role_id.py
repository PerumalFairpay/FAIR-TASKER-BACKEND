import asyncio
import os
import sys
from datetime import datetime

# Add the parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from app.database import roles_collection, users_collection, employees_collection


async def migrate_roles():
    print("=" * 60)
    print("Starting Migration: Backfilling role_id for Users & Employees")
    print("=" * 60)

    # 1. Fetch active roles and build lookup map
    roles = await roles_collection.find({"is_deleted": {"$ne": True}}).to_list(length=None)
    role_map = {}
    for r in roles:
        role_name = r.get("name", "").strip().lower()
        if role_name:
            role_map[role_name] = str(r["_id"])

    print(f"Loaded {len(role_map)} existing role(s) from database:")
    for name, r_id in role_map.items():
        print(f"  - '{name}': {r_id}")

    default_role_id = role_map.get("employee")

    # 2. Migrate Users Collection
    print("\n[1/2] Migrating 'users' collection...")
    users = await users_collection.find({}).to_list(length=None)
    user_updated = 0
    user_skipped = 0

    for user in users:
        user_id = user["_id"]
        current_role_id = user.get("role_id")
        role_name = str(user.get("role", "employee")).strip().lower()

        target_role_id = role_map.get(role_name, default_role_id)

        if not target_role_id:
            print(f"  [WARN] No matching role found for user {user.get('email')} (role='{role_name}'). Skipping.")
            user_skipped += 1
            continue

        if current_role_id == target_role_id:
            user_skipped += 1
            continue

        await users_collection.update_one(
            {"_id": user_id},
            {
                "$set": {
                    "role_id": target_role_id,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        user_updated += 1
        print(f"  [UPDATED] User {user.get('email')}: set role_id={target_role_id} (from role='{role_name}')")

    print(f"Users summary: {user_updated} updated, {user_skipped} skipped/already up-to-date.")

    # 3. Migrate Employees Collection
    print("\n[2/2] Migrating 'employees' collection...")
    employees = await employees_collection.find({}).to_list(length=None)
    emp_updated = 0
    emp_skipped = 0

    for emp in employees:
        emp_id = emp["_id"]
        current_role_id = emp.get("role_id")
        role_name = str(emp.get("role", "employee")).strip().lower()

        target_role_id = role_map.get(role_name, default_role_id)

        if not target_role_id:
            print(f"  [WARN] No matching role found for employee {emp.get('email')} (role='{role_name}'). Skipping.")
            emp_skipped += 1
            continue

        if current_role_id == target_role_id:
            emp_skipped += 1
            continue

        await employees_collection.update_one(
            {"_id": emp_id},
            {
                "$set": {
                    "role_id": target_role_id,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        emp_updated += 1
        print(f"  [UPDATED] Employee {emp.get('email')}: set role_id={target_role_id} (from role='{role_name}')")

    print(f"Employees summary: {emp_updated} updated, {emp_skipped} skipped/already up-to-date.")

    print("\n" + "=" * 60)
    print("Migration finished successfully!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(migrate_roles())
