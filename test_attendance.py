"""
Test script to verify attendance record generation
Run this after starting the backend server
"""
import requests
import json
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8000/api"

# Authentication: Your backend uses HTTP-only cookies
# You need to login first to get the session cookie
def login(email: str, password: str):
    """Login and return session with cookie"""
    response = requests.post(
        f"{BASE_URL}/auth/login",
        json={"email": email, "password": password}
    )
    
    if response.status_code == 200:
        print("✅ Login successful!")
        return response.cookies
    else:
        print(f"❌ Login failed: {response.json()}")
        return None

# Update these with your credentials
LOGIN_EMAIL = "perumal@gmail.com"  # Update with your email
LOGIN_PASSWORD = "your_password"    # Update with your password

# Session will store the cookie after login
session = None

def test_generate_preplanned_records():
    """Test morning job logic: Generate ONLY preplanned records (Leaves/Holidays) for TODAY"""
    print("\n=== Testing Morning Job (Preplanned Only) ===")
    
    # We use 'today' because the morning job runs for the current day
    today = datetime.utcnow().strftime("%Y-%m-%d")
    
    response = requests.post(
        f"{BASE_URL}/attendance/generate-records",
        params={"date": today, "preplanned_only": "true"},
        cookies=session
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")

def test_generate_full_records():
    """Test night job logic: Generate ALL records (fill in Absences) for TODAY"""
    print("\n=== Testing Night Job (Full Generation) ===")
    
    today = datetime.utcnow().strftime("%Y-%m-%d")
    
    response = requests.post(
        f"{BASE_URL}/attendance/generate-records",
        params={"date": today, "preplanned_only": "false"},
        cookies=session
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
def test_get_all_attendance():
    """Test getting all attendance records (should return actual records only)"""
    print("\n=== Testing Get All Attendance (No Filters) ===")
    
    response = requests.get(
        f"{BASE_URL}/attendance/",
        cookies=session
    )
    
    data = response.json()
    print(f"Status Code: {response.status_code}")
    print(f"Total Records: {data.get('metrics', {}).get('total_records', 0)}")
    print(f"Sample Record IDs: {[r['id'] for r in data.get('data', [])[:3]]}")
    
def test_get_attendance_with_date_filter():
    """Test getting attendance with date filters"""
    print("\n=== Testing Get Attendance with Date Filter ===")
    
    response = requests.get(
        f"{BASE_URL}/attendance/",
        params={
            "start_date": "2026-01-01",
            "end_date": "2026-01-03"
        },
        cookies=session
    )
    
    data = response.json()
    print(f"Status Code: {response.status_code}")
    print(f"Total Records: {data.get('metrics', {}).get('total_records', 0)}")
    print(f"Present: {data.get('metrics', {}).get('present', 0)}")
    print(f"Absent: {data.get('metrics', {}).get('absent', 0)}")
    print(f"Sample Record IDs: {[r['id'] for r in data.get('data', [])[:3]]}")
    
    # Check if any IDs start with 'v_' (virtual records - should be none now)
    virtual_records = [r for r in data.get('data', []) if r['id'].startswith('v_')]
    print(f"Virtual Records Found: {len(virtual_records)} (should be 0)")

def test_get_attendance_for_today():
    """Test getting attendance for today (should include the actual record from 2026-01-22)"""
    print("\n=== Testing Get Attendance for Specific Date ===")
    
    response = requests.get(
        f"{BASE_URL}/attendance/",
        params={"date": "2026-01-22"},
        cookies=session
    )
    
    data = response.json()
    print(f"Status Code: {response.status_code}")
    print(f"Total Records: {data.get('metrics', {}).get('total_records', 0)}")
    
    if data.get('data'):
        print(f"First Record: {json.dumps(data['data'][0], indent=2)}")

if __name__ == "__main__":
    print("=" * 60)
    print("Attendance Record Generation Test Suite")
    print("=" * 60)
    print("\nNOTE: Update LOGIN_EMAIL and LOGIN_PASSWORD before running!")
    print("Your backend uses HTTP-only cookies for authentication")
    
    if LOGIN_PASSWORD == "your_password":
        print("\n⚠️  Please update LOGIN_EMAIL and LOGIN_PASSWORD in the script first!")
    else:
        try:
            # Login first to get session cookie
            print("\n=== Logging in ===")
            session = login(LOGIN_EMAIL, LOGIN_PASSWORD)
            
            if not session:
                print("\n❌ Login failed. Cannot proceed with tests.")
                exit(1)
            
            # Run tests
            test_generate_preplanned_records() # Morning Job Test
            test_generate_full_records()       # Night Job Test
            test_get_all_attendance()
            test_get_attendance_with_date_filter()
            test_get_attendance_for_today()
            
            print("\n" + "=" * 60)
            print("✅ All tests completed!")
            print("=" * 60)
        except Exception as e:
            print(f"\n❌ Error: {str(e)}")

