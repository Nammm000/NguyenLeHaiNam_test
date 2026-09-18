"""Security tests: expired, tampered, and wrong-type tokens are rejected."""

from datetime import timedelta

from httpx import AsyncClient

from app.core.security import create_access_token, create_refresh_token
from app.models.user import User


async def request_me(client: AsyncClient, token: str) -> int:
    response = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    return response.status_code


async def test_expired_token_rejected(client: AsyncClient, user_a: User):
    token = create_access_token(
        data={"sub": str(user_a.id)}, expires_delta=timedelta(minutes=-5)
    )
    assert await request_me(client, token) == 401


async def test_tampered_token_rejected(client: AsyncClient, user_a: User):
    token = create_access_token(data={"sub": str(user_a.id)})
    tampered_suffix = "AAA" if token[-3:] != "AAA" else "BBB"
    tampered = token[:-3] + tampered_suffix
    assert await request_me(client, tampered) == 401


async def test_refresh_token_rejected_as_access_token(
    client: AsyncClient, user_a: User
):
    token = create_refresh_token(data={"sub": str(user_a.id)})
    assert await request_me(client, token) == 401
