# Manual Test Plan: Authentication, Todo CRUD, Authorization, Caching & Tier 4 Features

> Structure follows `templates/TEST_PLAN_TEMPLATE.md`. Status values reflect the
> latest verified run (automated coverage noted where applicable).

## 1. Scope & Objective

- **Objective**: Verify critical business paths of the Todo application and
  regression-test the Tier 1 fixes (JWT expiry, token-type enforcement, todo
  ownership, partial-update semantics, cache scoping/invalidation, list
  ordering), plus the Tier 4 feature set (tags, filtering, bulk actions).
- **Test scope**: Authentication, Authorization (IDOR boundaries), Todo CRUD
  business logic, Redis caching, Tag management, Todo filtering, Bulk status
  updates.
- **Out of scope**: Refresh-token rotation/revocation (known limitation, see
  §4), performance benchmarks (see `docs/DATABASE_BENCHMARK.md`), infrastructure
  provisioning.

## 2. Test Environment & Prerequisites

- Backend Base URL: `http://localhost:8000` (API docs at `/docs`)
- Frontend Base URL: `http://localhost:3000` (Docker) or `:5173` (dev server)
- Stack up: `docker compose up --build` (Postgres + Redis + backend + frontend)
- Test accounts (register once via UI or `POST /api/v1/auth/register`):
  - Account 1 (User A): `user_a@test.com` / `Password@123`
  - Account 2 (User B): `user_b@test.com` / `Password@123`
- Tools: browser (two profiles/incognito windows for two-user scenarios),
  `curl` or `/docs` playground, a JWT debugger (e.g. jwt.io) for token cases,
  `redis-cli` (optional, for cache inspection).

## 3. Test Cases Matrix

