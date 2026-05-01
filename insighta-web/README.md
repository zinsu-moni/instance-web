# Insighta Labs+ Web Portal

## Project Overview

Insighta Labs+ Web Portal is a standalone FastAPI and Jinja2 application for viewing profile analytics from the Insighta backend. It provides a browser-based dashboard, profile listing, profile detail view, natural-language search, account page, CSV export, and GitHub-backed authentication flow.

The portal does not own a database. It stores session tokens in browser cookies and communicates with the backend over HTTP.

## Backend Connection

Set the backend base URL in the portal environment:

```env
BACKEND_URL=https://your-backend-url.railway.app
FRONTEND_URL=https://your-web-portal.railway.app
SECRET_KEY=your-random-secret-key-for-csrf
PORT=5000
```

For production with the hosted Vercel backend, set these on the frontend deployment:

```env
BACKEND_URL=https://hng-task-lemon.vercel.app
FRONTEND_URL=https://instance-web.vercel.app
```

The portal uses `BACKEND_URL` to call:

- `GET /auth/me`
- `POST /auth/refresh`
- `POST /auth/logout`
- `GET /api/profiles`
- `GET /api/profiles/{profile_id}`
- `GET /api/profiles/search`
- `GET /api/profiles/export`

## Authentication Flow

1. The user opens `/login`.
2. The user clicks the GitHub login button.
3. The portal redirects the browser to `BACKEND_URL/auth/github?redirect_uri=FRONTEND_URL/auth/callback`.
4. The backend completes the GitHub OAuth callback.
5. The backend redirects back to `/auth/callback` on the portal with `access_token` and `refresh_token` query params.
6. The portal validates the access token with `GET /auth/me` and stores both tokens in HTTP-only cookies.
7. The portal redirects the user to `/dashboard`.
8. Protected pages call `get_current_user`, which validates the current access token through the backend.
9. If the access token is expired, the portal attempts to refresh tokens and updates the cookies.
10. If authentication fails, the user is redirected back to `/login`.

## HTTP-Only Cookies

The portal stores `access_token` and `refresh_token` in HTTP-only cookies so application JavaScript cannot read them. This reduces token exposure if a script injection bug appears in the frontend.

Cookies are configured with `SameSite=Lax` for normal portal navigation. In production, deploy over HTTPS and enable secure cookies.

## CSRF Protection

The portal sets a separate `csrf_token` cookie and passes the same token into templates. Mutating forms, such as logout, submit the token in a hidden input.

When a form posts back, the portal compares the submitted token with the cookie value. If the values do not match, the request is rejected.

## Pages

- `/login`: Starts GitHub login.
- `/auth/callback`: Receives backend-issued tokens and sets portal cookies.
- `/dashboard`: Shows profile totals and recent profile activity.
- `/profiles`: Lists profiles with filters, sorting, pagination, and CSV export.
- `/profiles/export`: Downloads a CSV export using the selected filters.
- `/profiles/{profile_id}`: Shows a single profile and all profile fields.
- `/search`: Searches profiles using plain-English queries and paginated results.
- `/account`: Shows the current user's avatar, username, email, role, member date, and logout form.

## Running Locally

Install dependencies:

```bash
pip install -e .
```

Run the portal:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 5000
```

Open:

```text
http://localhost:5000/login
```

## Deployment On Railway

1. Create a Railway service for the web portal.
2. Set the service root to this project directory if the repository contains multiple apps.
3. Add the required environment variables:

```env
BACKEND_URL=https://your-backend-url.railway.app
FRONTEND_URL=https://your-web-portal.railway.app
SECRET_KEY=replace-with-a-long-random-value
PORT=5000
```

4. Use a start command like:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

5. Deploy the portal.
6. Update the backend callback configuration so GitHub login returns users to the deployed portal URL.

## Required Backend Env Change

Add this to the backend `.env` for local development:

```env
WEB_PORTAL_CALLBACK=http://localhost:5000/auth/callback
```

For Railway, set it to the deployed portal URL:

```env
WEB_PORTAL_CALLBACK=https://your-web-portal.railway.app/auth/callback
```

In the backend `/auth/github/callback`, after issuing tokens, redirect back to the portal:

```python
redirect_url = (
    f"{WEB_PORTAL_CALLBACK}"
    f"?access_token={access_token}"
    f"&refresh_token={refresh_token}"
)
return RedirectResponse(redirect_url)
```
