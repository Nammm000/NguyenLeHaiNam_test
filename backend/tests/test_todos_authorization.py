"""Authorization boundary tests: users cannot access other users' todos."""

import uuid

from httpx import AsyncClient


async def create_todo(client: AsyncClient, headers: dict, title: str) -> dict:
    response = await client.post(
        "/api/v1/todos", json={"title": title}, headers=headers
    )
    assert response.status_code == 201
    return response.json()


async def test_other_user_cannot_read_update_delete_todo(
    client: AsyncClient, auth_headers_a: dict, auth_headers_b: dict
):
    todo = await create_todo(client, auth_headers_a, "A private todo")

    got = await client.get(f"/api/v1/todos/{todo['id']}", headers=auth_headers_b)
    assert got.status_code == 403

    put = await client.put(
        f"/api/v1/todos/{todo['id']}",
        json={"title": "hijacked"},
        headers=auth_headers_b,
    )
    assert put.status_code == 403

    deleted = await client.delete(f"/api/v1/todos/{todo['id']}", headers=auth_headers_b)
    assert deleted.status_code == 403


async def test_owner_can_read_update_delete_own_todo(
    client: AsyncClient, auth_headers_a: dict
):
    todo = await create_todo(client, auth_headers_a, "A private todo")

    got = await client.get(f"/api/v1/todos/{todo['id']}", headers=auth_headers_a)
    assert got.status_code == 200

    put = await client.put(
        f"/api/v1/todos/{todo['id']}",
        json={"title": "renamed"},
        headers=auth_headers_a,
    )
    assert put.status_code == 200
    assert put.json()["title"] == "renamed"

    deleted = await client.delete(f"/api/v1/todos/{todo['id']}", headers=auth_headers_a)
    assert deleted.status_code == 204


async def test_list_excludes_other_users_todos(
    client: AsyncClient, auth_headers_a: dict, auth_headers_b: dict
):
    await create_todo(client, auth_headers_a, "A private todo")

    response = await client.get("/api/v1/todos", headers=auth_headers_b)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert all(item["title"] != "A private todo" for item in data["items"])


async def test_missing_todo_returns_404(client: AsyncClient, auth_headers_a: dict):
    response = await client.get(f"/api/v1/todos/{uuid.uuid4()}", headers=auth_headers_a)
    assert response.status_code == 404
