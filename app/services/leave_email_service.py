import os
from app.helper.gmail import gmail_helper

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "fairpayhrm@gmail.com")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

async def send_leave_application_email(employee_name: str, employee_email: str, leave_type: str, start_date: str, end_date: str, total_days: float, reason: str):
    """Notify employee and admin about new leave request."""
    try:
        # 1. To Employee
        employee_subject = f"Leave Request Submitted - {leave_type}"
        employee_body = f"""
        <html>
            <body>
                <p>Hello {employee_name},</p>
                <p>Your leave request has been submitted successfully and is currently <strong>Pending</strong> approval.</p>
                <ul>
                    <li><strong>Leave Type:</strong> {leave_type}</li>
                    <li><strong>Duration:</strong> {start_date} to {end_date} ({total_days} days)</li>
                </ul>
                <p>You will receive another email once your request is reviewed.</p>
                <div style="margin-top: 20px;">
                    <a href="{FRONTEND_URL}/leave-management/request" 
                       style="background-color: #000; color: #fff; padding: 10px 20px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block;">
                       View My Request
                    </a>
                </div>
                <br/>
                <p>Best regards,<br/>HR Team</p>
            </body>
        </html>
        """
        gmail_helper.send_email(to=employee_email, subject=employee_subject, body_html=employee_body)

        # 2. To Admin
        admin_subject = f"New Leave Request: {employee_name}"
        admin_body = f"""
        <html>
            <body>
                <p>A new leave request has been submitted by <strong>{employee_name}</strong>.</p>
                <ul>
                    <li><strong>Leave Type:</strong> {leave_type}</li>
                    <li><strong>Duration:</strong> {start_date} to {end_date} ({total_days} days)</li>
                    <li><strong>Reason:</strong> {reason}</li>
                </ul>
                <p>Please click the button below to review the request in the admin dashboard:</p>
                <div style="margin-top: 20px;">
                    <a href="{FRONTEND_URL}/leave-management/request" 
                       style="background-color: #000; color: #fff; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block;">
                       Review Request
                    </a>
                </div>
            </body>
        </html>
        """
        gmail_helper.send_email(to=ADMIN_EMAIL, subject=admin_subject, body_html=admin_body)
    except Exception as e:
        print(f"[Gmail] Failed to send leave application emails: {e}")

async def send_leave_status_email(employee_name: str, employee_email: str, leave_type: str, start_date: str, end_date: str, status: str, rejection_reason: str = None):
    """Notify employee about leave status update."""
    try:
        subject = f"Leave Request {status} - {leave_type}"
        
        rejection_block = ""
        if status == "Rejected" and rejection_reason:
            rejection_block = f"<p><strong>Reason for Rejection:</strong> {rejection_reason}</p>"
            
        body = f"""
        <html>
            <body>
                <p>Hello {employee_name},</p>
                <p>Your leave request for <strong>{start_date} to {end_date}</strong> has been <strong>{status}</strong>.</p>
                {rejection_block}
                <div style="margin-top: 20px;">
                    <a href="{FRONTEND_URL}/leave-management/request" 
                       style="background-color: #000; color: #fff; padding: 10px 20px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block;">
                       View Details
                    </a>
                </div>
                <p>Thank you.</p>
                <br/>
                <p>Best regards,<br/>HR Team</p>
            </body>
        </html>
        """
        gmail_helper.send_email(to=employee_email, subject=subject, body_html=body)
    except Exception as e:
        print(f"[Gmail] Failed to send leave status email: {e}")
