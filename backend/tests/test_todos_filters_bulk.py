"""Filtering, tag attachment, bulk status, and cache scoping tests."""

import uuid
from datetime import datetime, timedelta, timezone

from httpx import AsyncClient

from app.api.v1.todos import build_list_cache_key
from app.models.user import User


def user_list_keys(redis_store: dict, user_id) -> list[str]:
    prefix = f"todos:list:{user_id}:"
    return [key for key in redis_store if key.startswith(prefix)]


async def create_todo(
    client: AsyncClient, headers: dict, title: str, description=None
) -> dict:
    payload: dict = {"title": title}
    if description is not None:
        payload["description"] = description
    response = await client.post("/api/v1/todos", json=payload, headers=headers)
    assert response.status_code == 201
    return response.json()


async def create_tag(client: AsyncClient, headers: dict, name: str) -> dict:
    response = await client.post("/api/v1/tags", json={"name": name}, headers=headers)
    assert response.status_code == 201
    return response.json()


async def test_filter_by_keyword(client: AsyncClient, auth_headers_a: dict):
    await create_todo(client, auth_headers_a, "Buy groceries")
    await create_todo(client, auth_headers_a, "Walk the dog")

    response = await client.get(
        "/api/v1/todos", params={"keyword": "grocer"}, headers=auth_headers_a
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "Buy groceries"


async def test_filter_by_status(client: AsyncClient, auth_headers_a: dict):
    await create_todo(client, auth_headers_a, "Incomplete one")
    done = await create_todo(client, auth_headers_a, "Completed one")
    await client.put(
        f"/api/v1/todos/{done['id']}",
        json={"completed": True},
        headers=auth_headers_a,
    )

    active = await client.get(
        "/api/v1/todos", params={"status": "active"}, headers=auth_headers_a
    )
    assert active.json()["total"] == 1
    assert active.json()["items"][0]["title"] == "Incomplete one"

    completed = await client.get(
        "/api/v1/todos",
        params={"status": "completed"},
        headers=auth_headers_a,
    )
    assert completed.json()["total"] == 1
    assert completed.json()["items"][0]["title"] == "Completed one"


async def test_filter_by_tag(client: AsyncClient, auth_headers_a: dict):
    tag = await create_tag(client, auth_headers_a, "Work")
    tagged = await create_todo(client, auth_headers_a, "Tagged todo")
    await create_todo(client, auth_headers_a, "Untagged todo")
    attach = await client.post(
        f"/api/v1/todos/{tagged['id']}/tags",
        json={"tag_id": tag["id"]},
        headers=auth_headers_a,
    )
    assert attach.status_code == 201

    response = await client.get(
        "/api/v1/todos", params={"tag_id": tag["id"]}, headers=auth_headers_a
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "Tagged todo"
    assert data["items"][0]["tags"][0]["name"] == "Work"


async def test_filter_by_date_range(client: AsyncClient, auth_headers_a: dict):
    await create_todo(client, auth_headers_a, "Today todo")
    # created_at is stored in UTC; anchor the filter to the UTC date.
    today = datetime.now(timezone.utc).date()

    inside = await client.get(
        "/api/v1/todos",
        params={"date_from": today.isoformat(), "date_to": today.isoformat()},
        headers=auth_headers_a,
    )
    assert inside.json()["total"] == 1

    yesterday = today - timedelta(days=1)
    before = await client.get(
        "/api/v1/todos",
        params={"date_from": yesterday.isoformat(), "date_to": yesterday.isoformat()},
        headers=auth_headers_a,
    )
    assert before.json()["total"] == 0


async def test_attach_other_users_tag_forbidden(
    client: AsyncClient, auth_headers_a: dict, auth_headers_b: dict
):
    foreign_tag = await create_tag(client, auth_headers_b, "B's tag")
    todo = await create_todo(client, auth_headers_a, "A's todo")

    response = await client.post(
        f"/api/v1/todos/{todo['id']}/tags",
        json={"tag_id": foreign_tag["id"]},
        headers=auth_headers_a,
    )
    assert response.status_code == 403


async def test_attach_tag_to_other_users_todo_forbidden(
    client: AsyncClient, auth_headers_a: dict, auth_headers_b: dict
):
    tag = await create_tag(client, auth_headers_a, "A's tag")
    foreign_todo = await create_todo(client, auth_headers_b, "B's todo")

    response = await client.post(
        f"/api/v1/todos/{foreign_todo['id']}/tags",
        json={"tag_id": tag["id"]},
        headers=auth_headers_a,
    )
    assert response.status_code == 403


async def test_attach_is_idempotent(client: AsyncClient, auth_headers_a: dict):
    tag = await create_tag(client, auth_headers_a, "Work")
    todo = await create_todo(client, auth_headers_a, "Todo")

    first = await client.post(
        f"/api/v1/todos/{todo['id']}/tags",
        json={"tag_id": tag["id"]},
        headers=auth_headers_a,
    )
    assert first.status_code == 201
    second = await client.post(
        f"/api/v1/todos/{todo['id']}/tags",
        json={"tag_id": tag["id"]},
        headers=auth_headers_a,
    )
    assert second.status_code == 200
    assert len(second.json()["tags"]) == 1


async def test_detach_tag(client: AsyncClient, auth_headers_a: dict):
    tag = await create_tag(client, auth_headers_a, "Work")
    todo = await create_todo(client, auth_headers_a, "Todo")
    await client.post(
        f"/api/v1/todos/{todo['id']}/tags",
        json={"tag_id": tag["id"]},
        headers=auth_headers_a,
    )

    detached = await client.delete(
        f"/api/v1/todos/{todo['id']}/tags/{tag['id']}", headers=auth_headers_a
    )
    assert detached.status_code == 200
    assert detached.json()["tags"] == []

    missing = await client.delete(
        f"/api/v1/todos/{todo['id']}/tags/{tag['id']}", headers=auth_headers_a
    )
    assert missing.status_code == 404


async def test_bulk_status_updates_only_own_todos(
    client: AsyncClient, auth_headers_a: dict, auth_headers_b: dict
):
    own = await create_todo(client, auth_headers_a, "Own todo")
    foreign = await create_todo(client, auth_headers_b, "B's todo")

    response = await client.patch(
        "/api/v1/todos/bulk-status",
        json={
            "todo_ids": [own["id"], foreign["id"]],
            "completed": True,
        },
        headers=auth_headers_a,
    )
    assert response.status_code == 200
    assert response.json() == {"updated": 1, "requested": 2}

    own_after = await client.get(f"/api/v1/todos/{own['id']}", headers=auth_headers_a)
    assert own_after.json()["completed"] is True

    foreign_after = await client.get(
        f"/api/v1/todos/{foreign['id']}", headers=auth_headers_b
    )
    assert foreign_after.json()["completed"] is False


async def test_bulk_status_ignores_unknown_ids(
    client: AsyncClient, auth_headers_a: dict
):
    todo = await create_todo(client, auth_headers_a, "Own todo")

    response = await client.patch(
        "/api/v1/todos/bulk-status",
        json={
            "todo_ids": [str(uuid.uuid4()), todo["id"]],
            "completed": True,
        },
        headers=auth_headers_a,
    )
    assert response.json() == {"updated": 1, "requested": 2}


async def test_cache_keys_scoped_by_filters(
    client: AsyncClient,
    auth_headers_a: dict,
    user_a: User,
    redis_store: dict,
):
    await create_todo(client, auth_headers_a, "Filterable")

    await client.get("/api/v1/todos", headers=auth_headers_a)
    await client.get(
        "/api/v1/todos",
        params={"status": "completed"},
        headers=auth_headers_a,
    )

    assert (
        build_list_cache_key(user_a.id, 1, 20, None, None, None, None, None)
        in redis_store
    )
    assert (
        build_list_cache_key(user_a.id, 1, 20, "completed", None, None, None, None)
        in redis_store
    )
    assert len(user_list_keys(redis_store, user_a.id)) == 2


async def test_tag_writes_invalidate_cache(
    client: AsyncClient,
    auth_headers_a: dict,
    user_a: User,
    redis_store: dict,
):
    tag = await create_tag(client, auth_headers_a, "Work")
    todo = await create_todo(client, auth_headers_a, "Todo")

    await client.get("/api/v1/todos", headers=auth_headers_a)
    assert user_list_keys(redis_store, user_a.id)

    await client.post(
        f"/api/v1/todos/{todo['id']}/tags",
        json={"tag_id": tag["id"]},
        headers=auth_headers_a,
    )
    assert user_list_keys(redis_store, user_a.id) == []

    await client.get("/api/v1/todos", headers=auth_headers_a)
    await client.delete(
        f"/api/v1/todos/{todo['id']}/tags/{tag['id']}", headers=auth_headers_a
    )
    assert user_list_keys(redis_store, user_a.id) == []


async def test_tag_rename_invalidates_cache(
    client: AsyncClient,
    auth_headers_a: dict,
    user_a: User,
    redis_store: dict,
):
    tag = await create_tag(client, auth_headers_a, "Work")
    await create_todo(client, auth_headers_a, "Todo")

    await client.get("/api/v1/todos", headers=auth_headers_a)
    assert user_list_keys(redis_store, user_a.id)

    response = await client.patch(
        f"/api/v1/tags/{tag['id']}",
        json={"name": "Deep Work"},
        headers=auth_headers_a,
    )
    assert response.status_code == 200
    assert user_list_keys(redis_store, user_a.id) == []


async def test_bulk_status_invalidates_cache(
    client: AsyncClient,
    auth_headers_a: dict,
    user_a: User,
    redis_store: dict,
):
    todo = await create_todo(client, auth_headers_a, "Todo")

    await client.get("/api/v1/todos", headers=auth_headers_a)
    assert user_list_keys(redis_store, user_a.id)

    await client.patch(
        "/api/v1/todos/bulk-status",
        json={"todo_ids": [todo["id"]], "completed": True},
        headers=auth_headers_a,
    )
    assert user_list_keys(redis_store, user_a.id) == []
