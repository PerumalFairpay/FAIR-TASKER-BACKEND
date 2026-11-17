from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from app.core.config import FRONTEND_URL
from app.services.api.google_auth import GoogleAuthService
from app.helper import set_auth_cookie

router = APIRouter()


@router.get("/login")
async def google_login():
    url, error = GoogleAuthService.get_login_url()
    if error:
        return RedirectResponse(f"{FRONTEND_URL}/?error=Google+OAuth+configuration+is+missing")
    return RedirectResponse(url)


@router.get("/callback")
async def google_callback(code: str, request: Request):
    token, error = await GoogleAuthService.process_callback(code)
    if error:
        clean_error = error.replace(" ", "+")
        return RedirectResponse(f"{FRONTEND_URL}/?error={clean_error}")

    redirect_response = RedirectResponse(f"{FRONTEND_URL}/dashboard")
    set_auth_cookie(response=redirect_response, request=request, token=token, httponly=False)
    return redirect_response
