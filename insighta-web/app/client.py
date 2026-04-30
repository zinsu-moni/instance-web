from typing import Any

import httpx

from app.config import settings


class BackendClient:
    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or settings.backend_url).rstrip("/")

    def _auth_headers(self, access_token: str | None = None) -> dict[str, str]:
        headers = {"X-API-Version": "1"}
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"
        return headers

    async def get_me(self, access_token: str) -> dict[str, Any] | None:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=10.0) as client:
            response = await client.get("/auth/me", headers=self._auth_headers(access_token))
            if response.status_code == 401:
                raise httpx.HTTPStatusError("Unauthorized", request=response.request, response=response)
            if response.is_error:
                return None
            return response.json()

    async def refresh_tokens(self, refresh_token: str) -> dict[str, str] | None:
        headers = self._auth_headers(refresh_token)
        async with httpx.AsyncClient(base_url=self.base_url, timeout=10.0) as client:
            response = await client.post("/auth/refresh", headers=headers)
            if response.is_error:
                return None
            data = response.json()
            if not data.get("access_token") or not data.get("refresh_token"):
                return None
            return data

    async def get_github_auth_url(self) -> str | None:
        async with httpx.AsyncClient(
            base_url=self.base_url,
            timeout=10.0,
            follow_redirects=False,
        ) as client:
            response = await client.get("/auth/github")
            if response.status_code not in {301, 302, 303, 307, 308}:
                return None
            return response.headers.get("location")

    async def exchange_github_callback(
        self,
        code: str,
        state: str,
        redirect_uri: str | None = None,
    ) -> dict[str, str] | None:
        params: dict[str, str] = {"code": code, "state": state}
        if redirect_uri:
            params["redirect_uri"] = redirect_uri

        async with httpx.AsyncClient(base_url=self.base_url, timeout=20.0) as client:
            response = await client.get("/auth/github/callback", params=params)
            if response.is_error:
                return None
            data = response.json()
            if not data.get("access_token") or not data.get("refresh_token"):
                return None
            return data

    async def logout(self, refresh_token: str | None) -> None:
        if not refresh_token:
            return
        async with httpx.AsyncClient(base_url=self.base_url, timeout=10.0) as client:
            await client.post("/auth/logout", headers=self._auth_headers(refresh_token))

    async def get_profiles(self, access_token: str, filters: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=20.0) as client:
            response = await client.get(
                "/api/profiles",
                params=filters,
                headers=self._auth_headers(access_token),
            )
            response.raise_for_status()
            return response.json()

    async def get_profile(self, access_token: str, profile_id: str) -> dict[str, Any] | None:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=20.0) as client:
            response = await client.get(
                f"/api/profiles/{profile_id}",
                headers=self._auth_headers(access_token),
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()

    async def search_profiles(
        self,
        access_token: str,
        query: str,
        page: int,
        limit: int,
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=20.0) as client:
            response = await client.get(
                "/api/profiles/search",
                params={"q": query, "page": page, "limit": limit},
                headers=self._auth_headers(access_token),
            )
            response.raise_for_status()
            return response.json()

    async def export_profiles(self, access_token: str, filters: dict[str, Any]) -> bytes:
        params = {"format": "csv", **filters}
        async with httpx.AsyncClient(base_url=self.base_url, timeout=60.0) as client:
            response = await client.get(
                "/api/profiles/export",
                params=params,
                headers=self._auth_headers(access_token),
            )
            response.raise_for_status()
            return response.content


backend_client = BackendClient()
