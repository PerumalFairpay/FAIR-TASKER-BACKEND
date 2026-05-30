import httpx
import logging
import os

CHATBOX_REGISTER_URL = os.getenv("CHATBOX_REGISTER_URL", "https://chatbox.fairental.com/api/auth/register")

logger = logging.getLogger(__name__)


async def register_chatbox_account(
    username: str,
    password: str,
    full_name: str,
    email: str,
) -> bool:
    """
    Register a new account on the Chatbox platform.
    Returns True on success, False if account already exists or error occurs.
    """
    payload = {
        "username": username,
        "password": password,
        "full_name": full_name,
        "email": email,
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(CHATBOX_REGISTER_URL, json=payload)
            resp_data = response.json()
            
            # Log for debugging
            logger.info(f"[Chatbox] Response Status: {response.status_code}, Body: {resp_data}")
            
            # Check for "already exists" in ANY status code (some APIs return 200 even if already there)
            msg = str(resp_data.get("message", "")).lower()
            if "already exists" in msg or "already registered" in msg:
                logger.info(f"[Chatbox] Account already exists for {email}")
                return False

            if response.status_code == 201:
                logger.info(f"[Chatbox] Account registered successfully (201) for {email}")
                return True
            
            if response.status_code == 200:
                # If it's 200 and we didn't see "already exists", we assume it's a success
                logger.info(f"[Chatbox] Account registered successfully (200) for {email}")
                return True
                
            response.raise_for_status()
            return False
            
    except httpx.HTTPStatusError as e:
        try:
            resp_data = e.response.json()
            msg = resp_data.get("message", "Unknown error")
            if "already exists" in msg.lower():
                logger.info(f"[Chatbox] Account already exists for {email}")
                return False
            logger.warning(f"[Chatbox] Registration failed for {email}: {e.response.status_code} - {msg}")
        except:
            logger.warning(f"[Chatbox] Registration failed for {email}: {e.response.status_code}")
    except Exception as e:
        logger.error(f"[Chatbox] Unexpected error registering account for {email}: {e}")
    return False
