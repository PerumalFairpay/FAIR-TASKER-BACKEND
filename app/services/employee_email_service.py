import os
from app.helper.gmail import gmail_helper

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

def send_welcome_email(employee_name: str, employee_email: str, password: str, include_workbench: bool = True):
    """Notify employee of their new account and credentials."""
    login_url = f"{FRONTEND_URL}"
    
    workbench_section = ""
    warning_note = "as soon as possible after your first login."
    
    if include_workbench:
        workbench_section = f"""
        <h3 style="color: #000; margin-top: 25px;">WorkBench Access</h3>
        <p>To keep you connected with the team, we've also provisioned your account on <strong>WorkBench</strong>, our official platform for internal communication and collaboration:</p>
        <div style="background-color: #e3f2fd; padding: 15px; border-radius: 5px; margin: 20px 0; border: 1px solid #bbdefb;">
            <p style="margin: 5px 0;"><strong>Username:</strong> {employee_name}</p>
            <p style="margin: 5px 0;"><strong>Password:</strong> {password}</p>
        </div>
        """
        warning_note = "on both platforms as soon as possible after your first login."

    body = f"""
    <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #333; max-width: 600px;">
        <h2 style="color: #000; border-bottom: 2px solid #eee; padding-bottom: 10px;">Welcome to FairPAY Tech Works!</h2>
        <p>Dear {employee_name},</p>
        <p>Your employee account has been successfully created. Welcome to the team!</p>
        <p>Please use the following credentials to access the company portal:</p>
        
        <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0; border: 1px solid #ddd;">
            <p style="margin: 5px 0;"><strong>Company Email:</strong> {employee_email}</p>
            <p style="margin: 5px 0;"><strong>Password:</strong> {password}</p>
        </div>

        {workbench_section}
        
        <div style="background-color: #fff9e6; border-left: 4px solid #ffcc00; padding: 15px; margin-top: 25px; margin-bottom: 20px; font-size: 14px;">
            <strong>Warning:</strong> For security reasons, please change your password {warning_note}
        </div>
        
        <p><strong>Instructions to change your password:</strong></p>
        <ol style="margin-top: 10px; margin-bottom: 25px; padding-left: 20px;">
            <li>Log in to the company portal using the credentials provided above.</li>
            <li>Navigate to your <strong>Profile</strong> or <strong>Account Settings</strong>.</li>
            <li>Select the <strong>Change Password</strong> option.</li>
            <li>Enter your current password and set a new secure password.</li>
        </ol>
        
        <p style="margin: 35px 0; text-align: center;">
            <a href="{login_url}" style="background-color: #000; color: #fff; padding: 14px 28px; text-decoration: none; border-radius: 4px; font-weight: 600; display: inline-block;">Log In Now</a>
        </p>

        <p>If you have any questions or need assistance, please contact the IT or HR department.</p>
        
        <p style="margin-top: 30px;">Best regards,<br/><strong>FairPAY Tech Works India Private Limited</strong></p>
    </div>
    """
    try:
        gmail_helper.send_email(
            to=employee_email, 
            subject="Welcome to FairPAY! Your Account Credentials", 
            body_html=body
        )
    except Exception as e:
        print(f"[Gmail] Failed to send welcome email: {e}")
