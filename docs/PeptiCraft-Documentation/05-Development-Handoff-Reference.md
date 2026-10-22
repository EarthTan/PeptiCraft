# 05 Development Handoff Technical Reference

> Chinese version: [中文版](05-Development-Handoff-Reference.cn.md)

This volume is intended for developers and AI agents who take over the work later; its content is handoff information precise down to files, fields and values. It assumes that the reader will modify code, and therefore does not restate the design rationale — that rationale is in volumes 01 to 04.

## 1. Repository Layout

The repository root `iGEM-website/` contains six business directories, whose responsibilities do not overlap.

**`app/`** is the frontend single-page application, used exclusively by the frontend. The source is in `app/src/`, and the build artefacts are in `app/dist/`. This directory carries its own independent git repository.

**`service/`** is the backend FastAPI service. The source is in `service/app/`, the database migration scripts are in `service/sql/`, the data import and self-check scripts are in `service/scripts/`, and the environment configuration is in `service/.env` (the template is `.env.example`).

**`resouces/`** holds the raw files of the reference-layer data (the directory name was changed from `data/`, and is spelt as it stands), and is the import source of the two tables for scaffolds and linkers.

**`iGEM-platform-main/`** is the existing data pipeline, not a service still to be built. It contains the four-piece set of `select / scoring / assemble / run` for four directions, table-creation scripts, an operations panel, and exported result files. What this repository keeps is the pipeline code and the table-creation scripts; **the prediction models themselves are not in this repository** — they are in another codebase and are called by the pipeline in the form of local HTTP services, each service occupying a fixed port.

**`docs/`** is the documentation directory, in which `docs/PeptiCraft-Documentation/` is this documentation set. Three earlier materials sit in the same directory; their division of labour with this documentation set is explained in volume 00.

**`publish/`** is the directory of static artefacts used for formal release.

## 2. Backend Layering and File Inventory

The layering constraint is hard: `routers` only validate parameters, call services and serialize; `services` carry all thresholds, weights and business judgements; `repositories` only perform SQL and the conversion of rows into dictionaries; `models` define the response contract. When making a change, first decide which layer should be touched: a change that crosses layers reintroduces threshold drift.

| File | Responsibility |
|---|---|
| `app/main.py` | Application assembly, CORS, two exception handlers, lifecycle probes |
| `app/config.py` | Environment variables and settings |
| `app/db.py` | Connection pool, session settings, `DatabaseUnavailable` / `QueryFailed` |
| `app/services/reference.py` | **The single source of truth**: the five routes, metadata for the nine tools, the four-round retention and four-round exclusion pipeline, display information for the four directions, material forms and evidence grades |
| `app/services/scoring.py` | Assembly of the nine scores, the six components and weight pools, the composite score, the safety verdict, `VETO_GATES` |
| `app/services/constructs.py` | List and detail assembly; `assemble_row` is the single place where the judgement "which scaffold and which linker to assemble with" is made |
| `app/services/assembly.py` | Fusion sequence concatenation, segmentation, placeholder scaffold detection |
| `app/services/build.py` | Ordering and statistics for the builder: definition of the candidate set, cross-direction ordering, verdict counts, and the parsing and explanatory text for the two assembly targets |
| `app/services/scaffolds.py` | Scaffold reading and shape conversion |
| `app/services/linkers.py` | Linker reading and shape conversion; the field differences between the two tables are normalized only here |
| `app/services/analysis.py` | Protocol and template implementation for generating interpretive text, conversation |
| `app/repositories/enrichment.py` | `peptide_enrichment` reads, tool-name constants |
| `app/repositories/constructs.py` | `constructs` reads |
| `app/repositories/catalog.py` | Direction counts, peptide counts, coverage statistics |
| `app/repositories/scaffolds.py` / `linkers.py` | Reference-layer reads |
| `app/models/*.py` | Response contracts, field names identical to the frontend types |

`app/db.py` contains two groups of session settings with different semantics, which must not be mixed. Every connection is marked read-only and given a query timeout when it is created; whereas the two items of disabling sequential scans and disabling bitmap scans are **applied only when accessing `peptide_enrichment`** (`cursor(force_index=True)`), because forcing index use pays off on a large table but is slower on the 496-row `constructs`.

## 3. API Inventory

All endpoints are prefixed with `/api`. Except for conversation, all are read-only GET. Paginated endpoints uniformly return `{ items, total, limit, offset }`.

Reference data group:

