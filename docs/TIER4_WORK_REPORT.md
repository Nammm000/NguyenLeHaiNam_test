# Tier 4 Work Report — Todo Tags, Filtering & Bulk Actions

**Branch:** `assessment/tier-4`
**Date:** 2026-09-19
**Commit range:** `0f7701a..4d0354c` (11 commits: 8 feature/test/style, 3 post-review fixes)
**Requirement source:** `README.md` — Tier 4: Optional Extension (Bonus +15 pts)

---

## 1. Scope

Tier 4 asked for a full-stack extension of the Todo app: per-user tags, todo filtering and
pagination, tag attach/detach on todos, bulk status updates, the supporting database schema
and indexes, user- and filter-scoped Redis caching with invalidation on every write path,
and a React UI (filter bar, tag chips, tag manager, bulk actions) built on TanStack Query
with react-hook-form + zod validation.

## 2. Deliverables map (requirement → implementation)

### 2.1 Database schema — complete

| Requirement | Implementation | Commit |
|---|---|---|
| `tags` (id UUID PK; user_id FK→users, NOT NULL; name VARCHAR(50) NOT NULL; color VARCHAR(20) NULL; created_at/updated_at TIMESTAMPTZ NOT NULL) | `backend/app/models/tag.py` | `0f7701a` |
| `todo_tags` (todo_id FK→todos, tag_id FK→tags, both NOT NULL, composite PK `(todo_id, tag_id)`) | `backend/app/models/todo_tag.py` | `0f7701a` |
| Case-insensitive unique tag name per user | Functional unique index `uq_tags_user_name_ci` on `(user_id, lower(name))` (model + migration) plus a service-level `func.lower()` check on create and rename → HTTP 400 `DuplicateTagNameError` | `0f7701a`, `303d0fc` |
| Indexes `tags(user_id)`, `todo_tags(tag_id)`, `todo_tags(todo_id)` | `ix_tags_user_id`, `ix_todo_tags_tag_id`, `ix_todo_tags_todo_id` in migration `c8d9e0f1a2b3` | `0f7701a` |
| Index `todos(user_id, completed, created_at)` | `ix_todos_user_completed_created_at` — created with the Tier 3C indexing migration `b7f2e8a1c9d3` (commit `0058854`) and reused by Tier 4 filtering | `0058854` |
| Deleting a tag removes its todo-tag relations | DB-level `ON DELETE CASCADE` on both FKs **and** explicit relation delete in `tag_service.delete_tag` | `0f7701a`, `303d0fc` |

Migration chain `001_initial → a0790c76a129 → b7f2e8a1c9d3 → c8d9e0f1a2b3` is linear with a
single head; model definitions match migration DDL (verified column-by-column — no drift).

### 2.2 API endpoints — complete (8/8)

All routes under `/api/v1`, mounted in `backend/app/main.py`.

| Endpoint | Handler | Notes |
|---|---|---|
| `GET /tags` | `tags.py :: list_tags` | Scoped to `current_user.id` |
| `POST /tags` | `tags.py :: create_new_tag` | 201; duplicate (case-insensitive) → 400 |
| `PATCH /tags/{tag_id}` | `tags.py :: update_existing_tag` | Ownership-gated; rename/recolor; invalidates todo cache (see §4) |
| `DELETE /tags/{tag_id}` | `tags.py :: delete_existing_tag` | 204; deletes relations; invalidates todo cache |
| `GET /todos?status=&tag_id=&keyword=&date_from=&date_to=&page=&page_size=` | `todos.py :: list_todos` | Exact README param names; `status` constrained to `completed\|active`; keyword = escaped ILIKE; tag filter via subquery; UTC date bounds; paginated `{items, total, page, size}` with tags eager-loaded (`lazy="selectin"`) |
| `POST /todos/{todo_id}/tags` | `todos.py :: attach_tag` | 201 new / 200 idempotent re-attach; both-sides ownership checks |
| `DELETE /todos/{todo_id}/tags/{tag_id}` | `todos.py :: detach_tag` | 204; 404 when not attached |
| `PATCH /todos/bulk-status` | `todos.py :: bulk_status` | Payload `{todo_ids: [uuid], completed: bool}` (1–100 ids); returns `{updated, requested}` |

Feature commits: `303d0fc` (tag CRUD), `dfb0728` (filtering, tag mapping, bulk status,
filter-scoped cache keys).

