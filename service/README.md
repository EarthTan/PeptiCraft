# PeptiCraft backend service

A read-only FastAPI service over the `igem_peptides` PostgreSQL database. It is the only thing
the front end talks to: every value the interface renders arrives through one of 19 endpoints
under `/api`, and no score, threshold or safety verdict is computed in the browser.

## Running it

```bash
pip install -r requirements.txt
cp .env.example .env               # then fill in IGEM_PG_PASSWORD
python -m uvicorn app.main:app --port 8000
```

There is no automatic reload, so restart after a backend edit. Interactive documentation is at
`/docs` and the OpenAPI document at `/openapi.json`.

## Configuration

Settings are read from the environment or from `.env`. `service/.env.example` is the annotated
template and carries every key.

| Variable | Default | Meaning |
| --- | --- | --- |
| `IGEM_PG_HOST`, `IGEM_PG_PORT`, `IGEM_PG_DB`, `IGEM_PG_USER`, `IGEM_PG_PASSWORD` | — | Connection parts. The host has no localhost default: the database runs on a separate machine and is reached by its IP address. A missing host or password is a hard error. |
| `IGEM_PG_DSN` | unset | A full libpq string, as an alternative to the parts above. |
| `IGEM_PG_ALLOW_LOCALHOST` | `false` | A local PostgreSQL instance does not carry the `igem` role, and a DSN pointing at localhost is rejected unless this is set. It exists for a deliberate SSH tunnel. |
| `IGEM_DB_BACKEND` | `auto` | `auto` probes PostgreSQL once and serves the SQLite fixture when the probe fails; `postgres` never falls back; `sqlite` never touches PostgreSQL. |
| `IGEM_SQLITE_PATH`, `IGEM_SQLITE_FIXTURE` | `local/…` | Where the fixture database is written, and the SQL it is built from. |
| `STATEMENT_TIMEOUT_MS` | `60000` | Per-statement ceiling. `peptide_enrichment` holds 377 M rows in 130 GB, and an unbounded planner mistake should fail the request rather than hold a worker. |
| `PG_POOL_MIN_SIZE`, `PG_POOL_MAX_SIZE`, `PG_POOL_TIMEOUT_S` | `1`, `8`, `15` | Connection pool bounds. |
| `API_HOST`, `API_PORT` | `127.0.0.1`, `8000` | Bind address. |
| `CORS_ORIGINS` | the Vite dev server | Allowed origins, comma-separated. |
| `ANALYSIS_PROVIDER` | `template` | `template` renders deterministic prose from stored scores. `llm` is reserved for a model-backed generator and is not implemented; `LLM_BASE_URL`, `LLM_API_KEY` and `LLM_MODEL` belong to it. |

## The local fallback

The database lives on a workstation behind a tunnel and is not always up, so the service can
serve a bundled SQLite fixture instead. The fixture is built from `local/fixture_local.sql` on
first use and holds four hand-made constructs, which exist to exercise code paths and are not
pipeline output. It covers both branches of the scaffold-binding logic — one construct whose
stored binding is the same placeholder the real 496 rows carry, one whose binding carries a real
sequence — plus a second design direction and a second linker, so that multi-direction ranking
and per-row linker fallback are observable rather than assumed.

`/api/health` names the source that answered. `database.backend` reads `postgres` or `sqlite`,
and when it reads `sqlite`, `database.fallback_reason` says why the fallback engaged. A caller
that needs to know whether it is looking at real data reads this field rather than inferring it
from the size of the numbers.

Rebuild the fixture after editing its SQL:

```bash
python scripts/build_local_db.py --force
```

`app/sqlite_backend.py` translates the PostgreSQL dialect the repositories are written in — `%s`
placeholders, `= ANY(%s)` expanded into an `IN` list, array containment against `json_each`,
`::text` casts — and raises on anything it cannot translate. A statement the translation does not
cover fails as an error rather than returning a wrong answer.

## Endpoints

All under `/api`. Eighteen read, one writes.