| Method | Path | Parameters | Notes |
|---|---|---|---|
| GET | `/api/health` | — | Liveness and database connectivity; when the database is unreachable, `ok=false` with `error` |
| GET | `/api/meta/reference` | — | Returns directions, routes, tools, evidence grades, material forms and scaffold categories in one call |
| GET | `/api/meta/directions` | — | The four directions, with real counts and status |
| GET | `/api/meta/routes` | — | The five routes, including weight tier, immunogenicity threshold, additional check items, and accepted scaffolds |
| GET | `/api/meta/tools` | — | Metadata, dimension, threshold, direction and whether it is a veto gate, for the nine metrics |
| GET | `/api/meta/pipeline` | — | The four rounds of retention and four rounds of exclusion, definition of the composite score |
| GET | `/api/meta/coverage` | — | Actual coverage statistics of each prediction tool over the whole library |

Construct group:

| Method | Path | Parameters | Notes |
|---|---|---|---|
| GET | `/api/constructs` | `direction`, `channel`(top/bottom), `status`(passed/failed_safety/failed_score/WIP), `route_id`, `limit`(1–500, default 50), `offset` | `route_id` only affects the composite score and the safety verdict, not filtering (because filtering by route is only possible in a future implementation) |
| GET | `/api/constructs/{id}` | `route_id`, `scaffold_id`, `linker_id` | Detail; the two target parameters are used to assemble the sequence with an explicitly specified scaffold and linker, and each takes effect independently |
| GET | `/api/constructs/{id}/scaffolds` | — | The scaffolds selectable for this construct, narrowed by the archived scenario |
| GET | `/api/constructs/{id}/peptide` | — | The per-tool raw output of this peptide, including the `details` JSONB |
| GET | `/api/constructs/{id}/analysis` | `route_id` | Six sections of interpretive text |
| POST | `/api/constructs/{id}/chat` | body: `message`, `route_id`, `history` (accepted but currently ignored) | Idempotent question answering |

Build group (`app/routers/build.py`):

| Method | Path | Parameters | Notes |
|---|---|---|---|
| GET | `/api/build` | `direction` (repeatable, or comma-separated, at least one), `route_id` (defaults to the first route), `scaffold_id`, `linker_id`, `limit`(1–500, default 50), `offset` | Decides the candidate set by route and the two assembly targets and assembles a fusion sequence for each row; the response contains `counts`, `totals` and two provenance notes |

`/api/build` is the only endpoint that **composes rather than reports what is stored**; everywhere else answers "what a stored construct looks like", while it answers "what the candidates become once a route, a direction, a scaffold and a linker have been chosen". It differs from `/api/constructs` in three places that are not interchangeable. First, the candidates are taken from `channel='top'`: the bottom channel is the negative-control arm — its rows are real and its scores are real, but it exists to serve as a comparison baseline, and putting control markers into the candidate list would make both hard to read; what `scoring` reads when computing the weight pool is also exactly the `top` channel, and the order the builder produces must be the distribution the candidates belong to. Second, **pagination is cut only after the whole candidate set has been ordered**: a record's composite score depends only on the weight pool of the direction it is in, and the pool is read independently of the request and cached per direction, so a row's score does not move when the requested range narrows; ordering the full set first and slicing afterwards is the correct order rather than an expedient, and it is also what gives `offset` meaning — ordering a single page in the browser never did. Third, **each row carries its own binding state**: when a scaffold is specified the whole batch is `inferred`, and when none is specified each row falls back to its own archived binding, so within the same response some rows may have a fusion sequence and others may not.

The two assembly targets act on the same surface, and neither changes the candidate set. What a scaffold and a linker change is what sequence each candidate is concatenated into, and the fusion length shown on the card; `linker_id` is the one added later, and the reason for adding it is that among the three components of assembly only it was still pinned to a fixed value — every `constructs.linker_id` points to the first row of the sample table, `GGGGS`, which is the result of the assembly script "taking the first available row" rather than a design choice. When `linker_id` is specified the whole batch uses the same one; when it is not, each row falls back to its own archived one, in which case **rows within the same response may differ**. The explanatory text for the two provenances is given separately (`binding_note` and `linker_note`), because the two decisions are made separately: one build can take the scaffold from the archive and the linker from the request, and writing them as one paragraph would have to describe a record that is half archived and half requested. Parsing happens only once and is passed to every row; otherwise one build would issue to the remote machine as many queries as there are candidates.

The four counts of `counts` and `ranked` cover **the entire matching set**, not the page returned. The difference between the two is exactly the number that this page could not previously avoid displaying: counting per page reads where the slice lands, not the shape of the candidate set. `without_composite` records the candidates for which no composite score can be computed under that route; they are placed last rather than taking part in ordering as zero — when the direction's weight pool has only one observation there is no dispersion to weight by, so no composite score can be computed, which is a different matter from "the score is very low". A direction exceeding `CANDIDATE_CEILING` (2000) raises an error directly instead of truncating, because a ranking quietly cut short still reads like a complete ranking.

Scaffold and linker group:

