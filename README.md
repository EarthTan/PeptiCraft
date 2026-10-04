# PeptiCraft

PeptiCraft is a web platform for designing recombinant fusion proteins. A construct joins three
parts end to end: a functional peptide, a structural scaffold protein, and a linker between them.
The platform pairs a pre-computed library of screened constructs with a guided builder, and
evaluates each candidate against criteria that depend on how the construct is meant to be
delivered.

The project is built by the DKU iGEM 2026 team. This repository is the whole platform: the
backend service, the web front end, the curated data behind both, the project documentation, and
the built front end used for deployment.

## Layout

| Path | Contents |
| --- | --- |
| `app/` | Front end. React 19 and TypeScript on Vite 8; five pages; English interface. |
| `service/` | Backend. FastAPI over the `igem_peptides` PostgreSQL database, 19 endpoints under `/api`. |
| `data/` | Curated reference data as files: the scaffold sequence database, the patent source packs, and the scenario/delivery matrix. |
| `docs/` | The project documentation set, in Chinese. |
| `publish/` | The built front end plus a zero-dependency static server. |

Two directories sit outside version control, both deliberately. `iGEM-platform-main/`, the
screening pipeline, is left out on size grounds — its result archives run to hundreds of
megabytes — and because it carries its own documentation. `service/.env` is left out because it
holds the database password; `service/.env.example` is the template and lists every setting.

## Running it locally

The backend reads a PostgreSQL instance that lives on a separate workstation, so it starts first:

```bash
cd service
pip install -r requirements.txt
cp .env.example .env               # then fill in IGEM_PG_PASSWORD
python -m uvicorn app.main:app --port 8000
```

The front end runs in a second terminal, and proxies `/api` to port 8000:

```bash
cd app
npm install
npm run dev                        # http://127.0.0.1:5173
```

The backend has no automatic reload, so a backend edit needs a manual restart. The remote
database is not always reachable; under the default `IGEM_DB_BACKEND=auto` an unreachable
instance is replaced by a bundled SQLite fixture of four hand-made constructs, and `/api/health`
names the source that actually answered. Settings are listed in `service/.env.example` and
described in `service/README.md`.

## The data

Three layers, each of a different origin.

The **peptide library** holds 20,248,885 peptides of 1 to 30 residues, drawn from ten sources.
Behind it sits `peptide_enrichment`, about 377 million rows, one row per peptide per tool.

The **construct library** holds 496 constructs across four design directions: 170 antioxidant,
65 antibacterial, 154 anti-inflammatory and 107 antimelanin. Each carries nine scores — one
functional, four safety, three developability, and a composite derived from the developability
ones. The antioxidant and antibacterial directions are signed off; the other two are works in
progress and the interface labels them as such. Every score is pre-computed and stored in the
database; the service reads them and never re-runs a predictor.

The **reference libraries** hold 8 scaffold protein clusters covering 16 sequences, and 15
curated linkers.

One property of the stored data is consequential enough to state here. All 496 constructs point
at a single placeholder scaffold row that carries no sequence, so a fused sequence cannot be
assembled end to end from the stored data alone. The service reports this rather than fabricating
a segment: with no scaffold named it emits the linker and peptide segments and marks the scaffold
segment unavailable, and it labels each binding as placeholder, verified or inferred according to
where the sequence came from. The options for closing the gap are recorded in
`docs/PeptiCraft-文档体系/04-技术架构与开发进度.md`.

## Status

Both halves run against the real database, and every value the interface shows traces to a table
and a field. The behaviour that is still provisional — the placeholder scaffold binding, the empty
peptide-metadata table, the linker library having no route dimension, and the builder steps that
change the assembled sequence without narrowing the candidate set — is listed in `app/README.md`
and in the project documentation.

The platform has been exercised end to end on a local machine and has never been deployed to a
public host. Deployment is `npm run build` in `app/`, copying `app/dist/` into `publish/`, and
running the server from there.

## Documentation

`docs/PeptiCraft-文档体系/` holds six documents in Chinese, about 130 KB together, written for
three readers: the project lead, who needs the state of the work rather than the code; domain
specialists, who need the biology and the meaning of the data; and the next person to take the
work over. `service/README.md`, `app/README.md` and `data/README.md` describe their own
directories.

The screening pipeline under `iGEM-platform-main/` is a separate body of work with its own
documentation, and is not part of this set.
