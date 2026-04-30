from datetime import datetime, timezone
from io import BytesIO
from math import ceil
from pathlib import Path
from typing import Any

import httpx
from fastapi import Depends, FastAPI, Form, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
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
FRONTEND_CALLBACK_URL = "http://127.0.0.1:5000/auth/callback"


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


def _profile_filters(
    *,
    gender: str | None = None,
    country_id: str | None = None,
    age_group: str | None = None,
    min_age: int | None = None,
    max_age: int | None = None,
    sort_by: str | None = None,
    order: str | None = None,
    page: int | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    raw_filters = {
        "gender": gender,
        "country_id": country_id,
        "age_group": age_group,
        "min_age": min_age,
        "max_age": max_age,
        "sort_by": sort_by,
        "order": order,
        "page": page,
        "limit": limit,
    }
    cleaned_filters: dict[str, Any] = {}
    for key, value in raw_filters.items():
        if value is None:
            continue
        if isinstance(value, str):
            trimmed = value.strip()
            if not trimmed:
                continue
            cleaned_filters[key] = trimmed
            continue
        cleaned_filters[key] = value
    return cleaned_filters


def _profile_filter_error(filters: dict[str, Any]) -> str:
    country_id = filters.get("country_id")
    if country_id:
        return "The backend rejected this country filter. Use the backend's actual country identifier, not a display name."
    return "The backend rejected one or more profile filters. Adjust the filter values and try again."


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
    github_url = httpx.URL(f"{settings.backend_url}/auth/github").copy_add_param(
        "redirect_uri",
        FRONTEND_CALLBACK_URL,
    )
    return RedirectResponse(url=str(github_url), status_code=status.HTTP_303_SEE_OTHER)


@app.get("/auth/callback")
async def auth_callback(
    access_token: str | None = None,
    refresh_token: str | None = None,
):
    if not access_token or not refresh_token:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

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


@app.get("/profiles", response_class=HTMLResponse)
async def profiles(
    request: Request,
    user: dict[str, Any] = Depends(get_current_user),
    gender: str | None = None,
    country_id: str | None = None,
    age_group: str | None = None,
    min_age: int | None = None,
    max_age: int | None = None,
    sort_by: str | None = None,
    order: str | None = None,
    page: int = 1,
    limit: int = 10,
):
    access_token = getattr(request.state, "access_token", request.cookies["access_token"])
    filters = _profile_filters(
        gender=gender,
        country_id=country_id,
        age_group=age_group,
        min_age=min_age,
        max_age=max_age,
        sort_by=sort_by,
        order=order,
        page=page,
        limit=limit,
    )

    error_message: str | None = None
    profiles: list[dict[str, Any]] = []
    total = 0
    total_pages = 1

    try:
        payload = await backend_client.get_profiles(access_token, filters)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code != status.HTTP_400_BAD_REQUEST:
            raise
        error_message = _profile_filter_error(filters)
    else:
        profiles = _paginated_items(payload)
        total = _paginated_total(payload)
        total_pages = ceil(total / limit) if total else 1

    for profile in profiles:
        profile["created_at_readable"] = _readable_date(profile.get("created_at"))

    return templates.TemplateResponse(
        request=request,
        name="profiles.html",
        context={
            "user": user,
            "profiles": profiles,
            "filters": filters,
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": total_pages,
            "error_message": error_message,
            "csrf_token": request.state.csrf_token,
        },
    )


@app.get("/profiles/export")
async def export_profiles(
    request: Request,
    user: dict[str, Any] = Depends(get_current_user),
    gender: str | None = None,
    country_id: str | None = None,
    age_group: str | None = None,
    min_age: int | None = None,
    max_age: int | None = None,
    sort_by: str | None = None,
    order: str | None = None,
    page: int = 1,
    limit: int = 10,
):
    access_token = getattr(request.state, "access_token", request.cookies["access_token"])
    filters = _profile_filters(
        gender=gender,
        country_id=country_id,
        age_group=age_group,
        min_age=min_age,
        max_age=max_age,
        sort_by=sort_by,
        order=order,
        page=page,
        limit=limit,
    )

    try:
        csv_bytes = await backend_client.export_profiles(access_token, filters)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == status.HTTP_400_BAD_REQUEST:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=_profile_filter_error(filters),
            ) from exc
        raise
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    headers = {
        "Content-Disposition": f'attachment; filename="profiles_{timestamp}.csv"',
    }
    return StreamingResponse(
        BytesIO(csv_bytes),
        media_type="text/csv",
        headers=headers,
    )


@app.get("/")
async def root():
    return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