| Method | Path | Parameters | Notes |
|---|---|---|---|
| GET | `/api/scaffolds` | `route_id`, `category` | List shape, without sequences and patent variants |
| GET | `/api/scaffolds/{id}` | — | Detail, including sequence variants, experiments, regulatory registrations, `unavailable_fields` |
| GET | `/api/scaffolds/{id}/constructs` | `limit` | **Currently always an empty array**, because the scaffold binding of every construct is a placeholder value |
| GET | `/api/linkers` | — | The two tables exposed merged, each row carrying `source_table` |
| GET | `/api/linkers/{id}` | — | Detail, including unit composition and literature source |

The public form of a construct identifier is `con_0001`; the service layer extracts the numeric part with a regular expression and maps it back to the database primary key. A format mismatch returns 400, and a missing record returns 404. An unknown `route_id` or `direction` also returns 400, with the legal values listed in detail.

Error semantics: `DatabaseUnavailable` → 503 with `error: database_unavailable` and troubleshooting hints; `QueryFailed` → 500 with `error: query_failed`.

## 4. Enums and Values

| Enum | Values | Notes |
|---|---|---|
| Functional direction | `antioxidant` / `antibacterial` / `anti_inflammatory` / `antimelanin` | Values as stored in the library; display names are given separately |
| Application route | `wound-dressing` / `mask-patch` / `injectable-filler` / `topical-film` / `hair-coating` | The order is the ordering of barrier integrity from broken to intact |
| Channel | `top` / `bottom` | `bottom` is the control channel; it has real scores but is not a candidate |
| Construct status | `passed` / `failed_safety` / `failed_score` / `WIP` | Only `passed` and `WIP` currently appear in the library |
| Direction status | `ready` / `wip` / `empty` | Derived from the construct total and the pass status; `wip` means there are rows but no `passed` |
| Barrier level | `tissue` / `breached` / `intact` / `non-living` | Determines the magnitude of immune exposure |
| Weight tier | `high` 1.8 / `medium` 1.0 / `low` 0.4 | |
| Score semantics | `probability` / `ranking_only` / `class_label` | `ranking_only` must not be rendered as a probability |
| Scaffold binding | `verified` / `placeholder` / `inferred` | `verified` means the scaffold row associated with the construct carries a real amino-acid sequence; `placeholder` means that row holds only a marker string; `inferred` means the scaffold is specified by a request parameter. In the current library all 496 rows are `placeholder` |
| Linker source table | `linkers` / `linker_library` | The values of `source_table` in linker responses. The former is the sample table (6 rows; construct foreign keys point here), the latter is the curated table (15 rows, with literature sources) |
| Rigidity tier | `Flexible` / `Balanced` / `Rigid` | The curated table carries text tiers itself; the sample table stores only a numeric rigidity of 0 or 1, from which the text is converted, and the raw number is returned separately in `rigidity_index` |
| Safety verdict | `clear` / `vetoed` / `borderline` / `indeterminate` | `borderline` means no failure but one item falling within 10% of the threshold |
| Threshold source | `tool` / `route` / `project` | The three have different meanings and different scopes of impact when adjusted |
| Evidence grade | `E1`–`E5` | E1 purified protein or cell-free, E2 cell, E3 animal, E4 human or controlled clinical, E5 regulatory review and post-market |
| Material form | `lyophilized` / `self-assembled-hydrogel` / `injectable-gel` / `film` / `fiber` / `sheet` / `solution` | Values extracted from the reference layer |

## 5. Tool Keys and Threshold Mapping

The correspondence among the response field names, database keys, display names and threshold sources of the nine scores is as follows. The slot for the functional score has the field name `antioxidant`, but what it carries is the functional score of the direction itself; `score_meta["antioxidant"]` is rewritten to the name of the actual predictor.

| Response field | Database key | Display name | Direction | Threshold | Threshold source | Veto gate |
|---|---|---|---|---|---|---|
| `antioxidant` | Varies by direction, see below | Varies by direction | Higher is better | 0.5 (partial) | `tool` | No |
| `toxicity` | `toxinpred3` | ToxinPred3 | Lower is better | 0.38 | `tool` (project-calibrated) | **Yes** |
| `hemolysis` | `hemopi2` | HemoPI2 | Lower is better | 0.55 | `tool` | **Yes** |
| `immunogenicity` | `mhcflurry` | MHCflurry 2.0 | Lower is better | 0.35 / 0.50 / 0.60 | `route` | **Yes** |
| `b_cell_epitope` | `bepipred3` (fallback `bepipred`) | BepiPred-3.0 | Lower is better | 0.1512 | `tool` | No |
| `thermal_stability` | `temstapro` | TemStaPro | Higher is better | No single threshold | — | No |
| `solubility` | `sodope` | SoDoPE | Higher is better | None | — | No |
| `cpp` | `plm4cpps` | pLM4CPPs | Higher is better | 0.15 | `tool` | No |
| `composite` | Computed on the server | Composite scorer | Higher is better | — | — | No |

