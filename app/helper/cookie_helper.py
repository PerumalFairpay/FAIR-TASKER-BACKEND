from fastapi import Request, Response
from app.core.config import ACCESS_TOKEN_EXPIRE_MINUTES


def set_auth_cookie(response: Response, request: Request, token: str, httponly: bool = False):
    """
    Sets auth token cookie dynamically.
    For Ngrok or HTTPS requests: uses SameSite='none' and Secure=True.
    For local HTTP requests: uses SameSite='lax' and Secure=False.
    """
    forwarded_proto = request.headers.get("x-forwarded-proto", "").lower()
    host = request.headers.get("host", "").lower()

    is_https = (
        request.url.scheme == "https"
        or forwarded_proto == "https"
        or "ngrok" in host
    )

    samesite = "none" if is_https else "lax"
    secure = True if is_https else False

    response.set_cookie(
        key="token",
        value=token,
        httponly=httponly,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite=samesite,
        secure=secure,
    )


def delete_auth_cookie(response: Response, request: Request):
    """
    Deletes auth token cookie matching the request environment parameters.
    """
    forwarded_proto = request.headers.get("x-forwarded-proto", "").lower()
    host = request.headers.get("host", "").lower()

    is_https = (
        request.url.scheme == "https"
        or forwarded_proto == "https"
        or "ngrok" in host
    )

    samesite = "none" if is_https else "lax"
    secure = True if is_https else False

    response.delete_cookie(
        key="token",
        samesite=samesite,
        secure=secure,
    )
