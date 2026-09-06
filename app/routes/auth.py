from fastapi import APIRouter, Response, Depends
from app.models import UserLogin
from app.auth import get_current_user
from app.core.config import ACCESS_TOKEN_EXPIRE_MINUTES
from app.services.api.auth import AuthService
from app.helper.response_helper import success_response, error_response

router = APIRouter()


@router.post("/login")
async def login(user: UserLogin, response: Response):
    user_data, token, error = await AuthService.login(user)
    if error:
        return error_response(message=error, status_code=400)

    # Set cookie
    response.set_cookie(
        key="token",
        value=token,
        httponly=True,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax",
        secure=False,
    )

    return success_response(
        message="Login successful",
        data=user_data,
        meta={"token": token}
    )


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("token")
    return success_response(message="Logged out successfully")


@router.get("/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    user_data, error = await AuthService.get_me(current_user)
    if error:
        return error_response(message=error, status_code=500)
    return success_response(message="Success", data=user_data)