The functional-score key and semantics of each direction (this table is the actual value of `FUNCTIONAL_SCORE` in `app/services/scoring.py`, checked direction by direction against the running service):

| Direction | Functional-score key | Display name | Semantics | Pooling key |
|---|---|---|---|---|
| `antioxidant` | `anoxpepred-frs` | AnOxPePred (FRS head) | `probability` | `aopxsvm` |
| `antibacterial` | `amp-esm` | AMPlify v0.1.0 | `probability` | `amp-esm` |
| `anti_inflammatory` | `imfp_lg_AIP` | iMFP-LG (AIP channel) | `ranking_only` | `imfp_lg_AIP` |
| `antimelanin` | `tipred` | TIPred | `ranking_only` | `tipred` |

Note that key spellings are not uniform: hyphens and underscores are mixed, and upper-case `AIP` / `AMP` coexists with all lower case. This is the original spelling as written by the pipeline, passed through as an identifier unchanged, and converted to a tool name by the mapping table only at display time. Two further key values need attention: the pooling basis of the antioxidant direction is the classifier `aopxsvm`, which stores a class label rather than a probability — the probability is in `details.prob`; the semantics of `imfp_lg_AIP` and `tipred` are overridden to `ranking_only` by the `func_score_meaning` field in the database, a field that appears on 261 rows and takes a single value.

There are three threshold sources, and only by distinguishing them can the scope of a change's impact be judged: `tool` is the decision boundary the tool itself carries (although the 0.38 of toxicity has been calibrated by the project, what is written is the tool's own `details`); `route` comes from the route's filtering configuration (the three tiers of immunogenicity); `project` is a platform constant (the 2% percentile boundary for strong MHC-II binders).

## 6. Data Semantics Invariants

Each of the following has a corresponding error precedent; they should be treated as assertions when the related code is modified.

1. **All nine scores are nullable, and empty is not zero.** Empty means not assessed. The response provides both `score_meta[field].assessed` and `assessed_flags`; the interface renders empty as "not assessed" rather than `0.00`, and gives no failing badge. Across the whole library, immunogenicity (MHC-I) is missing on 379 rows and has a value on 117 rows.
2. **Very small non-zero values must not be rendered as `0.00`.** There are more than three hundred such values across the library, concentrated in `cpp` and `solubility`. The formatting function falls back to significant figures when the value is small enough.
3. **A score with `ranking_only` semantics must not be presented as a probability.** All constructs in the anti-inflammatory and anti-melanogenic directions carry this semantics. List rows carry the marker too, because the card displays the functional score.
4. **The direction of MHC-II is the opposite of every other gate.** `higher_is_better = true`, and the pass condition is a percentile rank **higher than** 2.0. Any presentation code that writes "above the limit means out of limits" will say the opposite for this gate. The gate is currently a soft signal and does not veto.
5. **The immunogenicity threshold varies by route and must not be hard-coded.** Read `safety.immunogenicity_threshold` or the route configuration; do not use the literal 0.50.
6. **The scaffold binding of the current 496 constructs is entirely placeholder, but the service must not assume that this will always hold.** The `backbone_id` of all these 496 rows points to the same placeholder record, whose name contains `PLACEHOLDER` and whose sequence is empty. The basis on which the service judges whether a binding can be used for assembly is whether the row associated with `backbone_id` has a real amino-acid sequence: if it does, the binding is `verified` and a complete fusion sequence is output; only a marker string or an empty sequence is judged `placeholder` and the fusion sequence is refused. The judgement is concentrated in one place, `assembly.is_placeholder_backbone`, shared by assembly and by binding reporting, so there cannot be a situation where one place takes it for a real sequence and another for a placeholder. When `scaffold_id` is passed explicitly the binding is marked `inferred`, and that parameter takes precedence over the stored binding. A construct's `backbone_id` points to `backbone_proteins`, which is a table not connected with the curated library `scaffold_library`, and the two use different numbering systems.
7. **`constructs.scores` is heterogeneous by direction.** The whole table has 26 keys and no row possesses all of them; the four directions share 6 keys and the rest are direction-specific. Judging "incomplete data" by missing keys is wrong.
8. **`constructs.delivery_scores` is the old four-key scheme** (`topical` / `nanocarrier` / `microneedle` / `injection`), and no reversible mapping to the five application routes exists; it is not output externally and is returned only as an archive in the peptide detail endpoint.
9. **`constructs.full_sequence` is a label string** (of the form `4RepCT|GGGGS|<peptide>`), not an amino-acid sequence, and must not be output directly.
10. **All `constructs.linker_id` point to the first row of the `linkers` table** (`GGGGS`), so no difference in linker choice is visible on the construct table; the formal entries are in `linker_library`, distinguished in responses by `source_table`. The builder and the construct detail can explicitly specify `linker_id` to override it, in which case the fusion sequence uses that one while the construct's own archived value stays unchanged. When resolving a construct's own `linker_id`, only `linkers` may be queried, and the curated library must not be queried first: this foreign key points to the sample table, and if the curated library happens to contain an entry whose identifier is a number, querying it first would mask the row the construct actually points to. The column names of `linkers` and `linker_library` differ in two places (the former has a numeric 0/1 `rigidity` and no tier text, the latter has a text tier plus `rigidity_index`), and normalization is concentrated in one place, shared by the two read paths.
11. **Aggregation propensity is not in `peptide_enrichment`.** Querying with `tool='aggrescan'` returns zero rows; it exists only in `constructs.scores.aggrescan_a3v`, computed in real time by the pipeline at the assembly stage.
12. **`temstapro` and `sodope` exist only in `peptide_enrichment`.** Reading only `constructs` would suggest that these two metrics have never been run; in fact each has 20,248,885 rows and all 496 constructs carry values.
13. **The control channel is a control group.** Rows with `channel=bottom` are real and carry complete scores; their purpose is to provide a baseline rather than to serve as candidates.
14. **Direction status is derived from data; do not hard-code it in the frontend.** `ready` requires that the direction contain constructs in `passed` status; the anti-inflammatory and anti-melanogenic directions are therefore `wip` rather than `empty`.

