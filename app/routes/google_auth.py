from fastapi import APIRouter
from fastapi.responses import RedirectResponse
from app.core.config import FRONTEND_URL, ACCESS_TOKEN_EXPIRE_MINUTES
from app.services.api.google_auth import GoogleAuthService

router = APIRouter()


@router.get("/login")
async def google_login():
    url, error = GoogleAuthService.get_login_url()
    if error:
        return RedirectResponse(f"{FRONTEND_URL}/?error=Google+OAuth+configuration+is+missing")
    return RedirectResponse(url)


@router.get("/callback")
async def google_callback(code: str):
    token, error = await GoogleAuthService.process_callback(code)
    if error:
        clean_error = error.replace(" ", "+")
        return RedirectResponse(f"{FRONTEND_URL}/?error={clean_error}")

    redirect_response = RedirectResponse(f"{FRONTEND_URL}/dashboard")
    redirect_response.set_cookie(
        key="token",
        value=token,
        httponly=True,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax",
        secure=False,
    )
    return redirect_response
