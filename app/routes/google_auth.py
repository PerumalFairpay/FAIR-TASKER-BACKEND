from fastapi import APIRouter, HTTPException, Response, Request
from fastapi.responses import RedirectResponse
import httpx
from app.core.config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI, FRONTEND_URL, ACCESS_TOKEN_EXPIRE_MINUTES
from app.database import users_collection
from app.auth import create_access_token

router = APIRouter()

@router.get("/login")
async def google_login():
    if not GOOGLE_CLIENT_ID or not GOOGLE_REDIRECT_URI:
        raise HTTPException(status_code=500, detail="Google OAuth configuration is missing")
        
    url = (
        f"https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={GOOGLE_CLIENT_ID}&"
        f"redirect_uri={GOOGLE_REDIRECT_URI}&"
        f"response_type=code&"
        f"scope=https://www.googleapis.com/auth/userinfo.email https://www.googleapis.com/auth/userinfo.profile&"
        f"access_type=offline&prompt=select_account"
    )
    return RedirectResponse(url)

@router.get("/callback")
async def google_callback(code: str):
    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "grant_type": "authorization_code",
    }
    
    async with httpx.AsyncClient() as client:
        # 1. Exchange code for token
        token_response = await client.post(token_url, data=data)
        if token_response.status_code != 200:
            print(f"Token Error: {token_response.text}")
            raise HTTPException(status_code=400, detail="Failed to fetch token from Google")
        
        tokens = token_response.json()
        access_token = tokens.get("access_token")
        
        # 2. Get user info
        user_info_url = "https://www.googleapis.com/oauth2/v3/userinfo"
        user_info_response = await client.get(
            user_info_url, headers={"Authorization": f"Bearer {access_token}"}
        )
        if user_info_response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to fetch user info from Google")
        
        user_info = user_info_response.json()
        email = user_info.get("email")
        
        user_record = await users_collection.find_one({"email": email, "is_deleted": {"$ne": True}})
        if not user_record:
            # Redirect to frontend with error
            return RedirectResponse(f"{FRONTEND_URL}/?error=Account+not+found.+Please+contact+support.")
        
        # 4. Create system token
        token = create_access_token(user_record)
        
        # 5. Set cookie and redirect to dashboard
        redirect_response = RedirectResponse(f"{FRONTEND_URL}/dashboard")
        redirect_response.set_cookie(
            key="token",
            value=token,
            httponly=True,
            max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            samesite="lax",
            secure=False, # Set to True in production with HTTPS
        )
        return redirect_response