## 7. Startup, Debugging and Known Pitfalls

The backend is started by running the local HTTP service as a module in the service directory, on port 8000 by default; the frontend starts a development server in the application directory, on port 5173 by default, with `/api` proxied to the backend port.

**Pitfall one: the connection string falls back to a local instance.** On the development machine another PostgreSQL instance is listening on port 5432 at the local address, without the role this project uses, and the connection reports that the role does not exist. Several default connection strings in the project are written with the local address (that is for the workstation itself), and running without an override on the development machine silently lands on the wrong instance. The service's connection configuration must explicitly point at the remote address, and `IGEM_PG_ALLOW_LOCALHOST` in `.env` should remain disabled. To judge whether the connection is correct: the `database.server` returned by `/api/health` should show PostgreSQL 16.15 and the name of that database.

**Pitfall two: the backend does not enable code hot reload.** After backend code is changed the process must be restarted manually. When an old process is occupying the port, first find the process occupying it and then terminate it; otherwise the new process cannot start while the old one keeps serving the old code — the symptom in this case is "the code was changed but the behaviour did not change".

**Pitfall three: query timeout.** Connections are uniformly given a query timeout (60 seconds by default). An unconditional `count(*)` on a table of hundreds of millions of rows such as `netmhc_score` triggers the timeout directly and returns 503, rather than being slow. When a row count is needed, read statistics rather than an exact count.

**Pitfall four: the frontend depends on the proxy.** Frontend code contains only the relative path `/api`; forwarding in the development environment is handled by the build tool configuration, and the target address can be overridden by an environment variable. Opening build artefacts directly, bypassing the development server, makes every API return 404.

## 8. Where Common Changes Land

| Need | Where to change |
|---|---|
| Change a safety gate's threshold, or add or remove a veto gate | `VETO_GATES` in `app/services/scoring.py` and the tool metadata in `app/services/reference.py`; the gate count changes in the former only |
| Change a route's weight tier or immunogenicity threshold | `ROUTES` in `app/services/reference.py` |
| Change the components or multipliers of the composite score | `COMPONENTS`, `ROUTE_WEIGHTED`, `ALPHA` in `app/services/scoring.py` |
| Add a functional direction | `DIRECTION_META` in `app/services/reference.py`, `FUNCTIONAL_SCORE` and `POOLING_KEY` in `app/services/scoring.py`; construct rows for the direction must also be added to the library, otherwise the status is `empty` |
| Change how interpretive text or conversation is generated | `app/services/analysis.py`; when a large model is wired in, add a generator implementing the same protocol and switch the registration, leaving the routes and response models unchanged |
| Change segmentation colours or assembly logic | `app/services/assembly.py` |
| Add an endpoint | Add the route under the corresponding `routers/`, put business judgements in `services/` and SQL in `repositories/` |
| Add or modify a table structure | Add a numbered script under `service/sql/` (following the sequence numbers on the pipeline side, currently used up to 21), and make the import script idempotent with "update on conflict" |

## 9. Verification Approach

After a change, verify in three layers; failure at each layer means something different: failure at the data layer means the mapping is broken, failure at the API layer means the contract has drifted, and failure at the UI layer means the presentation is inconsistent with the data.