### 2.3 Backend rules — complete (7/7)

| Rule | Implementation |
|---|---|
| Users only interact with own tags/todos | 404/403 ownership gates on every by-id handler (`_get_owned_tag`; user_id checks in todos handlers); list queries scoped by `user_id`; bulk update filtered in SQL by `Todo.user_id == user_id` |
| Only own tags on own todos | Todo side (404/403) **and** tag side (404 / 403 "Not authorized to use this tag") checked on attach |
| Tag names unique per user, case-insensitive | DB functional unique index + service-level `lower()` check → 400 |
| Bulk updates in a transaction | Single atomic `UPDATE … WHERE user_id = :u AND id IN (…)` + flush, committed by the request-scoped session — partial updates impossible |
| Pagination orders `created_at DESC, id DESC` | `todo_service.get_todos` — `.order_by(Todo.created_at.desc(), Todo.id.desc())`, backed by `ix_todos_user_created_id (user_id, created_at, id)` |
| Redis cache scoped by user + all filters | `build_list_cache_key` includes user_id, page, page_size, status, tag_id, keyword, date_from, date_to; TTL 300 s |
| Cache invalidated on create / update / delete / tag mapping / bulk | Pattern delete `todos:list:{user}:{*}` via SCAN-based `delete_pattern` at all 7 write sites: todo create, update, delete; attach, detach; bulk-status; tag delete. Tag rename added post-review (§4) |

### 2.4 Frontend — complete (9/9)

| Requirement | Implementation |
|---|---|
| Filter bar: keyword, status, tag, date range, clear | `features/todos/components/TodoFilters.tsx` — debounced keyword (300 ms), status select, tag select from `useTags()`, from/to date inputs, Clear button (disabled when idle) |
| Todo item shows attached tags | `TodoItem.tsx` — colored Badge chips + per-todo attach/detach menu |
| Tag management UI: list/create/rename/delete | `TagManager.tsx` (opened from TodoPage) — list, create via `TagForm`, inline rename, delete |
| Bulk actions: select multiple → completed **or** active | Per-item + select-all-on-page checkboxes (`TodoItem`, `TodoList`); "Mark completed" / "Mark active" → `useBulkStatus` |
| TanStack Query for fetching/mutations | All server state via `useQuery`/`useMutation` (`features/todos/api/todos.ts`, `tags.ts`) |
| Query keys include all filter params | `buildTodosQueryKey` → `["todos", { page, page_size, status, tag_id, keyword, date_from, date_to }]` |
| Cache invalidated after mutations | `["todos"]` invalidated on create/update/delete todo, attach/detach, bulk status, tag delete (and tag rename post-review); `["tags"]` on tag CRUD; optimistic updates with snapshot rollback for todo update and bulk status |
| react-hook-form + zod matching backend | `TagForm`/`TodoForm` via `useForm` + `zodResolver`; zod schemas mirror backend constraints (name 1–50, color ≤ 20, title 1–200) |
| Clear user-scoped cache on logout | `queryClient.clear()` in `useLogout.onSuccess` and the `useAuth.logout` wrapper (success and error paths) |

Feature commits: `b9eb86d` (tag API hooks, schema, UI primitives), `226c126` (filter bar,
filter-scoped query keys), `9610a1c` (tag manager, tag menus, bulk actions, paginated list).

### 2.5 Tests — backend suggested tests: 7/7 covered

`backend/tests/` (SQLite + dict-backed FakeRedis; suite is self-contained — `pytest tests/ -v`).

| Suggested scenario | Test |
|---|---|
| Create tag success | `test_tags.py :: test_create_tag_success` |
| Duplicate tag casing | `test_tags.py :: test_duplicate_tag_name_case_insensitive`, `test_rename_to_existing_name_rejected` (+ other-user same name allowed) |
| Cross-user access prevention | `test_tags.py :: test_cross_user_tag_access_forbidden`; `test_todos_authorization.py` (read/update/delete, list isolation) |
| Attaching another user's tag | `test_todos_filters_bulk.py :: test_attach_other_users_tag_forbidden`, `test_attach_tag_to_other_users_todo_forbidden` |
| Filtering by tag | `test_todos_filters_bulk.py :: test_filter_by_tag` (+ keyword, status, date-range filters) |
| Bulk update ownership | `test_todos_filters_bulk.py :: test_bulk_status_updates_only_own_todos` (foreign todo untouched), unknown-id handling |
| Cache invalidation | `test_todos_cache.py` (real cache-hit served stale, user-scoped keys, create/update/delete invalidate), `test_todos_filters_bulk.py` (filter-scoped keys, attach/detach/bulk/rename invalidate) |

