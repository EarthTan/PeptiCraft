# PeptiCraft

> Chinese version: [中文版](README.cn.md)

PeptiCraft is a web platform for designing recombinant fusion proteins. A construct is assembled end to end from three segments: a functional peptide, a structural protein that serves as the scaffold (the scaffold protein), and a linker that joins the two. The platform pairs a precomputed screening results library with a guided builder, and evaluates each candidate against the standard that corresponds to the construct's intended delivery method.

The project is developed by the Duke Kunshan University iGEM 2026 team. This repository is the whole platform: the backend service, the web frontend, the curated data both depend on, the project documentation, and the built frontend used for deployment.

## Directory layout

| Path | Contents |
| --- | --- |
| `app/` | Frontend. React 19 and TypeScript on Vite 8; five pages; English interface. |
| `service/` | Backend. FastAPI over the `igem_peptides` PostgreSQL database; 19 endpoints under `/api`. |
| `resouces/` | Curated reference data stored as files: scaffold sequence tables, the patent source-data package, and the scenario/delivery matrix. |
| `docs/` | The project documentation set, in English. |
| `publish/` | The built frontend, plus a zero-dependency static server. |

Two directories are deliberately excluded from version control. The screening pipeline `iGEM-platform-main/` is excluded for two reasons: its size — its result archives run to hundreds of megabytes — and the fact that it carries its own documentation; it is a local copy of the `main` branch of [EarthTan/iGEM-platform](https://github.com/EarthTan/iGEM-platform), holding only what the pipeline needs to run, with code and documentation governed by the upstream address. `service/.env` is excluded because it holds the database password; `service/.env.example` is the template and lists every configuration item.

The project has two other repositories: [EarthTan/iGEM-silk](https://github.com/EarthTan/iGEM-silk) (the first-stage screening chain) and [EarthTan/iGEM-platform](https://github.com/EarthTan/iGEM-platform) (the second-stage pipeline and data). The positioning and lineage of the three are described in [`docs/repositories.md`](docs/repositories.md).

## Running locally

The PostgreSQL instance the backend reads runs on another workstation, so the backend is started first:

```bash
cd service
pip install -r requirements.txt
cp .env.example .env               # then fill in IGEM_PG_PASSWORD
python -m uvicorn app.main:app --port 8000
```

The frontend runs in a second terminal and forwards `/api` to port 8000:

```bash
cd app
npm install
npm run dev                        # http://127.0.0.1:5173
```

The backend does not auto-reload; it has to be restarted manually after a change. The remote database is not always reachable; under the default `IGEM_DB_BACKEND=auto`, an unreachable instance is replaced by a SQLite fixture packaged with the repository, which holds four hand-built constructs, and `/api/health` reports which data source is actually answering. Configuration items are listed in `service/.env.example`; `service/README.md` explains them.

## Data

There are three layers, each from a different source.

The **peptide library** holds 20,248,885 peptides of 1 to 30 residues, drawn from ten data sources. Behind it is `peptide_enrichment`, roughly 377 million rows, one row per peptide per tool.

The **construct library** holds 496 constructs across four design directions: 170 antioxidant, 65 antimicrobial, 154 anti-inflammatory and 107 anti-melanogenic. Each carries nine scores — one functional score, four safety scores and three developability scores — plus a composite score derived from the developability scores. The antioxidant and antimicrobial directions have been signed off; the other two are still in progress, and the interface labels them accordingly. Every score is precomputed and stored in the database; the service only reads them and never reruns a predictor.

The **reference library** holds 8 scaffold protein clusters totalling 16 sequences, and 15 curated linkers.

One property of the data is worth stating here. All 496 constructs point at the same placeholder scaffold row, and that row contains no sequence, so no complete end-to-end fusion sequence can be assembled from the stored data alone. The service reports this honestly rather than inventing segments: when no scaffold is specified it emits the linker and functional-peptide segments and marks the scaffold segment unavailable, and it labels every binding as placeholder, verified or inferred according to the sequence's provenance. The options for closing this gap are recorded in `docs/PeptiCraft-Documentation/04-Technical-Architecture-and-Progress.md`.

## Status

Both halves run against the real database, and every value the interface displays traces to a field in some table. The behaviours that are still temporary — the placeholder scaffold binding, the empty peptide secondary-attribute table, the linker library's missing route dimension, and the two builder steps that only change the assembled sequence without narrowing the candidate set — are listed in `app/README.md` and in the project documentation.

The platform runs end to end on local machines and has never been deployed to a public host. Deployment means running `npm run build` in `app/`, copying `app/dist/` into `publish/`, and starting the server from there.

## Documentation

`docs/PeptiCraft-Documentation/` holds six documents in English, about 130 KB in total, written for three kinds of reader: the project lead, who cares about progress rather than code; the domain expert, who cares about the biology and the meaning of each piece of data; and the person who takes the work over next. `service/README.md`, `app/README.md` and `resouces/README.md` each describe their own directory.

The competition wiki drafts, the page outline and the website optimization roadmap are in [`docs/igem-wiki/`](docs/igem-wiki/). Among them, the [2026 website and iGEM presentation optimization plan](docs/igem-wiki/Website-Optimization-Plan-2026.md) lists the current evidence, gaps and pre-submission actions against the points the official judging focuses on.

The screening pipeline under `iGEM-platform-main/` is a separate body of work with its own documentation, and is not part of this documentation set.
