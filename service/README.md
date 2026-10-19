# PeptiCraft Backend Service

A read-only FastAPI service layered on the `igem_peptides` PostgreSQL database. The frontend communicates only with it: every value rendered by the interface is delivered through one of the 19 endpoints under `/api`, and no score, threshold, or safety verdict is computed in the browser.

## Running

```bash
pip install -r requirements.txt
cp .env.example .env               # then fill in IGEM_PG_PASSWORD
python -m uvicorn app.main:app --port 8000
```

There is no auto-reload; a restart is required after changes. Interactive documentation is at `/docs`, and the OpenAPI document is at `/openapi.json`.

## Configuration

Configuration is read from environment variables or `.env`. `service/.env.example` is an annotated template containing every key.

| Variable | Default | Meaning |
| --- | --- | --- |
| `IGEM_PG_HOST`, `IGEM_PG_PORT`, `IGEM_PG_DB`, `IGEM_PG_USER`, `IGEM_PG_PASSWORD` | — | Connection parameters. The host has no local default: the database runs on another machine and is reached by its IP address. A missing host or password is a hard error. |
| `IGEM_PG_DSN` | not set | A complete libpq connection string, used instead of the individual settings above. |
| `IGEM_PG_ALLOW_LOCALHOST` | `false` | The local PostgreSQL instance normally has no `igem` role, so a connection string pointing at localhost is rejected unless this is set. It exists for two situations: a deliberately built SSH tunnel, and this development machine, which has held the primary copy in a local database since 2026-10-11. |
| `IGEM_DB_BACKEND` | `auto` | `auto` probes PostgreSQL once and serves the SQLite fixture if the probe fails; `postgres` never falls back; `sqlite` does not touch PostgreSQL at all. |
| `IGEM_SQLITE_PATH`, `IGEM_SQLITE_FIXTURE` | `local/…` | Where the fixture database is written, and the SQL from which it is built. |
| `STATEMENT_TIMEOUT_MS` | `60000` | Upper limit for a single statement. `peptide_enrichment` has 377 million rows and 130 GB; if the planner runs away, the request should fail rather than hold a worker process. |
| `PG_POOL_MIN_SIZE`, `PG_POOL_MAX_SIZE`, `PG_POOL_TIMEOUT_S` | `1`, `8`, `15` | Lower and upper bounds of the connection pool. |
| `API_HOST`, `API_PORT` | `127.0.0.1`, `8000` | Bind address. |
| `CORS_ORIGINS` | Vite development server | Allowed origins, comma-separated. |
| `ANALYSIS_PROVIDER` | `template` | `template` renders deterministic text from stored scores. `llm` is reserved for a model-backed generator and is not yet implemented; `LLM_BASE_URL`, `LLM_API_KEY`, and `LLM_MODEL` belong to it. |

## Where the data is

As of 2026-10-11 the primary copy of the data is on the local machine. The original remote instance (`dku-1387`, `100.69.116.8`) had long been offline, so the team exported it wholesale from a physical backup instead; the export package is in `resouces/pg_export_20261011/` (checksums and row counts were verified item by item on receipt). Loading it into the local PostgreSQL `igem_peptides` database takes four steps:

```bash
psql -h 127.0.0.1 -d postgres -c "CREATE ROLE igem NOLOGIN"   # the owner named in the schema script

cd resouces/pg_export_20261011
psql -h 127.0.0.1 -d igem_peptides -f schema/schema_full.sql  # 16 tables + coverage view
psql -h 127.0.0.1 -d igem_peptides -f load.sql                # 5 / 6 / 15 / 496 / 496 / 11736
psql -h 127.0.0.1 -d igem_peptides -f ../../service/sql/22_local_frozen_enrichment_counts.sql

cd ../../service
python scripts/import_scaffold_library.py --target postgres    # 8 clusters / 16 sequences
```

`load.sql` contains `TRUNCATE … CASCADE`, whose purpose on a new database is idempotency; if the database holds sample data to keep, that section should first be commented out. The export package does not include the scaffold library, so the last step cannot be omitted.

`.env` already points at this database (`IGEM_PG_DSN` plus `IGEM_PG_ALLOW_LOCALHOST=true`); the original remote connection parameters remain at the end of the same file as comments. The service is read-only, and no writes occur other than during loading.

