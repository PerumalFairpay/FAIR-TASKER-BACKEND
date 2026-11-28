import os
import traceback
from app.helper.gmail import gmail_helper

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3001")


def send_password_reset_email(to_email: str, user_name: str, token: str):
    """Send a password reset email with secure token link."""
    frontend_url = FRONTEND_URL.rstrip("/")
    reset_link = f"{frontend_url}/reset-password?token={token}"

    subject = "Password Reset Request - FairPAY HRM"
    body_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8fafc; margin: 0; padding: 20px; }}
        .container {{ max-width: 560px; margin: 0 auto; background: #ffffff; border-radius: 12px; padding: 32px; border: 1px solid #e2e8f0; }}
        .header {{ text-align: center; margin-bottom: 24px; }}
        .header h1 {{ color: #0f172a; font-size: 22px; margin: 0; }}
        .content {{ color: #334155; font-size: 15px; line-height: 1.6; margin-bottom: 28px; }}
        .btn-container {{ text-align: center; margin: 28px 0; }}
        .btn {{ display: inline-block; background-color: #2563eb; color: #ffffff !important; padding: 12px 28px; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 15px; }}
        .footer {{ text-align: center; font-size: 12px; color: #94a3b8; border-top: 1px solid #e2e8f0; padding-top: 20px; margin-top: 20px; }}
      </style>
    </head>
    <body>
      <div class="container">
        <div class="header">
          <h1>Password Reset Request</h1>
        </div>
        <div class="content">
          <p>Hello <strong>{user_name}</strong>,</p>
          <p>We received a request to reset your password for your FairPAY HRM account. Click the button below to choose a new password:</p>
          <div class="btn-container">
            <a href="{reset_link}" class="btn">Reset Password</a>
          </div>
          <p>Or copy and paste this URL into your browser:</p>
          <p style="word-break: break-all; color: #2563eb; font-size: 13px;">{reset_link}</p>
          <p>This password reset link will expire in <strong>30 minutes</strong>. If you did not request this, you can safely ignore this email.</p>
        </div>
        <div class="footer">
          <p>&copy; FairPAY Tech Works. All rights reserved.</p>
        </div>
      </div>
    </body>
    </html>
    """

    try:
        gmail_helper.send_email(to=to_email, subject=subject, body_html=body_html)
    except Exception as mail_err:
        print(f"[ForgotPassword] Failed to send email via gmail_helper: {mail_err}")
        traceback.print_exc()
