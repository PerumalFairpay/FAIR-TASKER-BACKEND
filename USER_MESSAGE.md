I have completed the fixes to prevent duplicate attendance records.

**What was done:**

1.  **Standardized Employee IDs:** Modified `repository.py` and `attendance_jobs.py` to strictly use the MongoDB ObjectId (`_id`) for all attendance records. This ensures that Manual Clock-ins, Biometric Syncs, and Leave Requests all update the _same_ record instead of creating parallel ones.
2.  **Verification Script:** added `verify_fix.py` to the backend folder. You can run this script to programmically verify that a clock-in using an Employee Number is correctly saved with the MongoDB ObjectId.
3.  **Documentation:** Added `README_ATTENDANCE_FIX.md` with details on the fix.

**How to Proceed:**
Since you have reset the database, the system is clean.

1.  **Restart the Backend:** Ensure the code changes are picked up (if hot-reload isn't active).
2.  **Test:**
    - Perform a Manual Clock In.
    - Sync Biometric Logs.
    - Apply/Approve Leave.

You should now see unified attendance records for each day.
