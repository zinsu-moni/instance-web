from pathlib import Path

import httpx
from fastapi import FastAPI, Form, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.client import backend_client
from app.config import settings
from app.dependencies import AuthRedirect, clear_auth_cookies, redirect_to_login, set_auth_cookies, validate_csrf


BASE_DIR = Path(__file__).resolve().parent.parent

app = FastAPI(title="Insighta Labs+ Web Portal")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

templates = Jinja2Templates(directory=BASE_DIR / "templates")


@app.exception_handler(AuthRedirect)
async def auth_redirect_handler(request: Request, exc: AuthRedirect) -> RedirectResponse:
    return redirect_to_login()


@app.get("/login", response_class=HTMLResponse)
async def login(request: Request) -> HTMLResponse | RedirectResponse:
    access_token = request.cookies.get("access_token")
    if access_token:
        try:
            if await backend_client.get_me(access_token):
                return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
        except Exception:
            pass

    return templates.TemplateResponse(
        "login.html",
        {"request": request, "backend_url": settings.backend_url},
    )


@app.get("/auth/callback")
async def auth_callback(access_token: str, refresh_token: str) -> RedirectResponse:
    response = RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    set_auth_cookies(response, access_token, refresh_token)
    return response


@app.post("/auth/logout")
async def logout(request: Request, csrf_token: str = Form(...)) -> RedirectResponse:
    validate_csrf(request, csrf_token)
    refresh_token = request.cookies.get("refresh_token")
    try:
        await backend_client.logout(refresh_token)
    except httpx.HTTPError:
        pass

    response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    clear_auth_cookies(response)
    return response


@app.get("/")
async def root() -> RedirectResponse:
    return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
