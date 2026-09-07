import { readFile, writeFile } from "node:fs/promises";

const databaseId = process.env.CLOUDFLARE_D1_DATABASE_ID ?? "";
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

if (!uuid.test(databaseId)) {
  throw new Error("CLOUDFLARE_D1_DATABASE_ID must be one UUID");
}

const configUrl = new URL("../dist/server/wrangler.json", import.meta.url);
const config = JSON.parse(await readFile(configUrl, "utf8"));
const databases = config.d1_databases;

if (!Array.isArray(databases)) {
  throw new Error("generated Wrangler config has no D1 bindings");
}

const matching = databases.filter((database) => database?.binding === "SIGNUPS");
if (matching.length !== 1) {
  throw new Error("generated Wrangler config must contain one SIGNUPS binding");
}

matching[0].database_name = "machine-control-site";
matching[0].database_id = databaseId;

await writeFile(configUrl, `${JSON.stringify(config)}\n`, { mode: 0o600 });