**The `22_local_frozen_enrichment_counts.sql` step before step 4 is not optional.** Two numbers on the home page and on the coverage page cannot be obtained by reading a single row; they exist only as aggregates over the whole `peptide_enrichment` table: how many peptides each direction's functional prediction tools have scored in total, and the coverage page's coverage. The local machine holds the 11,736 rows among those 367 million that are referenced by the 496 constructs, so recomputing in place would yield only the obviously too-small value of 496. This script freezes the per-tool counts for the 42 tools that the team aggregated on the real database as **data**, and makes the coverage view draw its values from that frozen table; the view's external column names, types, and semantics are unchanged character for character, so the server-side code needs no modification whatsoever. This step is unnecessary when the real database has the full `peptide_enrichment` installed, because its view already draws on the true counts.

After loading completes, `database.backend` in `GET /api/health` reports `postgres`, and `source_backend` in the `manifest.json` produced by `scripts/export_static.py` also reports `postgres`—the sample-data notice in the interface therefore stays silent.

## Local fallback

The database runs on a workstation that is not always online, so the service can instead serve an SQLite fixture packaged with the repository. When the local database is the primary copy (see the previous section) this fallback path does not trigger; it is retained so that the service still starts on a machine without the project database. The fixture is built on first use from `local/fixture_local.sql` and contains four hand-built constructs, whose purpose is to exercise the code paths, not to be pipeline output. It covers both branches of the scaffold-binding logic—one construct's stored binding carries the same placeholder value as the real 496 rows, and one binding carries a real sequence—plus a second design direction and a second linker, so that multi-direction ordering and per-row linker fallback are observable rather than assumed.

The scaffold library in the fixture is the exception: it can be real. The base file ships with two placeholder scaffolds beginning with `Fixture`, sufficient only to exercise the API; the curated scaffold library—the 8 protein clusters and 16 sequences in `resouces/scaffold_database_2026-09-06/`—is written separately into the same database by the import script:

```bash
python scripts/import_scaffold_library.py --target sqlite
```

This step is optional, and deliberately separate from the base file. `local/fixture_local.sql` is also the file from which the test suite builds its own database; the tests count how many scaffolds it contains and which ones are selected by application route, so the curated scaffolds cannot enter the base file, or those assertions would shift along with a dataset maintained separately by the team. The development database needs to be built only once, with the command below.

`/api/health` states which data source is actually answering. `database.backend` takes `postgres` or `sqlite`; when it takes `sqlite`, `database.fallback_reason` explains why the fallback is active. A caller that needs to know whether the data in front of it is real should read this field, rather than infer it from the magnitude of the numbers.

Rebuild after changing the fixture SQL:

```bash
python scripts/build_local_db.py --force --with-reference
```

Without `--with-reference`, only the two placeholder scaffolds from the base file are obtained.

`app/sqlite_backend.py` translates the PostgreSQL dialect written by the repositories—`%s` placeholders, `= ANY(%s)` expanded into `IN` lists, array containment against `json_each`, and `::text` casts—and raises directly on a form it cannot translate. A statement that the translation does not cover ends in an error rather than an incorrect answer.

## API

All are under `/api`. 18 reads, 1 write.

| Method | Path | Returns |
| --- | --- | --- |
| GET | `/api/health` | Liveness and database reachability, plus the backend that is actually answering. |
| GET | `/api/meta/reference` | Directions, routes, tools, pipeline rounds, and reference libraries in a single response. |
| GET | `/api/meta/directions` | The four design directions. |
| GET | `/api/meta/routes` | The five application routes and their filter profiles. |
| GET | `/api/meta/tools` | One definition per score: predictor, direction of improvement, threshold, and its source. |
| GET | `/api/meta/pipeline` | The screening pipeline's rounds and their individual status. |
| GET | `/api/meta/coverage` | Each tool's coverage of the peptide library. |
| GET | `/api/constructs` | A paginated list of constructs. Filter parameters: `direction`, `channel` (`top` or `bottom`), `status`, `route_id`; `limit` is at most 500, and `offset` is also accepted. |
| GET | `/api/constructs/{id}` | A single construct and all nine of its scores. `route_id` selects the filter profile; `scaffold_id` and `linker_id` specify the assembly targets. |
| GET | `/api/constructs/{id}/scaffolds` | The scaffolds available for assembling this construct. |
| GET | `/api/constructs/{id}/peptide` | The functional peptide and its score rows. |
| GET | `/api/constructs/{id}/analysis` | A generated passage about the construct, for the specified `route_id`. |
| POST | `/api/constructs/{id}/chat` | The conversational form of the analysis endpoint. The only endpoint that writes. |
| GET | `/api/build` | Ranks candidates for a `direction` and `route_id`, and assembles each into a fusion sequence. `scaffold_id` and `linker_id` are optional, and each changes only the sequence, not the ranking. |
| GET | `/api/scaffolds` | The scaffold library. Filter parameters: `route_id`, `category`. |
| GET | `/api/scaffolds/{id}` | A single scaffold cluster. |
| GET | `/api/scaffolds/{id}/constructs` | The constructs bound to a scaffold. |
| GET | `/api/linkers` | The curated linker library. `include_placeholder` controls whether entries from the sample table are listed as well. |
| GET | `/api/linkers/{id}` | A single linker. |

