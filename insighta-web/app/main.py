from pathlib import Path
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import Depends, FastAPI, Form, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

from app.client import backend_client
from app.config import settings
from app.dependencies import (
    AuthRedirect,
    clear_auth_cookies,
    get_current_user,
    redirect_to_login,
    set_auth_cookies,
    validate_csrf,
)


BASE_DIR = Path(__file__).resolve().parent.parent


app = FastAPI(title="Insighta Labs+ Web Portal")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8000"],  # Adjust as needed for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

templates = Jinja2Templates(directory=BASE_DIR / "templates")


@app.exception_handler(AuthRedirect)
async def auth_redirect_handler(request: Request, exc: AuthRedirect):
    return redirect_to_login()


def _paginated_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("items", "profiles", "data", "results"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
    return []


def _paginated_total(payload: dict[str, Any]) -> int:
    for key in ("total", "count", "total_count"):
        value = payload.get(key)
        if isinstance(value, int):
            return value
    return len(_paginated_items(payload))


def _readable_date(value: Any) -> str:
    if not value:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%b %d, %Y")
    if not isinstance(value, str):
        return str(value)

    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return value

    if parsed.tzinfo:
        parsed = parsed.astimezone(timezone.utc)
    return parsed.strftime("%b %d, %Y")


@app.get("/login", response_class=HTMLResponse)
async def login(request: Request):
    access_token = request.cookies.get("access_token")
    if access_token:
        try:
            if await backend_client.get_me(access_token):
                return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
        except Exception:
            pass

    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={},
    )


@app.get("/auth/login")
async def auth_login(request: Request):
    callback_url = str(request.url_for("auth_callback"))
    github_url = httpx.URL(f"{settings.backend_url}/auth/github").copy_add_param("redirect_uri", callback_url)
    return RedirectResponse(url=str(github_url), status_code=status.HTTP_303_SEE_OTHER)


@app.get("/auth/callback")
async def auth_callback(access_token: str, refresh_token: str):
    response = RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    set_auth_cookies(response, access_token, refresh_token)
    return response


@app.post("/auth/logout")
async def logout(request: Request, csrf_token: str = Form(...)):
    validate_csrf(request, csrf_token)
    refresh_token = request.cookies.get("refresh_token")
    try:
        await backend_client.logout(refresh_token)
    except httpx.HTTPError:
        pass

    response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    clear_auth_cookies(response)
    return response


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, user: dict[str, Any] = Depends(get_current_user)):
    access_token = getattr(request.state, "access_token", request.cookies["access_token"])

    totals_payload = await backend_client.get_profiles(access_token, {"limit": 1})
    recent_payload = await backend_client.get_profiles(
        access_token,
        {"limit": 10, "sort_by": "created_at", "order": "desc"},
    )

    recent_profiles = _paginated_items(recent_payload)
    for profile in recent_profiles:
        profile["created_at_readable"] = _readable_date(profile.get("created_at"))

    country_ids = {
        profile.get("country_id")
        for profile in recent_profiles
        if profile.get("country_id") is not None
    }
    male_count = sum(1 for profile in recent_profiles if profile.get("gender") == "male")
    female_count = sum(1 for profile in recent_profiles if profile.get("gender") == "female")

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "user": user,
            "total": _paginated_total(totals_payload),
            "total_countries": len(country_ids),
            "male_count": male_count,
            "female_count": female_count,
            "recent_profiles": recent_profiles,
            "csrf_token": request.state.csrf_token,
        },
    )


@app.get("/")
async def root():
    return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
