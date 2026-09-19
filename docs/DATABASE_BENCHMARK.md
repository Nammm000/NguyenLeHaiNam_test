# Database Indexing Benchmark — Before vs After

Tier 3C deliverable. All numbers from a real run on 2026-09-19 against
PostgreSQL 16 with **10,000 users / 1,000,000 todos** seeded via
`SEED_USERS=10000 SEED_TODOS=1000000 python -m app.db.seed` (seed runtime:
~31 s). Plans captured with `EXPLAIN (ANALYZE, BUFFERS)`; each query was run
twice and the second (warm-cache) run recorded. The benchmark user is the
heaviest user in the dataset (**138 todos**; per-user distribution:
avg 100, min 67, max 138 — the seed distributes todos uniformly at random).

## Indexes added (migration `b7f2e8a1c9d3`)

| Index | Definition | Purpose |
|---|---|---|
| `uq_users_email` | `UNIQUE (users.email)` | Closes the duplicate-email gap (concurrent registrations → `MultipleResultsFound` → HTTP 500 on login); also serves email lookups at login/register. |
| `ix_todos_user_completed_created_at` | `(user_id, completed, created_at)` on `todos` | Composite index for user-scoped, **status-filtered** list queries (`GET /todos?status=…`). |
| `ix_todos_user_created_id` | `(user_id, created_at, id)` on `todos` | Serves the default list `ORDER BY created_at DESC, id DESC` via a **backward index scan with no sort node**; also serves `COUNT(*)` as an index-only scan. |

## Benchmark queries

Core API query shapes (verbatim SQL actually measured):

- **Q1 — page-1 list**: `SELECT * FROM todos WHERE user_id = $1 ORDER BY created_at DESC, id DESC LIMIT 20 OFFSET 0`
- **Q2 — deep page**: same with `LIMIT 20 OFFSET 120`
- **Q3 — count for pagination**: `SELECT count(*) FROM todos WHERE user_id = $1`
- **Q4 — status-filtered list**: `SELECT * FROM todos WHERE user_id = $1 AND completed = false ORDER BY created_at DESC, id DESC LIMIT 20`

## Results

| Query | Before (plan) | Before time | After (plan) | After time | Speedup |
|---|---|---|---|---|---|
| Q1 page-1 list | Parallel Seq Scan + Gather Merge Sort (full 1M-row scan, ~27k buffers) | **31.59 ms** | Index Scan Backward on `ix_todos_user_created_id` (23 buffers, **no sort node**) | **0.16 ms** | ~195× |
| Q2 deep page | Parallel Seq Scan + Sort | **32.98 ms** | Bitmap Index Scan + sort of the user's 138 rows only | **0.77 ms** | ~43× |
| Q3 count | Parallel Seq Scan + Partial Aggregate | **31.67 ms** | Index **Only** Scan (5 buffers, 0 heap fetches) | **0.08 ms** | ~396× |
| Q4 status filter | Parallel Seq Scan + Sort | **34.79 ms** | Index Scan Backward on `ix_todos_user_completed_created_at` + incremental sort | **0.18 ms** | ~193× |

Every "before" plan scanned all ~1,000,000 rows (filter removed ~333k rows per
worker) and sorted the results; every "after" plan touches only the target
user's rows (≤ 138).

Representative plans (warm runs, trimmed):

