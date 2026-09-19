"""Cache tests: list caching, user-scoped keys, and invalidation on writes."""

import uuid

from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.todos import build_list_cache_key
from app.models.todo import Todo
from app.models.user import User


def user_list_keys(redis_store: dict, user_id) -> list[str]:
    prefix = f"todos:list:{user_id}:"
    return [key for key in redis_store if key.startswith(prefix)]


async def create_todo(client: AsyncClient, headers: dict, title: str) -> dict:
    response = await client.post(
        "/api/v1/todos", json={"title": title}, headers=headers
    )
    assert response.status_code == 201
    return response.json()


async def test_list_caches_response_and_serves_hits(
    client: AsyncClient,
    auth_headers_a: dict,
    user_a: User,
    redis_store: dict,
    db_session: AsyncSession,
):
    todo = await create_todo(client, auth_headers_a, "Original title")

    first = await client.get("/api/v1/todos", headers=auth_headers_a)
    assert first.status_code == 200
    expected_key = build_list_cache_key(user_a.id, 1, 20, None, None, None, None, None)
    assert expected_key in redis_store

    # Rename behind the API's back: a cache hit must still serve the stale title.
    await db_session.execute(
        update(Todo)
        .where(Todo.id == uuid.UUID(todo["id"]))
        .values(title="Renamed behind cache")
    )
    await db_session.commit()

    second = await client.get("/api/v1/todos", headers=auth_headers_a)
    assert second.status_code == 200
    assert second.json()["items"][0]["title"] == "Original title"


async def test_cache_keys_are_user_scoped(
    client: AsyncClient,
    auth_headers_a: dict,
    auth_headers_b: dict,
    user_a: User,
    user_b: User,
    redis_store: dict,
):
    await create_todo(client, auth_headers_a, "A private todo")

    response_a = await client.get("/api/v1/todos", headers=auth_headers_a)
    response_b = await client.get("/api/v1/todos", headers=auth_headers_b)

    assert (
        build_list_cache_key(user_a.id, 1, 20, None, None, None, None, None)
        in redis_store
    )
    assert (
        build_list_cache_key(user_b.id, 1, 20, None, None, None, None, None)
        in redis_store
    )
    assert response_a.json()["total"] == 1
    assert response_b.json()["total"] == 0


def test_cache_key_distinguishes_literal_all_keyword():
    # A keyword of "all" must not share the no-keyword cache entry.
    user_id = uuid.uuid4()
    with_keyword = build_list_cache_key(user_id, 1, 20, None, None, "all", None, None)
    without_keyword = build_list_cache_key(user_id, 1, 20, None, None, None, None, None)
    assert with_keyword != without_keyword


async def test_create_invalidates_list_cache(
    client: AsyncClient, auth_headers_a: dict, user_a: User, redis_store: dict
):
    await create_todo(client, auth_headers_a, "First")
    await client.get("/api/v1/todos", headers=auth_headers_a)
    assert user_list_keys(redis_store, user_a.id)

    response = await client.post(
        "/api/v1/todos", json={"title": "Second"}, headers=auth_headers_a
    )
    assert response.status_code == 201
    assert user_list_keys(redis_store, user_a.id) == []


async def test_update_invalidates_list_cache(
    client: AsyncClient, auth_headers_a: dict, user_a: User, redis_store: dict
):
    todo = await create_todo(client, auth_headers_a, "To update")
    await client.get("/api/v1/todos", headers=auth_headers_a)
    assert user_list_keys(redis_store, user_a.id)

    response = await client.put(
        f"/api/v1/todos/{todo['id']}",
        json={"completed": True},
        headers=auth_headers_a,
    )
    assert response.status_code == 200
    assert user_list_keys(redis_store, user_a.id) == []


async def test_delete_invalidates_list_cache(
    client: AsyncClient, auth_headers_a: dict, user_a: User, redis_store: dict
):
    todo = await create_todo(client, auth_headers_a, "To delete")
    await client.get("/api/v1/todos", headers=auth_headers_a)
    assert user_list_keys(redis_store, user_a.id)

    response = await client.delete(
        f"/api/v1/todos/{todo['id']}", headers=auth_headers_a
    )
    assert response.status_code == 204
    assert user_list_keys(redis_store, user_a.id) == []
