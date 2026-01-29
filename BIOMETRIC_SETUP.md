# Biometric Data Integration Setup

This project includes a standalone script to sync attendance data from a ZKTeco Biometric Device (EasyTimePro) to the FAIR-TASKER backend.

## Overview

- **Script Location**: `d:\NEXT JS\FAIR-TASKER\BiometricSync\biometric_client.py`
- **Device**: ZKTeco EasyTimePro (IP: 192.168.1.43)
- **Mechanism**: The script runs continuously on a local machine, fetching logs from the device and pushing them to the backend API.

## Prequisites

1.  **Local Machine**: A Windows/Linux computer connected to the SAME network as the biometric device.
2.  **Python 3.8+**: Installed on that local machine.
3.  **Backend Access**: The machine must be able to reach the deployed FAIR-TASKER backend URL.

## Deployment Steps

### 1. Locate the Script

The script has been moved to a dedicated folder outside the backend project:
**`d:\NEXT JS\FAIR-TASKER\BiometricSync\`**

You can run it directly from there or copy this entire folder to the target machine.

### 2. Install Dependencies

Open a terminal in the `BiometricSync` folder and run:

```bash
pip install -r requirements.txt
```

### 3. Configure

Open `biometric_client.py` and check the configuration at the top:

```python
BIOMETRIC_IP = '192.168.1.43' # IP of your Device
BACKEND_URL = 'http://YOUR_SERVER_IP:8000/api/attendance/biometric/sync' # Update this!
```

### 4. Run

Run the script manually to test:

```bash
python biometric_client.py
```

### 5. Automate (Windows)

To ensure it runs 24/7, set it up as a **Scheduled Task**:

1.  Open **Task Scheduler**.
2.  Create a Basic Task -> "Biometric Sync".
3.  Trigger: **When the computer starts**.
4.  Action: **Start a program**.
    - Program: `python.exe` (path to your python executable)
    - Arguments: `C:\FairTaskerBiometric\biometric_client.py`
    - Start in: `C:\FairTaskerBiometric\`

## Troubleshooting

- **Logs**: Check `biometric_client_YYYY-MM-DD.log` in the script folder.
- **Data Not Showing**: Ensure the `User ID` in the biometric device matches the `Employee No / ID` or `Attendance ID` in the FAIR-TASKER employee profile.
