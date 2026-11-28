from fastapi import APIRouter, Response, Request, Depends
from app.models import UserLogin
from app.models.user import ForgotPasswordRequest, ResetPasswordRequest
from app.auth import get_current_user
from app.services.api.auth import AuthService
from app.helper import success_response, error_response, set_auth_cookie, delete_auth_cookie

router = APIRouter()


@router.post("/login")
async def login(user: UserLogin, response: Response, request: Request):
    user_data, token, error = await AuthService.login(user)
    if error:
        return error_response(message=error, status_code=400)

    # Set cookie (matches FLEETGLIDE-AI-BACKEND dynamic cookie setting)
    set_auth_cookie(response=response, request=request, token=token, httponly=False)

    return {
        "success": True,
        "message": "Login successful",
        "data": user_data,
        "meta": {"token": token},
    }


@router.post("/logout")
async def logout(response: Response, request: Request):
    delete_auth_cookie(response=response, request=request)
    return {
        "success": True,
        "message": "Logged out successfully",
    }


@router.get("/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    user_data, error = await AuthService.get_me(current_user)
    if error:
        return error_response(message=error, status_code=500)
    return success_response(message="Success", data=user_data)


@router.post("/forgot-password")
async def forgot_password(payload: ForgotPasswordRequest):
    success, error = await AuthService.forgot_password(payload.email)
    if error:
        return error_response(message=error, status_code=400)
    return success_response(
        message="If an account exists with this email, a password reset link has been sent."
    )


@router.post("/reset-password")
async def reset_password(payload: ResetPasswordRequest):
    success, error = await AuthService.reset_password(payload.token, payload.new_password)
    if error:
        return error_response(message=error, status_code=400)
    return success_response(message="Password reset successfully. You can now login with your new password.")