```text
-- Q1 BEFORE
Limit (actual time=29.176..31.541 rows=20)
  -> Gather Merge (Sort Key: created_at DESC, id DESC)
       -> Sort (Sort Method: top-N heapsort)
            -> Parallel Seq Scan on todos
                 Filter: (user_id = '…')  Rows Removed by Filter: 333287
                 Buffers: shared hit=11712 read=15606
Planning Time: 0.447 ms   Execution Time: 31.593 ms

-- Q1 AFTER
Limit (actual time=0.031..0.136 rows=20)
  -> Index Scan Backward using ix_todos_user_created_id on todos
       Index Cond: (user_id = '…')
       Buffers: shared hit=23
Planning Time: 0.684 ms   Execution Time: 0.162 ms

-- Q3 AFTER
Aggregate (actual time=0.043..0.043 rows=1)
  -> Index Only Scan using ix_todos_user_created_id on todos
       Index Cond: (user_id = '…')  Heap Fetches: 0
Execution Time: 0.080 ms

-- Q4 AFTER
Limit (actual time=0.148..0.151 rows=20)
  -> Incremental Sort (Sort Key: created_at DESC, id DESC; Presorted Key: created_at)
       -> Index Scan Backward using ix_todos_user_completed_created_at on todos
            Index Cond: ((user_id = '…') AND (completed = false))
Execution Time: 0.180 ms
```

## Index trade-offs

- **Write latency**: each INSERT/UPDATE on `todos` now maintains two
  additional btree indexes (~56 MB + 47 MB). `completed` flips and `updated_at`
  bumps are the hot write path; the composite indexes include `completed` and
  `created_at` but **not** `updated_at`, so a pure status flip touches
  `ix_todos_user_completed_created_at` plus the heap, while `ix_todos_user_created_id`
  (user_id/created_at/id only) is untouched by updates. Measured seed rate with
  indexes present was still thousands of rows/batch (no observable penalty at
  application insert batch sizes).
- **Storage overhead**: todos table 212 MB heap + 38 MB PK → 354 MB total with
  the two new indexes (**+103 MB, ~29% growth**); `uq_users_email` adds
  only 440 kB on 10k users. Cheap relative to the ~200× read improvement on
  every list request.
- **Why two indexes?** `(user_id, completed, created_at)` cannot serve the
  default `ORDER BY created_at DESC, id DESC` without an intermediate sort,
  because `completed` sits between `user_id` and `created_at`. Q1's zero-sort
  plan requires `(user_id, created_at, id)` scanned backward. If write overhead
  ever matters more than deep-page latency, `ix_todos_user_created_id` is the
  one to drop first — the composite index alone still gives correct (sorted
  post-hoc) results.
- **Migration safety on large production tables**: the migration builds all
  indexes with `CREATE INDEX CONCURRENTLY` (via Alembic's
  `autocommit_block()`), so reads and writes continue during the build and no
  ACCESS EXCLUSIVE lock is taken. Caveats: it cannot run inside a transaction;
  if interrupted it leaves an `INVALID` index that must be dropped and retried
  (check `pg_index.indisvalid`). Before creating the **unique** email index on
  a production table with pre-existing data, dedupe rows first — the build
  fails on any duplicate (our seed data is unique by construction, verified).
  Rollback (`alembic downgrade -1`) drops the indexes CONCURRENTLY as well;
  verified: downgrade → 0 indexes, re-upgrade → 2 indexes recreated.
- **Seed-data caveat (honesty note)**: the seed script stamps `created_at`
  per 5,000-row batch, so ~1M rows share ~200 distinct timestamps. Ordering
  therefore degenerates to `id DESC` across large tie groups. The index still
  removes the sort node entirely and remains correct under skew (a user with
  thousands of rows), which is the property that matters; wall-clock gains
  here come chiefly from eliminating the 1M-row scan, not from the sort.

## Reproduction

```bash
docker compose down -v && docker compose up -d postgres backend
docker compose exec backend alembic upgrade a0790c76a129   # pre-index schema
docker compose exec -e SEED_USERS=10000 -e SEED_TODOS=1000000 backend python -m app.db.seed
docker compose exec postgres psql -U fabbi -d postgres -c "ANALYZE todos;"
docker compose exec postgres psql -U fabbi -d postgres   # run Q1–Q4 EXPLAIN (ANALYZE, BUFFERS)
docker compose exec backend alembic upgrade head          # add indexes
docker compose exec postgres psql -U fabbi -d postgres -c "ANALYZE todos;"   # re-run Q1–Q4
```

(On a host where port 5432 is occupied, run the stack on an alternate port or
point `DATABASE_URL` at any PostgreSQL 16 instance.)