| Method | Path | Returns |
| --- | --- | --- |
| GET | `/api/health` | Liveness plus database reachability, and which backend answered. |
| GET | `/api/meta/reference` | Directions, routes, tools, pipeline rounds and reference libraries in one payload. |
| GET | `/api/meta/directions` | The four design directions. |
| GET | `/api/meta/routes` | The five application routes and their screening profiles. |
| GET | `/api/meta/tools` | One definition per score: the predictor, the direction of improvement, the threshold and where the threshold comes from. |
| GET | `/api/meta/pipeline` | The screening pipeline rounds and their status. |
| GET | `/api/meta/coverage` | How much of the peptide library each tool covers. |
| GET | `/api/constructs` | Paged construct list. Filters: `direction`, `channel` (`top` or `bottom`), `status`, `route_id`; `limit` up to 500 and `offset`. |
| GET | `/api/constructs/{id}` | One construct with all nine scores. `route_id` selects the screening profile; `scaffold_id` and `linker_id` name assembly targets. |
| GET | `/api/constructs/{id}/scaffolds` | Scaffolds this construct could be assembled with. |
| GET | `/api/constructs/{id}/peptide` | The functional peptide and its enrichment rows. |
| GET | `/api/constructs/{id}/analysis` | Generated prose about the construct, for one `route_id`. |
| POST | `/api/constructs/{id}/chat` | Conversational form of the analysis endpoint. The only endpoint that writes. |
| GET | `/api/build` | Ranks the candidates for one `direction` and `route_id` and assembles each into a fused sequence. `scaffold_id` and `linker_id` are optional and each changes only the sequence, not the ranking. |
| GET | `/api/scaffolds` | The scaffold library. Filters: `route_id`, `category`. |
| GET | `/api/scaffolds/{id}` | One scaffold cluster. |
| GET | `/api/scaffolds/{id}/constructs` | Constructs bound to a scaffold. |
| GET | `/api/linkers` | The curated linker library. `include_placeholder` controls whether the sample-table entries are listed alongside it. |
| GET | `/api/linkers/{id}` | One linker. |

`/` returns a small service descriptor and is excluded from the schema.

## Source layout

```
app/
  main.py             the application, its error handlers and the router mounting
  config.py           settings, and the guard that refuses a localhost DSN
  db.py               the connection pool, and the DatabaseUnavailable / QueryFailed pair
  sqlite_backend.py   PostgreSQL-to-SQLite translation for the fallback backend
  models/             response models (pydantic v2), one module per endpoint group
  repositories/       one module per table group; the only place SQL is written
  services/           the decisions: scoring, safety, reference data, assembly
  routers/            HTTP binding only
```

The split between the last three layers is what keeps a change local. A repository answers with
rows; a service turns rows into a verdict or an assembled sequence; a router validates input and
chooses a status code. Two modules hold decisions that would otherwise be duplicated across
callers: `services/scoring.py` owns the composite score and the safety verdict, and
`services/constructs.py` owns `assemble`, the single place a construct's segments are put
together.

## Scripts

| Script | Purpose |
| --- | --- |
| `scripts/migrate.py` | Applies the idempotent, additive migrations under `sql/`. |
| `scripts/import_scaffold_library.py` | Imports the curated scaffold table from `data/scaffold_database_2026-09-06/` into `scaffold_library` and `scaffold_library_sequences`. |
| `scripts/import_linker_library.py` | Imports the linker library into `linker_library`. |
| `scripts/extract_linkers.mjs` | The companion that produced the linker import's input from the front end. Superseded: it reads a file the front end no longer has, so the import cannot be re-run from it as it stands. |
| `scripts/build_local_db.py` | Builds or rebuilds the SQLite fixture. |

## Tests

```bash
python -m pytest tests
```

44 tests, all offline. `test_sqlite_dialect.py` pins the PostgreSQL-to-SQLite translation against
each construct it must cover; `test_local_backend.py` drives every endpoint through the real
application against the fixture; `test_build.py` pins the ranking and the two assembly targets,
including that naming a target changes the sequence and not the candidate set.

Editing a repository so that it emits a statement the translation cannot handle fails in this
suite rather than in a deployment, which is the point of running the endpoints against SQLite at
all.

## Rules the service holds to

**A missing score is not a zero.** All nine scores are nullable, and `null` means the predictor
did not cover that peptide while `0` means it did and returned zero. The interface renders them
differently, and so does every aggregate.

**Two directions are rankings, not probabilities.** Anti-inflammatory (iMFP-LG's AIP channel) and
antimelanin (TIPred) separate functional-looking peptides from random fragments rather than
measuring activity, so the service tags the score with `ranking_only` semantics. Such a score can
be ordered but is never given a probability colour or a pass/fail badge.

**Thresholds live here, and travel with the answer.** The three safety gates are toxicity,
haemolysis and immunogenicity; B-cell epitope propensity is a soft signal rather than a gate.
Immunogenicity has no global threshold — it is 0.35 for wound dressing and injectable filler,
0.50 for mask/patch and topical film, and 0.60 for hair care — so the gate is applied from the
route's profile and the profile is returned with the response. Nothing downstream re-derives a
threshold or re-weights a component.

**Assembly is resolved once per request.** `?scaffold=` and `?linker=` are independent and either
may be omitted, in which case that part falls back to what the construct's own row records. Both
report their provenance separately, because one build can take its scaffold from the request and
its linker from the row.