**The data layer checks the completeness of the mapping with a set of assertions**, placed under `service/scripts/`. There are four kinds of thing to assert: whether all 496 constructs can be associated with a peptide, and whether all peptides can be associated with peptide-level scores; whether the non-null count of each of the nine scores matches the server's output; whether keys that exist in construct rows but are used by no endpoint (the direction-specific functional-score keys are the main batch) are explicitly recorded rather than silently discarded; and whether the reference layer's route narrowing counts agree with the label counts of the dataset (the five routes should be 2 / 4 / 2 / 4 / 2). This set of assertions also serves as a regression test of the database structure, so a change in structure is discovered immediately.

**The API layer compares the automatically generated OpenAPI schema with the frontend TypeScript types, field by field.** This comparison is mechanical, because the frontend types retain the backend's snake_case field names, so any renaming is exposed directly without going through a naming conversion. After the comparison, one real record is taken for each endpoint and the values in the response are checked by hand against the result of a direct query; of these, the two items computed on the server — the composite score and the safety verdict — must be reproducible by an independent calculation: the former can be recomputed by hand from the component values, weights and multipliers returned in the response, the latter from the measured value and threshold of each gate.

**The UI layer is a page-by-page walkthrough after starting the backend and the frontend.** On the landing page, check whether the statistics agree with the API; in the peptide library, check whether the list fields, filters and expansion all obtain real data; in the builder, confirm above all whether every choice actually enters the result — the route and direction determine the candidate set and the ordering, the scaffold and linker determine the assembled sequence without changing the candidate set, and a defect once occurred here in which a choice did not enter the result at all; on the result page, check whether the nine scores, the safety verdict and the sequence segments are all present; on the scaffold detail page, check how fields are filled, in particular whether fields that are declared complete but do not exist in the dataset are listed in the "unavailable" notice area rather than rendered as blank cards.

**The minimum self-check sequence after a change**: first access the health check to confirm database connectivity and the correct database name; then fetch the reference data once and confirm that the direction counts are 170 / 65 / 154 / 107 and the statuses are two `ready` and two `wip`; then fetch one construct detail and confirm that the nine scores, the composite scores for the five routes, the safety gate details and the three sequence segments are all present; finally open the frontend and walk through page by page.

**The static layer's self-check sequence is on a par with the one above, and neither replaces the other.** The backend tests number 115 in total and all run offline, requiring neither a database nor a resident service; the frontend type check covers three projects, of which the third specifically covers the edge function, because that file is the only TypeScript in the repository that runs in the production environment but not in the browser, and it had never been checked by the build process before. The static data layer has a further walkthrough with 82 assertions in total, which likewise does not need the backend to be running: it serves the export directory over HTTP and reads it with the frontend's own data layer; two of these assertions are worth remembering separately — one compares the sequence assembled by the interface with the sample produced by the server residue by residue, confirming that the two fusion sequences are completely identical, and the other confirms that every read by the page comes from a file, failing as soon as any one of them goes to the network. This walkthrough covers what neither of the previous two can: both assume that a service is available, whereas a static deployment has no service.

When the fact block, the prompt or the edge function is changed, one further check for consistency between the two languages will also fail. The fact block the model sees is written in Python on the server and in TypeScript in the edge function; the two cannot share code, so three assertions guard, respectively, that the prompt is word-for-word identical, that the sections and field names of the fact block are identical, and that all numbers are written identically. Number notation is especially error-prone: Python's format strings switch to scientific notation when the value is below 1e-4 or at least 1e6, whereas JavaScript's own default conversion does not switch at these points, and every number in the shared fact block comes from one of these two paths; the consequence is that a number the model cites cannot be found on the page. The location of the shared fact block and the case table is recorded in *06 Release Progress and Remaining Work*.

## 10. Known Implementation Inconsistencies and Legacies

The following are real problems in the current code, recorded here so that they are not later taken as the correct implementation and imitated.

**One piece of dead code, with incorrect values.** The constant `FUNCTIONAL_SCORE_BY_DIRECTION` in `app/repositories/enrichment.py` has no reference point, and two of its values are inconsistent with the implementation that actually takes effect: it writes the functional-score key of the antibacterial direction as `imfp_lg_AMP` (it is actually `amp-esm`), and writes the semantics of the anti-melanogenic direction as `probability` (it is actually `ranking_only`). What the service actually uses is `FUNCTIONAL_SCORE` in `app/services/scoring.py`, which has been checked direction by direction against the running response. This leftover constant is exactly the duplicate definition that the layering constraint exists to avoid, and should be removed in a later change.

**Display metadata is inconsistent with the actual scoring keys.** In `DIRECTION_META` in `app/services/reference.py`, the functional predictor of the antibacterial direction is written as "the AMP channel of iMFP-LG, cross-checked with AMPlify-ESM", whereas the functional-score key that actually takes part in ranking and display is `amp-esm`, with the display name AMPlify. The direction's display description does not match the actual scheme and needs to be unified.

