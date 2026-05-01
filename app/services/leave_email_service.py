import os
from app.helper.gmail import gmail_helper

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "fairpayhrm@gmail.com")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

def _get_base_template(content_html: str, title: str):
    """Wrap content in a professional, responsive email layout."""
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; background-color: #f9f9f9; }}
            .container {{ max-width: 600px; margin: 20px auto; background: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 10px rgba(0,0,0,0.05); }}
            .header {{ background-color: #000000; color: #ffffff; padding: 30px; text-align: center; }}
            .header h1 {{ margin: 0; font-size: 24px; font-weight: 600; letter-spacing: 1px; }}
            .content {{ padding: 30px; }}
            .footer {{ background-color: #f1f1f1; color: #777; padding: 20px; text-align: center; font-size: 12px; }}
            .info-card {{ background-color: #f8faff; border-left: 4px solid #000; padding: 15px 20px; margin: 20px 0; border-radius: 4px; }}
            .info-row {{ margin-bottom: 10px; }}
            .info-label {{ font-weight: bold; color: #555; width: 120px; display: inline-block; }}
            .button {{ display: inline-block; background-color: #000; color: #fff !important; padding: 12px 28px; text-decoration: none; border-radius: 5px; font-weight: bold; margin-top: 10px; }}
            .status-chip {{ display: inline-block; padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: bold; text-transform: uppercase; }}
            .status-pending {{ background-color: #fef3c7; color: #92400e; }}
            .status-approved {{ background-color: #d1fae5; color: #065f46; }}
            .status-rejected {{ background-color: #fee2e2; color: #991b1b; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>FairPAY</h1>
            </div>
            <div class="content">
                <h2 style="margin-top: 0; color: #000;">{title}</h2>
                {content_html}
            </div>
            <div class="footer">
                <p>&copy; FairPAY Tech Works. All rights reserved.</p>
                <p>This is an automated notification. Please do not reply directly to this email.</p>
            </div>
        </div>
    </body>
    </html>
    """

async def send_leave_application_email(employee_name: str, employee_email: str, leave_type: str, start_date: str, end_date: str, total_days: float, reason: str):
    """Notify employee and admin about new leave request."""
    try:
        # 1. To Employee
        employee_title = "Leave Request Submitted"
        employee_content = f"""
            <p>Hello <strong>{employee_name}</strong>,</p>
            <p>Your leave request has been successfully submitted and is now awaiting review by the HR team.</p>
            
            <div class="info-card">
                <div class="info-row"><span class="info-label">Leave Type:</span> {leave_type}</div>
                <div class="info-row"><span class="info-label">Duration:</span> {start_date} to {end_date}</div>
                <div class="info-row"><span class="info-label">Total Days:</span> {total_days} day(s)</div>
                <div class="info-row"><span class="info-label">Status:</span> <span class="status-chip status-pending">Pending</span></div>
            </div>
            
            <p>You will receive a follow-up email as soon as a decision has been made regarding your request.</p>
            
            <div style="text-align: center; margin-top: 30px;">
                <a href="{FRONTEND_URL}/leave-management/request" class="button">Track Request Status</a>
            </div>
        """
        gmail_helper.send_email(
            to=employee_email, 
            subject=f"Leave Request Confirmation - {leave_type}", 
            body_html=_get_base_template(employee_content, employee_title)
        )

        # 2. To Admin
        admin_title = "New Leave Application"
        admin_content = f"""
            <p>A new leave request has been submitted by <strong>{employee_name}</strong> and requires your attention.</p>
            
            <div class="info-card">
                <div class="info-row"><span class="info-label">Employee:</span> {employee_name}</div>
                <div class="info-row"><span class="info-label">Leave Type:</span> {leave_type}</div>
                <div class="info-row"><span class="info-label">Duration:</span> {start_date} to {end_date}</div>
                <div class="info-row"><span class="info-label">Total Days:</span> {total_days} day(s)</div>
                <div class="info-row"><span class="info-label">Reason:</span> {reason}</div>
            </div>
            
            <p>Please log in to the admin portal to review the details and take appropriate action.</p>
            
            <div style="text-align: center; margin-top: 30px;">
                <a href="{FRONTEND_URL}/leave-management/request" class="button">Review Application</a>
            </div>
        """
        gmail_helper.send_email(
            to=ADMIN_EMAIL, 
            subject=f"Action Required: New Leave Request from {employee_name}", 
            body_html=_get_base_template(admin_content, admin_title)
        )
    except Exception as e:
        print(f"[Gmail] Failed to send leave application emails: {e}")

async def send_leave_status_email(employee_name: str, employee_email: str, leave_type: str, start_date: str, end_date: str, status: str, rejection_reason: str = None):
    """Notify employee about leave status update."""
    try:
        status_class = "status-approved" if status == "Approved" else "status-rejected"
        title = f"Leave Request {status}"
        
        rejection_html = ""
        if status == "Rejected" and rejection_reason:
            rejection_html = f"""
            <div style="margin-top: 20px; padding: 15px; background-color: #fff1f2; border: 1px solid #fda4af; border-radius: 4px;">
                <p style="margin: 0; color: #991b1b; font-weight: bold;">Reason for Rejection:</p>
                <p style="margin: 5px 0 0; color: #be123c;">{rejection_reason}</p>
            </div>
            """
            
        content = f"""
            <p>Hello <strong>{employee_name}</strong>,</p>
            <p>There has been an update regarding your leave request for <strong>{start_date} to {end_date}</strong>.</p>
            
            <div class="info-card" style="border-left-color: {'#065f46' if status == 'Approved' else '#991b1b'};">
                <div class="info-row"><span class="info-label">Leave Type:</span> {leave_type}</div>
                <div class="info-row"><span class="info-label">Period:</span> {start_date} to {end_date}</div>
                <div class="info-row"><span class="info-label">Final Status:</span> <span class="status-chip {status_class}">{status}</span></div>
            </div>
            
            {rejection_html}
            
            <p style="margin-top: 20px;">For more details or to manage your leave requests, please visit your dashboard.</p>
            
            <div style="text-align: center; margin-top: 30px;">
                <a href="{FRONTEND_URL}/leave-management/request" class="button">View in Dashboard</a>
            </div>
        """
        gmail_helper.send_email(
            to=employee_email, 
            subject=f"Leave Request Update: {status}", 
            body_html=_get_base_template(content, title)
        )
    except Exception as e:
        print(f"[Gmail] Failed to send leave status email: {e}")