The FakeRedis is a dict-backed fake whose `get` returns stored values and `delete_pattern`
performs fnmatch deletion — the cache path is genuinely exercised (a test proves stale reads
on hits and empty keys after each write type). Commit: `6cd1537` (+ `f810e6c` style fix).

## 3. Post-implementation review

A requirement-by-requirement completion audit re-verified schema, endpoints, rules, frontend
and tests against the README (evidence: model/migration cross-check, all cache write-path
call sites, query-key construction, invalidation call sites). Result: all mandatory sections
complete. The audit surfaced two cache-consistency defects in the new Tier 4 code, fixed with
regression tests:

1. **Tag rename left stale cache** (backend `PATCH /tags/{tag_id}` and frontend `useUpdateTag`
   invalidated nothing / only `["tags"]`, while tag *delete* invalidated `todos:list:*` on
   both sides). Cached todo lists embed tag name/color chips → stale UI for up to 300 s.
   Fixed by mirroring the delete handler's pattern delete (`fix(backend): invalidate todo
   list cache after tag rename` — `a8cb188`; `fix(frontend): invalidate todos cache after
   tag rename` — `4d0354c`), with `test_tag_rename_invalidates_cache`.
2. **`keyword="all"` cache-key collision** — the no-keyword placeholder was the literal
   `'all'`, so filtering by keyword "all" shared a cache entry with the unfiltered list.
   Fixed by an empty-string sentinel (safe: `keyword` has `min_length=1`) in
   `fix(backend): disambiguate empty keyword in todo list cache key` — `467a2e7`, with
   `test_cache_key_distinguishes_literal_all_keyword`.

## 4. Verification evidence

| Check | Command | Result |
|---|---|---|
| Backend suite | `cd backend && pytest tests/ -v` | **46 passed** (incl. the 2 post-review regression tests) |
| Backend style | `black .` / `flake8 .` | clean |
| Frontend typecheck + build | `npm run build` (`tsc -b && vite build`) | pass |
| Frontend lint | `npm run lint` | clean |
| Migrations | `alembic upgrade head` (linear chain, single head) | verified in schema audit |

## 5. Known limitations (deliberate, non-blocking)

- **Frontend unit tests not implemented** — the README lists them as *suggested*; `frontend/`
  has no test runner today. The suggested cases (tag form validation, filter query-key
  behavior, bulk success/error handling, logout cache clear) remain open follow-ups; hooks
  already expose testable seams (e.g. exported `buildTodosQueryKey`).
- **E2E coverage** — the Playwright suite (Tier 2B: user journey, cross-user isolation) does
  not yet include Tier 4 scenarios; the UI ships ready-made `data-testid`s
  (`todo-filters`, `tag-manager-list`, `bulk-complete`, …) for future specs.
- **Minor accepted behaviors:** duplicate-tag creation under a race returns 500 (the DB
  unique index still blocks the insert); `date_from`/`date_to` filter by UTC calendar day;
  bulk selection is page-scoped and clears on page/filter change; no tag seed data (not
  required by the README).

## 6. Commit list (Tier 4 range)

| Commit | Type | Subject |
|---|---|---|
| `0f7701a` | feat(db) | add tags and todo_tags models and migration |
| `303d0fc` | feat(tags) | tag CRUD endpoints |
| `dfb0728` | feat(todos) | add filtering, tag mapping, bulk status and filter-scoped cache keys |
| `6cd1537` | test(backend) | cover tags, filters, bulk ownership and cache invalidation |
| `f810e6c` | style(backend) | wrap long line in security module per black |
| `b9eb86d` | feat(frontend) | tag api hooks, schema and ui primitives |
| `226c126` | feat(frontend) | todo filter bar with filter-scoped query keys |
| `9610a1c` | feat(frontend) | tag manager, tag menus, bulk actions and paginated list |
| `a8cb188` | fix(backend) | invalidate todo list cache after tag rename |
| `467a2e7` | fix(backend) | disambiguate empty keyword in todo list cache key |
| `4d0354c` | fix(frontend) | invalidate todos cache after tag rename |
