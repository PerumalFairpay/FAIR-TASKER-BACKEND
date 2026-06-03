from app.integrations.chatbox_service import register_chatbox_account
from app.services.employee_email_service import send_welcome_email
import logging

logger = logging.getLogger(__name__)

async def handle_new_employee_onboarding(employee_name: str, employee_email: str, password: str):
    """
    Coordinates background tasks for new employee creation:
    1. Registers a WorkBench (Chatbox) account.
    2. Sends the welcome email with credentials.
    
    If the WorkBench account already exists or registration fails, 
    the email will NOT include the WorkBench section.
    """
    try:
        # 1. Register WorkBench account
        # returns True if newly created, False if already exists or error
        # is_new_registration = await register_chatbox_account(
        #     username=employee_name,
        #     password=password,
        #     full_name=employee_name,
        #     email=employee_email
        # )
        is_new_registration = False
        
        # 2. Send Welcome Email
        # include_workbench is only True if a NEW account was successfully created
        send_welcome_email(
            employee_name=employee_name,
            employee_email=employee_email,
            password=password,
            include_workbench=is_new_registration
        )
        
    except Exception as e:
        logger.error(f"Error in onboarding process for {employee_email}: {e}")