`/` returns a short service description and is not part of the API schema.

## Source layout

```
app/
  main.py             application body, error handlers, and router mounting
  config.py           configuration, plus the guard that rejects local connection strings
  db.py               connection pool, plus the DatabaseUnavailable / QueryFailed exception pair
  sqlite_backend.py   PostgreSQL-to-SQLite translation for the fallback backend
  models/             response models (pydantic v2), one module per endpoint group
  repositories/       one module per table group; the only place SQL is written
  services/           the individual judgments: scoring, safety, reference data, assembly
  routers/            HTTP binding only
```

The division of labour among the last three layers is what keeps changes confined to one place. Repositories answer with rows; services turn rows into a verdict or an assembled sequence; routers validate input and select status codes. Two modules concentrate decisions that would otherwise be repeated across callers: `services/scoring.py` owns the composite score and the safety verdict, and `services/constructs.py` owns `assemble`, the single place where a construct's parts are joined together.

## Scripts

| Script | Purpose |
| --- | --- |
| `scripts/migrate.py` | Applies the idempotent, incremental migrations under `sql/`. |
| `scripts/import_scaffold_library.py` | Imports the curated scaffold table in `resouces/scaffold_database_2026-09-06/` into `scaffold_library` and `scaffold_library_sequences`. `--target sqlite` writes to the local fixture database instead, which is the step that makes real scaffolds visible without a connection to the project database. |
| `scripts/import_linker_library.py` | Imports the linker library into `linker_library`. |
| `scripts/extract_linkers.mjs` | The companion script that produced the input for the linker import, taking its input from the frontend. Deprecated: the files it reads are no longer kept by the frontend, so the import cannot be re-run through it as things stand. |
| `scripts/build_local_db.py` | Builds or rebuilds the SQLite fixture. `--with-reference` also writes the curated scaffold library. |
| `scripts/bind_construct_backbones.py` | Backfills the 496 constructs onto real scaffolds by application route. `--dry-run` does not connect to the database, and `--emit-sql` prints executable SQL directly. It has not yet written to any production database. |
| `scripts/export_static.py` | Writes each endpoint's response to static JSON and is the last link in the chain that makes data changes take effect. The output directory is replaced wholesale rather than merged, so leftover files are no longer served; exporting from the SQLite fixture is refused by default. |

## Tests

```bash
python -m pytest tests
```

All tests run offline. `test_sqlite_dialect.py` pins the PostgreSQL-to-SQLite translation for every form that the translation must cover; `test_local_backend.py` exercises every endpoint through the real application against the fixture; `test_build.py` pins the ranking and the two assembly targets, including the rule that specifying a target changes only the sequence and not the candidate set.

When a change to a repository makes it emit a statement outside the translation's coverage, it fails in this test suite rather than at deployment—which is precisely the point of running the API against SQLite.

## Rules the service upholds

**A missing score is not zero.** All nine scores are nullable; `null` means the predictor did not cover that peptide, and `0` means it covered it and returned zero. The interface renders the two differently, and so does every aggregate value.

**Scores from two directions are for ranking only, not probabilities.** Anti-inflammatory (iMFP-LG's AIP channel) and anti-melanogenic (TIPred) distinguish "whether it looks like a functional peptide" rather than measuring activity, so the service tags such scores with the `ranking_only` semantic marker. These scores can be ranked but are never given a probability colour scale or a pass/fail badge.

**Thresholds exist only here and are returned with the answer.** The three safety gates are toxicity, hemolysis, and immunogenicity; B-cell epitope propensity is a soft signal, not a gate. Immunogenicity has no global threshold—0.35 for wound dressings and injectable fillers, 0.50 for mask patches and film-forming coatings, and 0.60 for hair care—so the gate is applied per route profile, and the profile is returned with the response. Downstream never re-derives thresholds or re-weights any component.

**Assembly is resolved once per request.** `?scaffold=` and `?linker=` are independent and both optional; when omitted, that part falls back to the value recorded on the construct's own row. The two report their origins separately, because the scaffold of a single build can come from the request while the linker comes from the row.
