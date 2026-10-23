# Runbook

What to do when something is wrong with the live service. The service is one container function on
Vercel Hobby with Neon Postgres behind it, and a static site on GitHub Pages in front of it. Nothing
in it needs a card, and nothing in it pages anyone.

## Is it up

```
deploy/probe.ps1     # /health: version, protocol revision, database, the provider the router picks
deploy/verify.ps1    # a separate MCP client: discovery, tools/list, a run_sql and its readback
```

Both read the URL from deploy/live-url.txt. A first request after an idle period can take several
seconds while the function starts; the probe tries twice for that reason, and so does the site.

## The desk says recorded session

The site could not reach /health twice in a row. Check, in order:

1. The probe. If it fails too, the function is down or the URL changed; see the next section.
2. The browser console on the desk. A CORS error means the site's origin is not in the API's allowed
   origins (packages/api app.py) or READBACK_PUBLIC_HOSTS on Vercel does not include the host.
3. The Pages build. NEXT_PUBLIC_READBACK_API comes from the READBACK_API_URL repository variable;
   empty means the default address in web/next.config.ts.

The recorded session is a feature, not an outage page: every page still works, labeled.

## The function fails to start

Open the deployment's logs on Vercel. The container runs `alembic upgrade head` and then uvicorn, so
the two common failures are:

- **The migration.** DATABASE_URL is missing, wrong, or Neon's compute is suspended and took too
  long to wake. Check the variable on Vercel, then open Neon and confirm the project is active.
- **The warehouses.** The image fetches them at build time from GitHub at the pinned tags; a build
  that could not reach GitHub fails at the fetch with the file it could not get.

## Answers come back refused with budget spent

Every model's daily budget is spent and the floor is answering. That is the design. The budgets
reset at midnight Pacific. /health lists each provider's use today and its cap.

## A model's answers degrade

The scheduled live eval opens a pull request with the new scorecard rows; read the per family table
and the gate catch list there. If one provider's accuracy fell, remove its key from the Vercel
environment and the router skips it; the next live eval measures it again.

## Clearing the answer log

```
uv run python scripts/reset_and_rederive.py --live    # clears answers and spans in Neon, then rederives locally
```

The demo recording writes answers; this clears them before a tag. Spans also expire on their own
after seven days.

## Rolling back

Vercel keeps every deployment. Promote the previous one from the project's deployments page; the
database schema has one migration, so a rollback never needs a down migration.
