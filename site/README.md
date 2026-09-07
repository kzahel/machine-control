# Machine Control website

This Astro application serves [machinecontrol.dev](https://machinecontrol.dev)
from a Cloudflare Worker. It includes the project landing page, field notes,
RSS, and a small project-update list backed by Cloudflare D1 and protected by
Cloudflare Turnstile.

## Local development

Install dependencies and create the local database once:

```sh
pnpm install
pnpm wrangler d1 migrations apply machine-control-site --local
```

Copy `.dev.vars.example` to `.dev.vars` to use Cloudflare's public Turnstile
test secret, then run:

```sh
pnpm dev
```

Build and type-check the Cloudflare boundary with:

```sh
pnpm generate-types
pnpm build
```

## Automatic production deployment

GitHub Actions deploys the site after a push to `main` changes `site/` or the
deployment workflow. The `production` GitHub environment must define these
secrets:

- `CLOUDFLARE_API_TOKEN`: a narrowly scoped **Edit Cloudflare Workers** token
  for the account and the `machinecontrol.dev` zone;
- `CLOUDFLARE_ACCOUNT_ID`: the owning Cloudflare account ID; and
- `CLOUDFLARE_D1_DATABASE_ID`: the existing `machine-control-site` database ID.

The workflow injects the database ID only into the ignored generated build
configuration. Never add any of these values to this public repository. The
existing `TURNSTILE_SECRET_KEY` remains a Worker secret in Cloudflare and is
required at deploy time; it is not copied into GitHub.

The workflow can also be rerun manually from GitHub Actions. D1 migrations are
not applied automatically: apply and verify a migration deliberately before
merging code that depends on it.

## Production resources

The Worker has a D1 binding named `SIGNUPS`, a public `TURNSTILE_SITE_KEY`
variable, and an encrypted `TURNSTILE_SECRET_KEY` secret. Apply tracked
migrations before deploying a schema change:

```sh
pnpm wrangler d1 migrations apply machine-control-site --remote
pnpm deploy
```

Never commit the Turnstile secret or a production signup export. To withdraw
an address while retaining consent history:

```sql
UPDATE newsletter_subscribers
SET status = 'withdrawn', withdrawn_at = CURRENT_TIMESTAMP,
    updated_at = CURRENT_TIMESTAMP
WHERE email = ?;
```

Delete the matching row instead when a subscriber asks for full removal.
