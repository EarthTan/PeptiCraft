# Deploying to Cloudflare Pages

The platform is served as static files. There is no Python service at runtime and no database
in the request path: every page reads JSON exported from the pipeline's own database, and the
one endpoint that cannot be answered from a file — the chat — runs as a Pages Function so the
model key stays out of the browser.

## What is deployed

    dist/                          the built frontend
    dist/assets/*                  hashed bundles, cached forever
    dist/data/*                    the exported snapshot, cached with revalidation
    dist/_headers                  cache policy and security headers
    dist/_redirects                SPA routing
    functions/api/constructs/[id]/chat.ts    the model proxy

`functions/` sits beside `package.json`, not inside `dist/`. Cloudflare reads it from the
project root, and there is nothing to configure for it: the directory is fixed.

## Producing the export

The export is produced once from the real database, on the machine that can reach it. It cannot
be produced from the bundled fixture, which holds four hand-made constructs and no pipeline
data; a deployment built from it would present those four as the library. The script therefore
refuses to run against the fixture unless it is told to, and the flag that tells it is for local
work only.

    cd service
    python scripts/export_static.py --out ../app/public/data

Read the summary it prints. It reports how many files and how many megabytes were written.
`manifest.json` and `health.json` both record `source_backend`, which is the name of the
database that answered, and that field is the one to check before deploying: `postgres` is the
pipeline's own data, `sqlite` is the sample fixture.

The master copy of the data now lives on this development machine rather than on the far
workstation, so "the machine that can reach it" is the local one. `../service/README.md`
records how the team's export was loaded here, and the one step that is easy to miss: the home
and coverage pages read two full-library aggregates that a subset-only database cannot compute,
so `service/sql/22_local_frozen_enrichment_counts.sql` has to be applied before exporting
locally.

The export replaces the output directory rather than merging into it. That matters more than it
sounds: the static layer turns a request path straight into a file path, so a record left behind
by an earlier export is still reachable even though the manifest does not name it. A re-run
therefore cannot leave one behind. The directory is only cleared when it already carries a
`manifest.json` of ours, so a mistyped `--out` is left untouched.

A build made from the fixture is not silent. `source_backend: "sqlite"` is carried into
`health.json`, and the interface reads it and puts the sample-data banner on every route, so
such a build announces itself wherever it runs. That is a safety net for a mistake, not a
licence to deploy a fixture export.

## Building

    cd app
    npm run build

The build copies `public/` verbatim, so `public/data/` becomes `dist/data/`. There is no
separate upload step and no environment variable to set for the data path: the frontend looks
for `/data`, which is where the build places it. `VITE_DATA_BASE` exists only for a deployment
that serves the export from somewhere other than the site root.

`npm run build` type-checks three projects: `src`, the Vite config, and `functions/`. The last
of those is the model proxy, which runs in production but not in a browser, and it has its own
`tsconfig.functions.json` for that reason.

## Serving the export in development

`npm run dev` serves `public/data` and needs nothing else running: the flag it sets makes the
frontend read the export before any request goes out. `npm run dev:api` is the other mode — it
talks to the service through the Vite proxy and ignores whatever export is on disk, which is
what to use when the page has to reflect the database as it stands.

    npm run dev          # serve the export; nothing else needs to run
    npm run dev:api      # proxy /api to the service instead

The reason the proxy mode exists at all is that an export is a snapshot of whatever database
produced it, and on a development machine that is usually not the database being worked on. A
page rendered from a stale export says nothing about it, which is the one failure mode the
data-source banner cannot catch on its own — unless the export was made from the fixture, in
which case the banner does announce it. Under either script the choice reduces to one variable:
`VITE_STATIC=1` forces the export, `VITE_STATIC=0` forces the network.

## Verifying before deploying

    cd service && python -m pytest tests        # 113 tests, all offline; two skip on the fixture
    cd app && npm run verify:static             # the static layer, no backend needed

The second one is the one that matters for a static deployment. It serves `public/data` over
HTTP and drives the frontend's own data layer against it, including the assertion that the
sequences the interface assembles match residue for residue what the service itself produced.
Every request the pages make is answered from a file, and the check fails if any of them reaches
for a network.

It reads the export rather than producing one, so it needs an export to exist: run it after
`export_static.py`, not on a fresh clone. It is a step to take on the machine that has the data,
not a gate that a build server can run.

## Deploying

Build first, then upload the result. The export has to be in place before `npm run build`,
because the build copies it:

    cd app
    npm run build
    npx wrangler pages deploy dist --project-name pepticraft

Uploading a directory directly rather than connecting the repository is the arrangement this
project uses. The export is produced from a database that Cloudflare's build environment cannot
reach, so the machine that has the data is the machine that builds and uploads.

The export is committed (`app/public/data/`), which is what lets a teammate clone the repository
and serve the site without a database or a re-export. The cost is the other direction: a
re-export has to be committed as well, or the repository's copy drifts behind the deployed one
while looking exactly as authoritative.

Settings, for a dashboard-connected project:

| Setting | Value |
| --- | --- |
| Framework preset | None |
| Build command | `npm run build` |
| Build output directory | `dist` |
| Root directory | `app` |

The root directory is `app`, not the repository root, because `package.json` and
`wrangler.jsonc` are there.

## Environment variables

Set these in the dashboard, not in the repository. `LLM_API_KEY` must never be committed and
never reaches the browser: the Function reads it, and nothing else can.

| Variable | Required | Meaning |
| --- | --- | --- |
| `LLM_BASE_URL` | for chat | OpenAI-compatible API base or full chat endpoint. A bare host uses `/v1/chat/completions`; a base with a path (for example `/api/v4` or `/compatible-mode/v1`) gets `/chat/completions` appended; a full `/chat/completions` endpoint stays unchanged. |
| `LLM_API_KEY` | for chat | The provider's key. |
| `LLM_MODEL` | for chat | The model id, e.g. `qwen-plus`. |

Without them the data pages remain available, but AI conversation is disabled. Readers can
explicitly select **View records**; this is not a generated answer and does not enter the AI
conversation. With a model configured, it writes an answer to the actual question and recent
history, using validated references to record facts and sources. Model errors are shown as
errors instead of being silently replaced with record paragraphs.
`GET /api/chat/status` reports configuration without exposing the endpoint or key.
`llm_configured` means the settings exist, not that a live provider call has succeeded.
See [AI chat verification](../docs/AI-Chat-Verification.md) for the evidence contract and checks.

The presence of those three variables is the only switch. The service has `ANALYSIS_PROVIDER`,
but a Pages Function has no equivalent and does not read the export's `analysis_provider`
either, so a deployment that wants the model off has to remove the key rather than set a flag.
There is nothing to re-export: the function reads the variable, not the snapshot.

The chat endpoint takes a question from anyone who can reach the site and spends the key on it.
One request is bounded — the JSON body at 32 KiB, the question at 2,000 characters, the history
at the last six turns of at most 4,000 characters each, the model reply at 1,800 tokens by default and
the rendered answer at 4,000 characters — but the number of requests is not, and
neither is the identity of whoever sends them. A rate-limiting rule on `/api/constructs/*/chat`
in the Cloudflare dashboard is the control for that, and it is not configured here.

`MiniMax-M3.1-Flash` uses a separate 8,192-token reasoning-and-answer budget, medium
reasoning effort, split reasoning output and a 60-second model timeout. This model requires
thinking, so the default short output budget may otherwise be exhausted before it returns an
answer. Other models retain the 20-second timeout. See the provider's
[OpenAI compatibility documentation](https://platform.minimax.cn/docs/api-reference/text-openai-api).

## What the deployment does not do

It does not recompute anything. The composite, the safety verdict and the Builder's ranking were
computed once at export time by the same service that serves the API in development, and the
static files are that service's own output. Re-running a predictor means re-running the export.

It also does not keep the peptide library. The 20.2 M-row table is not exported — no browser
needs it, and it would be a hundred gigabytes. What is exported is the 496 screened constructs
and the predictions that bear on them, together with the raw per-predictor output in
`peptide_details.json`, which is the largest single file in the export. The Builder contributes
one ranking file per direction set — fifteen per route, since a set is ranked as a set and a
request cannot be answered by slicing a larger one — so expect roughly 8.5 MB or more across
about 1,550 files for the real database, against 0.4 MB and 125 files for the fixture. Pages'
limits are 25 MB per file and 20,000 files.
