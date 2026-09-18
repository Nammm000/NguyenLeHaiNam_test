"""Tag CRUD tests: creation, case-insensitive uniqueness, ownership."""

from httpx import AsyncClient


async def create_tag(
    client: AsyncClient, headers: dict, name: str, color: str | None = None
) -> dict:
    payload: dict = {"name": name}
    if color is not None:
        payload["color"] = color
    response = await client.post("/api/v1/tags", json=payload, headers=headers)
    assert response.status_code == 201
    return response.json()


async def test_create_tag_success(client: AsyncClient, auth_headers_a: dict):
    response = await client.post(
        "/api/v1/tags",
        json={"name": "Work", "color": "#3b82f6"},
        headers=auth_headers_a,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Work"
    assert data["color"] == "#3b82f6"
    assert data["id"]


async def test_duplicate_tag_name_case_insensitive(
    client: AsyncClient, auth_headers_a: dict
):
    await create_tag(client, auth_headers_a, "Work")

    response = await client.post(
        "/api/v1/tags", json={"name": "wORK"}, headers=auth_headers_a
    )
    assert response.status_code == 400
    assert "exists" in response.json()["detail"].lower()


async def test_duplicate_tag_name_other_user_allowed(
    client: AsyncClient, auth_headers_a: dict, auth_headers_b: dict
):
    await create_tag(client, auth_headers_a, "Work")

    response = await create_tag(client, auth_headers_b, "Work")
    assert response["name"] == "Work"


async def test_list_tags_returns_only_own_tags(
    client: AsyncClient, auth_headers_a: dict, auth_headers_b: dict
):
    await create_tag(client, auth_headers_a, "Mine")
    await create_tag(client, auth_headers_b, "Theirs")

    response = await client.get("/api/v1/tags", headers=auth_headers_a)
    assert response.status_code == 200
    names = [tag["name"] for tag in response.json()["items"]]
    assert names == ["Mine"]


async def test_update_tag_rename_and_color(client: AsyncClient, auth_headers_a: dict):
    tag = await create_tag(client, auth_headers_a, "Work", "#111111")

    response = await client.patch(
        f"/api/v1/tags/{tag['id']}",
        json={"color": "#ff0000"},
        headers=auth_headers_a,
    )
    assert response.status_code == 200
    assert response.json()["color"] == "#ff0000"

    response = await client.patch(
        f"/api/v1/tags/{tag['id']}",
        json={"name": "Deep Work"},
        headers=auth_headers_a,
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Deep Work"


async def test_rename_to_existing_name_rejected(
    client: AsyncClient, auth_headers_a: dict
):
    await create_tag(client, auth_headers_a, "Work")
    urgent = await create_tag(client, auth_headers_a, "Urgent")

    response = await client.patch(
        f"/api/v1/tags/{urgent['id']}",
        json={"name": "WORK"},
        headers=auth_headers_a,
    )
    assert response.status_code == 400


async def test_cross_user_tag_access_forbidden(
    client: AsyncClient, auth_headers_a: dict, auth_headers_b: dict
):
    tag = await create_tag(client, auth_headers_a, "Private")

    got = await client.get(f"/api/v1/tags/{tag['id']}", headers=auth_headers_b)
    assert got.status_code in (403, 404, 405)  # GET single not exposed

    patched = await client.patch(
        f"/api/v1/tags/{tag['id']}",
        json={"name": "Hijacked"},
        headers=auth_headers_b,
    )
    assert patched.status_code == 403

    deleted = await client.delete(f"/api/v1/tags/{tag['id']}", headers=auth_headers_b)
    assert deleted.status_code == 403


async def test_delete_tag_removes_relations(client: AsyncClient, auth_headers_a: dict):
    tag = await create_tag(client, auth_headers_a, "Work")
    todo = await client.post(
        "/api/v1/todos", json={"title": "Tagged todo"}, headers=auth_headers_a
    )
    assert todo.status_code == 201

    attach = await client.post(
        f"/api/v1/todos/{todo.json()['id']}/tags",
        json={"tag_id": tag["id"]},
        headers=auth_headers_a,
    )
    assert attach.status_code == 201
    assert attach.json()["tags"][0]["name"] == "Work"

    deleted = await client.delete(f"/api/v1/tags/{tag['id']}", headers=auth_headers_a)
    assert deleted.status_code == 204

    got = await client.get(f"/api/v1/todos/{todo.json()['id']}", headers=auth_headers_a)
    assert got.status_code == 200
    assert got.json()["tags"] == []
