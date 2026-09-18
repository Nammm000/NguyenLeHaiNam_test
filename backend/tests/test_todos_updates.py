"""Business-logic tests: completed toggle and partial-update semantics."""

from httpx import AsyncClient


async def create_todo(
    client: AsyncClient, headers: dict, title: str, description: str | None = None
) -> dict:
    payload: dict = {"title": title}
    if description is not None:
        payload["description"] = description
    response = await client.post("/api/v1/todos", json=payload, headers=headers)
    assert response.status_code == 201
    return response.json()


async def test_completed_toggle_true_to_false_persists(
    client: AsyncClient, auth_headers_a: dict
):
    todo = await create_todo(client, auth_headers_a, "Toggle me")
    todo_id = todo["id"]

    put = await client.put(
        f"/api/v1/todos/{todo_id}", json={"completed": True}, headers=auth_headers_a
    )
    assert put.status_code == 200
    assert put.json()["completed"] is True

    put = await client.put(
        f"/api/v1/todos/{todo_id}", json={"completed": False}, headers=auth_headers_a
    )
    assert put.status_code == 200
    assert put.json()["completed"] is False

    got = await client.get(f"/api/v1/todos/{todo_id}", headers=auth_headers_a)
    assert got.status_code == 200
    assert got.json()["completed"] is False


async def test_title_only_update_preserves_description(
    client: AsyncClient, auth_headers_a: dict
):
    todo = await create_todo(
        client, auth_headers_a, "Original title", "Keep this description"
    )
    todo_id = todo["id"]

    put = await client.put(
        f"/api/v1/todos/{todo_id}", json={"title": "New title"}, headers=auth_headers_a
    )
    assert put.status_code == 200

    got = await client.get(f"/api/v1/todos/{todo_id}", headers=auth_headers_a)
    assert got.status_code == 200
    data = got.json()
    assert data["title"] == "New title"
    assert data["description"] == "Keep this description"
