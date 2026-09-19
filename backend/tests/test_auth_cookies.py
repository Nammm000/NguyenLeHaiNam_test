"""Refresh-token cookie tests."""

import pytest
from httpx import AsyncClient


def refresh_cookies(response) -> list[str]:
    return [
        cookie
        for cookie in response.headers.get_list("set-cookie")
        if "refresh_token=" in cookie
    ]


@pytest.mark.asyncio
async def test_refresh_roundtrip_rotates_cookie(client: AsyncClient):
    """Cookie set at register works on /refresh and is rotated."""
    reg_response = await client.post(
        "/api/v1/auth/register",
        json={"email": "roundtrip@example.com", "password": "password123"},
    )
    assert reg_response.status_code == 201
    initial = refresh_cookies(reg_response)
    assert initial

    # No body: the client's cookie jar replays the refresh cookie
    response = await client.post("/api/v1/auth/refresh")
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" not in data

    rotated = refresh_cookies(response)
    assert rotated
    assert rotated[0] != initial[0]

    # The new access token is usable
    me = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {data['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["email"] == "roundtrip@example.com"


@pytest.mark.asyncio
async def test_refresh_without_cookie_returns_401(client: AsyncClient):
    """No refresh cookie at all."""
    response = await client.post("/api/v1/auth/refresh")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_with_invalid_cookie_returns_401(client: AsyncClient):
    """Garbage cookie value fails verification."""
    response = await client.post(
        "/api/v1/auth/refresh",
        headers={"Cookie": "refresh_token=garbage"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid refresh token"


@pytest.mark.asyncio
async def test_logout_clears_refresh_cookie(client: AsyncClient):
    """Logout drops the cookie and refresh then fails."""
    reg_response = await client.post(
        "/api/v1/auth/register",
        json={"email": "logout-cookie@example.com", "password": "password123"},
    )
    assert reg_response.status_code == 201
    token = reg_response.json()["access_token"]

    response = await client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    clearing = refresh_cookies(response)
    assert clearing
    assert "max-age=0" in clearing[0].lower()
    assert "path=/api/v1/auth" in clearing[0].lower()

    # Cookie is gone from the jar, so refresh no longer works
    post_logout = await client.post("/api/v1/auth/refresh")
    assert post_logout.status_code == 401
