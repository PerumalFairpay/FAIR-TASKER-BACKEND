
import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from app.crud.repository import repository
from app.models import AttendanceCreate
from datetime import datetime

async def verify():
    print("Verifying ID Standardization...")
    
    # 1. Fetch a real employee
    emp = await repository.employees.find_one({})
    if not emp:
        print("No employees found. Cannot verify.")
        return

    print(f"Testing with Employee: {emp.get('name')} (Mongo ID: {emp.get('_id')}, No ID: {emp.get('employee_no_id')})")
    
    # 2. Simulate Clock In using Employee No ID (Rest of the string)
    emp_no_id = str(emp.get("employee_no_id"))
    
    payload = AttendanceCreate(
        employee_id=emp_no_id,
        date="2099-01-01", # Future date to avoid messing up today
        clock_in=datetime.utcnow().isoformat(),
        device_type="Test Script"
    )
    
    try:
        # Call clock_in
        result = await repository.clock_in(payload, emp_no_id)
        
        # 3. Verify the stored record
        saved_record = await repository.attendance.find_one({"date": "2099-01-01", "employee_id": str(emp.get("_id"))})
        
        if saved_record:
            print("SUCCESS: Record found using Mongo ObjectId!")
            print(f"Stored Employee ID: {saved_record.get('employee_id')}")
            
            # Clean up
            await repository.attendance.delete_one({"_id": saved_record["_id"]})
            print("Test record user cleaned up.")
        else:
            print("FAILURE: Record NOT found using Mongo ObjectId.")
            # check if it was stored with emp_no_id
            wrong_record = await repository.attendance.find_one({"date": "2099-01-01", "employee_id": emp_no_id})
            if wrong_record:
                 print(f"FAILURE: Record found with WRONG ID: {wrong_record.get('employee_id')}")
                 await repository.attendance.delete_one({"_id": wrong_record["_id"]})

    except Exception as e:
        print(f"Error during verification: {e}")

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(verify())
