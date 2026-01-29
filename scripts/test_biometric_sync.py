import requests
import json
from datetime import datetime
import random

BACKEND_URL = 'http://127.0.0.1:8000/api/attendance/biometric/sync'

def generate_mock_data():
    now = datetime.now()
    timestamp = now.isoformat()
    
    # Simulate a user ID (must match an existing employee_no_id or attendance_id in your DB for successful sync)
    user_id = "EMP001" 
    
    data = [
        {
            "user_id": user_id,
            "timestamp": timestamp,
            "status": 0,
            "punch": 0
        }
    ]
    return data

def test_sync():
    data = generate_mock_data()
    print(f"Sending Mock Data: {json.dumps(data, indent=2)}")
    
    try:
        response = requests.post(BACKEND_URL, json={"data": data})
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_sync()
