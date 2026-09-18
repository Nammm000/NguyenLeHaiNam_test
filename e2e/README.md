# E2E Tests (Playwright)

Browser end-to-end tests for the Todo app: a full user journey and cross-user
data isolation.

## Prerequisites (once)

Postgres and Redis must be reachable on `localhost` — the repository's compose
stack provides them:

```bash
docker compose up -d postgres redis
```

Frontend dependencies must be installed (the Vite dev server is started
automatically by Playwright):

```bash
cd ../frontend && npm install
```

Install the e2e dependencies and the Chromium browser:

```bash
npm install
npx playwright install chromium
```

## Running

```bash
npx playwright test             # headless (default)
npm run test:headed             # headed
```

## How it works

- The backend webServer command first drops and recreates the dedicated
  `todo_e2e` database (`create-e2e-db.mjs`), then applies Alembic migrations
  to it and boots the API.
- The backend runs locally via `uvicorn` on `:8000` with
  `DATABASE_URL=…todo_e2e` and `REDIS_URL=redis://localhost:6379/1` (dev data
  in db 0 is never touched).
- The frontend runs via `npm run dev` on `:5173`.
- Tests register fresh users with unique emails, so runs never depend on
  seeded data.
- If another service already occupies port 5432, point the suite at an
  alternate port with `E2E_PG_PORT` (e.g. `E2E_PG_PORT=5434 npx playwright test`).