**Two sets of type definitions coexist.** The comment in `app/models/common.py` mentions that field names are consistent with `app/src/types/index.ts`, but the frontend's current type definitions are in `app/src/api/types.ts`; the old path was deleted along with the static data layer, and the location the comment points to no longer exists.

**Legacies in the frontend.** The builder formerly fetched the direction's construct list and ordered it by composite score in the browser without issuing a calculation request; it has now been changed to call `/api/build`, with ordering and statistics done on the server, and the output of this step is the assembled fusion sequence of every candidate. The peptide library browser's search box and sort controls were added in October, with four filters and three sorts complete, and pagination is true pagination. One item remains: the application has no catch-all route, so visiting a non-existent path lands on a blank page. There are also two files in the project that are no longer rendered, one of which, `App.css`, has no reference point anywhere in the project.

**One component is defined during rendering.** `LibraryPage.tsx` retrieves the icon component inside its own options component, which static checking flags as "creating a component during render". It holds no state, so there is currently no observable consequence; the real cost is that every render obtains a new component identity, and once it comes to hold state in future it will be reset. The fix is to move icon resolution to module level. The builder's breadcrumb was formerly written the same way and has been changed to an ordinary function call.

## 11. Static Deployment and the Local Fallback Data Source

### Static Export

The formal deployment contains no backend process; data is exported once as static files before deployment by `service/scripts/export_static.py`, and the frontend reads them directly. The export script calls the route and service functions themselves rather than implementing queries and judgements separately, so the static files are byte-for-byte identical to the API responses — this is the sole basis on which these files are trustworthy enough to be published externally, and it is the property that must be preserved whenever the export script is modified. The exported content, the size estimate and the work remaining before release are recorded in *06 Release Progress and Remaining Work*.

The export artefacts are placed in `app/public/data/`, already committed to the repository. The reason for committing them is that the project is entering its final phase and this content no longer changes: after a teammate clones the repository, there is no need to connect to a database or to re-export — the pages can be run directly. The cost is that re-exporting replaces this directory wholesale, and after exporting, the new files must be committed together with it; otherwise the copy in the repository silently lags behind the one actually deployed, and the two cannot be told apart from the outside. The export script prints a warning when its source is the local fixture, and refuses to export by default, requiring an explicit `--allow-fixture` to proceed. The source field is recorded in two places: `source_backend` in `manifest.json`, and the same-named top-level field in `health.json` among the export artefacts — the latter is the field read by the data-source banner in the interface; when it reads `sqlite` the banner appears, indicating that what is currently displayed is samples rather than results. On a real-library export both places are written `postgres`. These two measures address the same thing: if a file exported from the fixture were deployed, the four demonstration records displayed on the site would be read as 496 real outputs. The banner does not offer a retry button in this situation, because static files do not change while running, and a retry button here would be a false promise.

The frontend's static data source is in `app/src/api/static.ts`, coexisting with the original data-access layer and dispatched by `request()`. The dispatch rule is `staticEnabled()`: an explicit setting takes precedence, then when a remote API address is configured the static layer gives way, and finally the decision is made by whether this is a development environment. The necessity of this rule is that the export directory sits under the frontend asset directory, and the build tool returns static files first — without the environment check, the development period would show the previous export's snapshot rather than the database's current content, and a formal build configured with a remote API would also be silently masked by the snapshot.

The static layer has one non-negotiable constraint: **it replicates no threshold, weight or judgement in the browser**. It does only two things: take one page from a list that is already ordered, and concatenate three already-exported amino-acid sequences into a fusion sequence. The former contains no scheme; the latter is string concatenation. The composite score and the safety verdict change with the application route, so at export time they are each computed once per route and written to disk.

One three-state distinction between the static layer and the API layer is also worth remembering: a route not covered in this export, and a route covered but whose record is not among them, are two different situations. The former falls back to the service; the latter reports directly that "the record does not exist". The consequence of merging them into a single empty value is that a missing record on a static deployment falls through to the single-page application's route fallback, gets back a piece of HTML, and is reported as "response format error" rather than "record does not exist".

### Local Fallback

The remote database is an instance on a workstation, accessed through a tunnel, and that workstation is not always switched on. When the database is unreachable the whole service, and the interface with it, ceases to work — exactly when development most needs it available. For this reason the service gained a layer of local fallback: `app/sqlite_backend.py` uses a small SQLite file to perform the same queries; the repository layer is not duplicated, and only the Postgres constructs the repositories actually use are translated one by one into SQLite equivalents.

