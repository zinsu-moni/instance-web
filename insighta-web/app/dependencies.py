from typing import Any
from uuid import uuid4

import httpx
from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse

from app.client import backend_client


class AuthRedirect(Exception):
    pass


def redirect_to_login() -> RedirectResponse:
    response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    clear_auth_cookies(response)
    return response


def clear_auth_cookies(response: Response) -> None:
    for cookie_name in ("access_token", "refresh_token", "csrf_token"):
        response.delete_cookie(cookie_name)


def set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    response.set_cookie("access_token", access_token, httponly=True, secure=False, samesite="lax")
    response.set_cookie("refresh_token", refresh_token, httponly=True, secure=False, samesite="lax")


def set_csrf_cookie(response: Response) -> str:
    csrf_token = str(uuid4())
    response.set_cookie("csrf_token", csrf_token, httponly=False, secure=False, samesite="lax")
    return csrf_token


def validate_csrf(request: Request, submitted_token: str | None) -> None:
    cookie_token = request.cookies.get("csrf_token")
    if not cookie_token or not submitted_token or cookie_token != submitted_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid CSRF token")


async def get_current_user(request: Request, response: Response) -> dict[str, Any]:
    access_token = request.cookies.get("access_token")
    refresh_token = request.cookies.get("refresh_token")

    if not access_token:
        raise AuthRedirect

    try:
        user = await backend_client.get_me(access_token)
        if user is None:
            raise AuthRedirect
        request.state.access_token = access_token
        request.state.csrf_token = set_csrf_cookie(response)
        request.state.current_user = user
        return user
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code != status.HTTP_401_UNAUTHORIZED or not refresh_token:
            raise AuthRedirect from exc
    except httpx.HTTPError as exc:
        raise AuthRedirect from exc

    try:
        refreshed = await backend_client.refresh_tokens(refresh_token)
    except httpx.HTTPError as exc:
        raise AuthRedirect from exc

    if not refreshed:
        raise AuthRedirect

    new_access_token = refreshed["access_token"]
    try:
        user = await backend_client.get_me(new_access_token)
    except httpx.HTTPError as exc:
        raise AuthRedirect from exc

    if user is None:
        raise AuthRedirect

    set_auth_cookies(response, new_access_token, refreshed["refresh_token"])
    request.state.access_token = new_access_token
    request.state.csrf_token = set_csrf_cookie(response)
    request.state.current_user = user
    return user


CurrentUser = Depends(get_current_user)
