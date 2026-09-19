# Technical Specification: Todo Sharing with Viewer / Editor Permissions

> Structure follows `templates/SPEC_TEMPLATE.md`. Specification only — no
> implementation in this release.

## 1. Overview & Objective

- **Feature Summary**: Todo owners can share an individual todo with another
  registered user, granting either **read-only (viewer)** or **edit
  (editor)** permission, and can revoke that access at any time. Shared todos
  appear in the grantee's "shared with me" list with a clear visual
  distinction from their own todos.
- **Problem Statement**: Today a todo is strictly private — there is no way to
  collaborate. Users must copy content out of the app (screenshots, chat
  messages) to let a colleague review or update an item, which breaks audit
  trails and loses single-source-of-truth editing.
- **Target Audience / Roles**:
  - **Owner** — the user who created the todo; full control (read, edit,
    delete, share, revoke).
  - **Viewer** — a user the todo was shared with; can read the todo, cannot
    modify it.
  - **Editor** — a user the todo was shared with; can update todo content
    (title, description, completed) but cannot delete the todo or manage its
    shares.
  - No admin role in this release.

## 2. User Stories & Acceptance Criteria

### User Story 1: Share a todo as viewer
- **As a** todo owner
- **I want to** share one of my todos with another registered user with
  read-only permission
- **So that** they can follow my progress without being able to change
  anything
- **Acceptance Criteria**:
  - [ ] Owner can grant access by supplying the grantee's email and
        `permission: "viewer"`; the API returns the created share with 201.
  - [ ] Grantee sees the todo in `GET /todos/shared-with-me` with
        `permission: "viewer"` and the owner's email.
  - [ ] Grantee's `GET /todos/{id}` succeeds; `PUT`/`DELETE` return 403.
  - [ ] The todo never appears in the grantee's own `GET /todos` list
        (ownership list stays private-first).

### User Story 2: Share a todo as editor
- **As a** todo owner
- **I want to** grant edit permission to a collaborator
- **So that** they can keep the todo up to date on my behalf
- **Acceptance Criteria**:
  - [ ] Owner can grant `permission: "editor"`; grantee can `PUT` title,
        description, and completed flag.
  - [ ] Editor cannot delete the todo (403) and cannot create, modify, or
        revoke shares (403).
  - [ ] Editor's updates are visible to the owner immediately (cache
        invalidation, see §7).
  - [ ] `updated_by`-style audit fields: the todo's `updated_at` reflects the
        editor's change (a `last_modified_by` column is a nice-to-have;
        minimum viable is `updated_at`).

### User Story 3: Revoke access at any time
- **As a** todo owner
- **I want to** revoke a user's access immediately
- **So that** former collaborators lose all access without delay
- **Acceptance Criteria**:
  - [ ] `DELETE /todos/{todo_id}/shares/{share_id}` returns 204; subsequent
        grantee reads return 404 (todo treated as non-existent, not 403, to
        avoid existence disclosure).
  - [ ] Revocation invalidates the grantee's cached shared-list entries
        immediately (see §7).
  - [ ] Revoking during an in-flight edit: the edit either commits (if the
        auth check passed before revocation) or is rejected 403/404 — either
        is acceptable; the very next request must fail.

### User Story 4: See todos shared with me
- **As a** grantee (viewer or editor)
- **I want to** list all todos shared with me and my permission on each
- **So that** I can act on them (read or edit) without hunting for links
- **Acceptance Criteria**:
  - [ ] `GET /todos/shared-with-me` returns paginated todos with embedded
        `permission` and `owner_email`.
  - [ ] List is ordered `created_at DESC, id DESC` (consistent with the
        owned-todos list).

## 3. Scope

- **In-Scope** (this release):
  - Sharing a **single todo** with registered users (identified by email).
  - Two permission levels: `viewer`, `editor`.
  - Listing a todo's shares (owner only) and revoking any share (owner only).
  - "Shared with me" listing for grantees.
  - Cache invalidation for owner lists and grantee shared-lists.
