import { defineConfig } from "@playwright/test";

// Override when another service already occupies the default Postgres port
// (the compose stack publishes 5432).
const pgPort = process.env.E2E_PG_PORT ?? "5432";

const E2E_DATABASE_URL = `postgresql+asyncpg://fabbi:fabbi_secret@localhost:${pgPort}/todo_e2e`;

export default defineConfig({
  testDir: "./tests",
  timeout: 30_000,
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"]],
  use: {
    baseURL: "http://localhost:5173",
    trace: "on-first-retry",
  },
  webServer: [
    {
      // Recreate the e2e database, migrate it, then boot the API on it.
      command:
        "node create-e2e-db.mjs && cd ../backend && " +
        "./venv/bin/alembic upgrade head && " +
        "./venv/bin/uvicorn app.main:app --port 8000",
      url: "http://localhost:8000/health",
      timeout: 120_000,
      // Never reuse: the command above drops and recreates the e2e database,
      // which would break a long-running server's connection pool.
      reuseExistingServer: false,
      env: {
        DATABASE_URL: E2E_DATABASE_URL,
        REDIS_URL: "redis://localhost:6379/1",
      },
    },
    {
      command: "cd ../frontend && npm run dev",
      url: "http://localhost:5173",
      timeout: 60_000,
      reuseExistingServer: !process.env.CI,
    },
  ],
});
