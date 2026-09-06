from typing import Dict, Any, List, Optional, Tuple
import httpx
from app.core.config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI
from app.database import users_collection
from app.auth import create_access_token
import traceback


class GoogleAuthService:

    @staticmethod
    def get_login_url() -> Tuple[Optional[str], Optional[str]]:
        if not GOOGLE_CLIENT_ID or not GOOGLE_REDIRECT_URI:
            return None, "Google OAuth configuration is missing"

        url = (
            f"https://accounts.google.com/o/oauth2/v2/auth?"
            f"client_id={GOOGLE_CLIENT_ID}&"
            f"redirect_uri={GOOGLE_REDIRECT_URI}&"
            f"response_type=code&"
            f"scope=https://www.googleapis.com/auth/userinfo.email https://www.googleapis.com/auth/userinfo.profile&"
            f"access_type=offline&prompt=select_account"
        )
        return url, None

    @staticmethod
    async def process_callback(code: str) -> Tuple[Optional[str], Optional[str]]:
        """Returns (system_token, error_message)"""
        token_url = "https://oauth2.googleapis.com/token"
        data = {
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code",
        }

        try:
            async with httpx.AsyncClient() as client:
                token_response = await client.post(token_url, data=data)
                if token_response.status_code != 200:
                    return None, "Failed to fetch token from Google"

                tokens = token_response.json()
                access_token = tokens.get("access_token")

                user_info_url = "https://www.googleapis.com/oauth2/v3/userinfo"
                user_info_response = await client.get(
                    user_info_url, headers={"Authorization": f"Bearer {access_token}"}
                )
                if user_info_response.status_code != 200:
                    return None, "Failed to fetch user info from Google"

                user_info = user_info_response.json()
                email = user_info.get("email")

                user_record = await users_collection.find_one({"email": email, "is_deleted": {"$ne": True}})
                if not user_record:
                    return None, "Account not found. Please contact support."

                token = create_access_token(user_record)
                return token, None
        except Exception as e:
            traceback.print_exc()
            return None, str(e)