- **Out-of-Scope** (deliberately excluded to keep the release lean):
  - Sharing an entire list/account.
  - Invites to non-registered users (email magic links) — grantee must exist.
  - Editor re-sharing (no transitive sharing).
  - Ownership transfer.
  - Notifications (email/in-app) on share/revoke.
  - Share-level rate limits or per-share activity audit log.
  - Bulk share operations.

## 4. Database Design

- **New table `todo_shares`**:

  | Column | Type | Constraints |
  |---|---|---|
  | `id` | `UUID` | PK, default `gen_random_uuid()` |
  | `todo_id` | `UUID` | `NOT NULL`, FK → `todos(id) ON DELETE CASCADE` |
  | `grantee_user_id` | `UUID` | `NOT NULL`, FK → `users(id) ON DELETE CASCADE` |
  | `permission` | `VARCHAR(10)` | `NOT NULL`, `CHECK (permission IN ('viewer','editor'))` |
  | `created_by` | `UUID` | `NOT NULL`, FK → `users(id)` (the owner at grant time) |
  | `created_at` | `TIMESTAMPTZ` | `NOT NULL`, default `now()` |
  | `updated_at` | `TIMESTAMPTZ` | `NOT NULL`, default `now()`, on update |

- **Altered tables**: none. `todos` and `users` are untouched; sharing is
  purely associative.
- **Constraints & indexes**:
  - `UNIQUE (todo_id, grantee_user_id)` — prevents duplicate invites at the
    DB level (race-safe; the API surfaces `IntegrityError` as 409).
  - `INDEX ix_todo_shares_todo_id ON todo_shares(todo_id)` — serves "list a
    todo's shares" and the join when loading a todo with its shares.
  - `INDEX ix_todo_shares_grantee_user_id ON todo_shares(grantee_user_id)` —
    serves "shared with me".
  - Both FKs `ON DELETE CASCADE`: deleting a todo or a user removes dependent
    shares automatically; no orphan cleanup jobs.
  - No index on `permission` (low cardinality; never queried alone).

## 5. API Contracts & Endpoints

All endpoints require a valid access token (`Authorization: Bearer …`).

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| POST | `/api/v1/todos/{todo_id}/shares` | Grant access (owner only) | Yes |
| GET | `/api/v1/todos/{todo_id}/shares` | List shares of a todo (owner only) | Yes |
| PATCH | `/api/v1/todos/{todo_id}/shares/{share_id}` | Change permission (owner only) | Yes |
| DELETE | `/api/v1/todos/{todo_id}/shares/{share_id}` | Revoke access (owner only) | Yes |
| GET | `/api/v1/todos/shared-with-me` | Todos shared with the caller, paginated | Yes |

- **Request bodies (Pydantic v2)**:

```json
// POST /todos/{todo_id}/shares
{
  "grantee_email": "colleague@test.com",   // required, valid email
  "permission": "viewer"                   // "viewer" | "editor", required
}

// PATCH /todos/{todo_id}/shares/{share_id}
{
  "permission": "editor"                   // required, "viewer" | "editor"
}
```

- **Success responses**:
  - `POST` → `201` with `TodoShareResponse`:
    `{"id", "todo_id", "grantee_user_id", "grantee_email", "permission", "created_by", "created_at", "updated_at"}`
  - `GET …/shares` → `200` with `{"items": [TodoShareResponse], "total"}`
  - `PATCH` → `200` with updated `TodoShareResponse`
  - `DELETE` → `204 No Content`
  - `GET /todos/shared-with-me` → `200`
    `{"items": [TodoResponse + {"permission", "owner_email"}], "total", "page", "size"}`