The fallback is controlled by the configuration item `IGEM_DB_BACKEND`, which takes three values. `auto` is the default: the service probes the remote once before its first data access, and on probe failure switches to the local database and records the reason for the failure. `postgres` connects only to the remote and never falls back; it is used in deployment, so that a database fault is not silently concealed. `sqlite` reads only the local database and does not touch the remote at all; it is used in testing and offline development. The case of a connection dropping in mid-run is covered too: after a successful first probe, a connection that later fails also switches to the local database, and switching back to the remote requires restarting the process.

The local database is generated by `service/local/fixture_local.sql`; when the file is missing the service builds it on demand, and it can also be rebuilt manually, with the command `python service/scripts/build_local_db.py --force`. It contains four hand-built constructs, whose purpose is to make every code branch reachable within a single run. The scaffold binding of `con_9001` is a placeholder value and must not output a fusion sequence; the scaffold binding of `con_9002` carries a real sequence and must output the complete fusion sequence (scaffold + linker + functional peptide); these two together also give the composite-score weight pool two observations from which to take dispersion. `con_9003` and `con_9004` add a second direction, of which `con_9004` falls in the bottom channel and is used to verify that the builder orders only `top` candidates; the antibacterial direction has only one `top` record, so its composite score is **empty as expected**, which incidentally covers the builder's handling of empty values in ordering. `con_9003` also records the second linker of the sample table, different from that of the other three constructs, so that "each row falls back to its own archived value when no linker is specified" is an assertable fact rather than a statement. The linker library holds three further curated entries, one of which has length 15, different from the 5 of both sample-table linkers — so the difference between unspecified and specified can be judged arithmetically, not merely by letters. Any declared length in the fixture agrees with the sequence beside it — a declared length inconsistent with its own sequence would become a trap, and every arithmetic assertion written against it would fail for a reason that looks like a code defect. **These four constructs are fixture data, not pipeline output, and must not be cited as results.**

The fallback never happens silently. The service prints a warning at startup; the `database.backend` field of `/api/health` states which side is supplying data, and when it is `sqlite` it also gives `database.fallback_reason` and an explanation, with `database.server` showing the SQLite version rather than the PostgreSQL version. To judge whether an environment is running real data or fixture data, read these fields; do not infer from the values — the numeric assertions in section 6, and the direction counts in the "minimum self-check sequence" of section 9, hold only for the remote database.

The three test files under `service/tests/` exercise all read-only endpoints, the build endpoint and the chat endpoint against the fixture, run with `python -m pytest service/tests`. `test_sqlite_dialect.py` asserts each construct of the dialect translation one by one, so a new SQLite-untranslatable construct added to the repositories fails here rather than at some endpoint at runtime. `test_local_backend.py` drives the real repositories and services through the real FastAPI application, replacing only the database engine, and two of its constructs assert the `placeholder` and `verified` binding paths respectively; further assertions cover construct detail assembly with an explicit linker, because the builder's result card links to the detail page with the linker it used, and a detail page that ignored that parameter would show a different fusion sequence for the same candidate without explanation. `test_build.py` asserts the few combination decisions of the build endpoint themselves: that candidates come only from the `top` channel, that ordering covers the whole match before slicing by `limit`, that each row's binding state indeed reflects what this assembly used, and that naming a linker changes only the sequence while **the candidate set, the scores and the ranking remain unchanged item by item**.

The frontend also has a browser-independent walkthrough script, `app/verify/builder-build-check.mjs`. It renders the real `App` in jsdom, walks the builder's five steps with real clicks, and points the application's relative `/api` requests at a genuinely running service — so what is asserted is how real responses are rendered by the components, not data written to make the assertions pass. It requires `jsdom`, and the frontend currently declares no test toolchain, so the dependency is installed temporarily with `npm install --no-save --no-package-lock jsdom`; if the script is to be kept long term, it should go into `devDependencies` with an npm script. It can answer only questions about logic and markup — jsdom has no layout, so position and size it cannot answer.

This round also fixed two implementation defects, unrelated to scaffold binding but both of the same kind, "declaration inconsistent with implementation". First, **the immunogenicity gate was skipped entirely when no route was specified**: the safety verdict formerly received the route parameter from the request directly, and when that parameter was empty the immunogenicity gate, which takes its value by route, was not added to the gate list, so the response returned to `clear`, while the unassessed immunogenicity appeared neither in the gate list nor in `unassessed`, reading as though it had passed. The composite score had always had the default "take the first route when none is specified"; the safety verdict did not, and the two are now unified on the same default. Second, **linker detail could not obtain the unit composition**: `LinkerDetail` declares and renders `unit_composition` and `priority_reason`, but the query that selects them never selected these two columns, so every linker detail returned an empty unit composition. After listing the two columns, `unit_composition` is `jsonb` on the Postgres side and JSON text on the SQLite side, and the fallback layer decodes it uniformly into an object, so both sides behave the same.
