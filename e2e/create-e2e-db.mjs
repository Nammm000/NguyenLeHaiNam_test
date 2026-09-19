import { Client } from "pg";

const port = process.env.E2E_PG_PORT ?? "5432";

const client = new Client({
  connectionString: `postgresql://fabbi:fabbi_secret@localhost:${port}/postgres`,
});
await client.connect();
await client.query("DROP DATABASE IF EXISTS todo_e2e WITH (FORCE)");
await client.query("CREATE DATABASE todo_e2e");
await client.end();
console.log(`recreated database todo_e2e on localhost:${port}`);