| TC ID | Module / Feature | Test Scenario | Preconditions | Test Steps | Expected Result | Priority / Severity | Status (Pass/Fail) |
|---|---|---|---|---|---|---|---|
| TC-01 | Auth | Login with correct credentials | User A registered | 1. Enter correct email/password<br>2. Click Sign In | Access + refresh tokens returned; redirected to Todo page; header shows user email | High / Blocker | Pass |
| TC-02 | Auth | Login with wrong password | User A registered | 1. Enter correct email, wrong password<br>2. Click Sign In | Generic error, HTTP 401, no page reload, error toast visible | Medium / Security | Pass |
| TC-03 | Auth | Login with unknown email (user enumeration) | Email not registered | 1. Enter unknown email + any password<br>2. Click Sign In | Ideally generic 401 "Invalid email or password". **Actual: HTTP 404 "User with this email not found"** — distinct from wrong-password 401, enabling enumeration | Medium / Security | **Fail — known issue (A5, unfixed by design, see §4)** |
| TC-04 | Auth / Token | Expired access token rejected | Obtain token, wait past expiry (or mint expired token via `/docs` scripts) | 1. Call `GET /auth/me` with expired Bearer token | HTTP 401; SPA redirects to login | High / Critical | Pass (automated: `test_auth_security.py`) |
| TC-05 | Auth / Token | Refresh token cannot be used as access token | User has refresh token | 1. Call `GET /auth/me` with refresh token as Bearer | HTTP 401 "Invalid token type" | High / Critical | Pass (automated) |
| TC-06 | Auth / Token | Tampered token rejected | Any valid token | 1. Modify signature chars<br>2. Call protected endpoint | HTTP 401 | High / Critical | Pass (automated) |
| TC-07 | Authorization | User A cannot read User B's todo | A & B logged in; B owns todo X | 1. As A, `GET /todos/X` | HTTP 403 Forbidden | High / Critical | Pass (automated: `test_todos_authorization.py`) |
| TC-08 | Authorization | User A cannot update/delete User B's todo | B owns todo X | 1. As A, `PUT /todos/X`<br>2. As A, `DELETE /todos/X` | HTTP 403 both; B's data unchanged | High / Critical | Pass (automated) |
| TC-09 | Authorization | List shows only own todos | A & B each own todos | 1. As B, `GET /todos`<br>2. Check UI | Only B's items; count matches B's total | High / Critical | Pass (automated + e2e `cross-user-isolation.spec.ts`) |
| TC-10 | Todo Logic | Toggle completed true → false persists | Todo X is completed | 1. `PUT /todos/X {"completed": false}`<br>2. `GET /todos/X`<br>3. F5 the UI | `completed = false` after reload; no line-through | Medium / Major | Pass (automated: `test_todos_updates.py`) |
| TC-11 | Todo Logic | Title-only update preserves description | Todo X has description | 1. `PUT /todos/X {"title": "new"}` | 200; description unchanged (no wipe to null) | Medium / Major | Pass (automated) |
| TC-12 | Cache | Cache is user-scoped | A & B have different todos | 1. `GET /todos` as A<br>2. Same as B | B never receives A's cached payload | High / Critical | Pass (automated: `test_todos_cache.py`) |
| TC-13 | Cache | Update invalidates stale cache | List already cached (call GET once) | 1. Rename todo<br>2. `GET /todos` again (or F5) | New title returned; no stale copy within TTL window | Medium / Major | Pass (automated for create/update/delete) |
| TC-14 | Cache | Create/delete invalidate cache | List cached | 1. Create todo → GET<br>2. Delete todo → GET | New item appears; deleted item disappears immediately | Medium / Major | Pass (automated) |
| TC-15 | Pagination | Stable ordering across pages | User has > 20 todos | 1. `GET /todos?page=1`<br>2. `GET /todos?page=2` | Ordered `created_at DESC, id DESC`; no duplicates/omissions across pages | Medium / Major | Pass |
| TC-16 | Tags | Create tag | User A logged in | 1. `POST /tags {"name": "Work"}` | 201; tag appears in UI tag manager | Medium / Major | Pass |
| TC-17 | Tags | Duplicate tag name (case-insensitive) | A has tag "Work" | 1. `POST /tags {"name": "work"}` | HTTP 400; single tag remains | Medium / Major | Pass (automated: `test_tags.py`) |
| TC-18 | Tags | Cross-user tag access prevented | B owns tag T | 1. As A, `PATCH /tags/T` / `DELETE /tags/T` | HTTP 403/404; B's tag unchanged | High / Critical | Pass (automated) |
| TC-19 | Tags | Attaching another user's tag prevented | B owns tag T; A owns todo X | 1. As A, `POST /todos/X/tags {"tag_id": T}` | HTTP 403 | High / Critical | Pass (automated) |
| TC-20 | Filtering | Filter by tag / keyword / status / date | User has tagged todos | 1. `GET /todos?tag_id=…`<br>2. `?keyword=…` / `?status=completed` / `?date_from=…` | Only matching items; total reflects filter; empty filter returns all | Medium / Major | Pass (automated: `test_todos_filters_bulk.py`) |
| TC-21 | Bulk | Bulk status update ownership | A owns 1 of the 2 ids submitted (other belongs to B) | 1. `PATCH /todos/bulk-status {"todo_ids": [a1, b1], "completed": true}` | Only A's todo updated (`updated=1, requested=2`); B's todo unchanged; response 200 | High / Critical | Pass (automated) |
| TC-22 | Bulk / Cache | Bulk update invalidates cache | List cached | 1. Bulk-complete several todos<br>2. F5 | UI reflects new statuses immediately | Medium / Major | Pass (automated) |
| TC-23 | Logout | Logout clears cached state | User A logged in with todos visible | 1. Logout<br>2. Login as B on same tab | B sees only B's todos/email; none of A's data flashes | High / Critical | Pass (automated vitest + e2e user journey) |

## 4. Defect Tracking & Known Limitations

- **A5 — Login user enumeration (TC-03)**: unknown email returns 404
  "User with this email not found" while wrong password returns 401,
  allowing account enumeration. Reported in the Tier 1 review; intentionally
  left unfixed (Tier 1 scope closed). Recommended fix: route login through
  `authenticate_user()` and return a generic 401 for both cases.
- **A7 — Refresh-token lifecycle**: `/auth/refresh` does not rotate or
  revoke refresh tokens (no `jti` denylist) and logout revokes nothing
  server-side. Reported; out of scope for this release.
- **A8 — JWT secret default**: the development secret ships in the committed
  `.env` (intentional per assessment rules); production must override via
  environment (enforced by the prod compose file).
- **SPA refresh flow**: the frontend stores the refresh token but never calls
  `/auth/refresh`; sessions end at access-token expiry (30 min) with a
  redirect to login. Missing feature, not a regression.
- Automated suites: backend `pytest tests/ -v`; e2e `cd e2e && npx playwright
  test` (see `e2e/README.md`); frontend unit `cd frontend && npm run test`.
