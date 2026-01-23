import asyncio
import sys
from seed_permissions import seed_permissions
from seed_leave_types import seed_leave_types
from seed_admin import seed_admin

async def seed_all():
    """
    Master seed script to populate the database with initial data.
    Runs all seed scripts in the correct order.
    """
    print("=" * 60)
    print("Starting Database Seeding Process")
    print("=" * 60)
    print()
    
    try:
        # 1. Seed Permissions and Roles (must be first)
        print("Step 1: Seeding Permissions and Roles...")
        print("-" * 60)
        await seed_permissions()
        print()
        
        # 2. Seed Leave Types
        print("Step 2: Seeding Leave Types...")
        print("-" * 60)
        await seed_leave_types()
        print()
        
        # 3. Seed Admin User (must be after permissions)
        print("Step 3: Seeding Admin User...")
        print("-" * 60)
        await seed_admin()
        print()
        
        print("=" * 60)
        print("✅ Database Seeding Completed Successfully!")
        print("=" * 60)
        print()
        print("Default Admin Credentials:")
        print("  Email: admin@fairpay.com")
        print("  Password: admin123")
        print()
        print("⚠️  Please change the admin password after first login!")
        print("=" * 60)
        
    except Exception as e:
        print()
        print("=" * 60)
        print("❌ Error during seeding process:")
        print(f"   {str(e)}")
        print("=" * 60)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(seed_all())