- **Error payloads** (FastAPI default envelope `{"detail": "…"}`):

  | Code | When |
  |---|---|
  | `400` | Self-sharing (`grantee_email` == owner's email); permission value invalid (also caught as 422 by Pydantic) |
  | `401` | Missing/invalid/expired token, or refresh token presented as access |
  | `403` | Caller is not the owner (share management, editor trying to manage shares or delete the todo, viewer trying to update) |
  | `404` | Todo or share id not found **or not visible to caller** (grantees see 404 for revoked todos to avoid existence disclosure) |
  | `409` | Duplicate invite — an active share `(todo_id, grantee_user_id)` already exists |
  | `422` | Malformed body / validation failure |

## 6. Business Logic & Security Considerations

- **Authorization & permission matrix**:

  | Action | Owner | Editor | Viewer | Other user |
  |---|---|---|---|---|
  | Read todo | ✅ | ✅ | ✅ | ❌ 404 |
  | Update todo | ✅ | ✅ | ❌ 403 | ❌ 404 |
  | Delete todo | ✅ | ❌ 403 | ❌ 403 | ❌ 404 |
  | List shares | ✅ | ❌ 403 | ❌ 403 | ❌ 404 |
  | Grant / change / revoke share | ✅ | ❌ 403 | ❌ 403 | ❌ 404 |

- **Re-share handling**: only the owner may manage shares. An editor's
  `POST/PATCH/DELETE` on `/shares` returns 403 — sharing is never transitive
  and permission cannot be escalated by a grantee.
- **Edge cases & race conditions**:
  - **Self-sharing**: rejected 400 ("Cannot share with yourself") before any
    insert.
  - **Duplicate invites**: API checks first for a friendly 409, but the DB
    `UNIQUE (todo_id, grantee_user_id)` is the authoritative guard under
    concurrency; `IntegrityError` maps to 409. Grant → revoke → re-grant is
    allowed (the revoked row is gone, so no conflict).
  - **Concurrent updates (owner + editor editing simultaneously)**: last
    write wins per field, consistent with the existing `exclude_unset`
    partial-update semantics; `updated_at` reflects the last committed write.
    No field-level merge or optimistic locking in this release (documented
    trade-off).
  - **Revoke during an in-flight edit**: authorization is evaluated per
    request. If the auth check passed before revocation committed, the edit
    lands; any subsequent request 403/404s. This is the standard
    sessionless-JWT behavior and is acceptable.
  - **Grantee deleted their account**: `ON DELETE CASCADE` removes the share
    automatically; the todo itself is untouched.
  - **Owner deletes the todo**: cascade removes shares; grantees' next read
    returns 404 and their cached shared-lists are invalidated (todo deletion
    already invalidates owner cache — §7 extends this).
  - **Grantee already has max shares**: not limited in this release; noted as
    a future abuse-guard.

## 7. Caching & Invalidation Strategy

- **Key structure** (extends the existing user-scoped convention
  `todos:list:{user_id}:…`):
  - Owner list cache: unchanged — `todos:list:{owner_id}:{page}:{size}…`.
  - Shared-with-me cache (new): `todos:shared:{grantee_id}:{page}:{size}`,
    TTL 300 s (same `CACHE_TTL` as todo lists).
- **Invalidation triggers** (all via the existing `delete_pattern` helper):
  - **Grant / permission change / revoke** →
    `delete_pattern(f"todos:shared:{grantee_id}:*")` (immediate: the grantee's
    next read must already reflect the change — revocation effectiveness is a
    security property, not a freshness nicety) **and**
    `delete_pattern(f"todos:list:{owner_id}:*")` (owner's share-list views).
  - **Editor updates the todo** → invalidate the owner's list keys
    (`todos:list:{owner_id}:*`) and every grantee's shared keys for that todo.
    Since grantees are enumerable from `todo_shares` in the same transaction,
    fan-out per grantee is bounded and cheap.
  - **Owner updates / deletes the todo** → existing owner invalidation plus
    the grantee fan-out above.
- **Rationale**: per-user key prefixes + pattern invalidation keeps the
  existing `SCAN`-based `delete_pattern` sufficient — no cache versioning
  machinery is required at this scale.
