# PeptiCraft — Front End

PeptiCraft is a web platform for designing recombinant fusion proteins. A construct is assembled from three segments: a functional peptide, a scaffold protein that serves as the scaffold, and a linker joining the two. The platform exposes a precomputed screening results library and a guided builder that scores new combinations against the standard for each application route.

This directory holds the frontend only. Everything it renders comes from the backend service in `../service/`, which reads the `igem_peptides` PostgreSQL instance. The project is developed by the Duke Kunshan University iGEM 2026 team.

## Running

By default the frontend reads an already-exported static data set, so it runs on its own without starting the backend or the database at the same time:

```bash
npm install
npm run dev
```

The development server listens on `http://127.0.0.1:5173`, and every value on a page comes from the export files under `public/data/`. The export is generated from the database by `../service/scripts/export_static.py` and is committed with the repository, so a clone runs without an export first; after the data changes it has to be re-exported before the change shows on a page:

```bash
cd ../service && python scripts/export_static.py --out ../app/public/data
```

The copy in the current working tree comes from the real database: 496 constructs, the team's curated scaffold library of 8 protein clusters, and 15 linkers. `source_backend` in `manifest.json` records where it came from — when it is `postgres` no banner appears at the top of a page, and when it is `sqlite` a banner states that this is sample data. An export replaces `public/data/` as a whole rather than merging into it, so files left by the previous export are no longer served.

The copy shipped in the repository is the snapshot taken when it was exported and does not update automatically after later database changes; to see the database's current state, use the backend-connected mode below.

To see the database's current state, switch to the backend-connected mode. First start the service in `../service/`:

```bash
python -m uvicorn app.main:app --port 8000
```

Then in this directory:

```bash
npm run dev:api
```

In this mode `/api` is forwarded to the backend, the frontend requests relative paths only, and no CORS configuration is needed during development. The forwarding target defaults to `http://127.0.0.1:8000` and can be overridden with `VITE_API_PROXY_TARGET`.

```bash
npm run build     # type-check and emit the production bundle to dist/
npm run preview   # serve the built bundle locally
npm run lint      # oxlint
```

The backend does not auto-reload while running. After changing backend code it has to be restarted manually.

The two modes cover different endpoint sets. Chat is the only endpoint carried by POST and the static data does not provide it, so under `npm run dev` it cannot get an answer and is handled only in the deployed environment, by a Pages Function.

## Routes

| Path | Page |
|---|---|
| `/` | Home page: platform positioning, direction counts, application routes, pipeline rounds |
| `/library` | Library browser: peptides and constructs, scaffolds, linkers |
| `/builder` | Construct builder: five-step guided flow |
| `/results/:id` | Result page for a single construct |
| `/library/scaffold/:id` | Scaffold detail |

## Source layout

```
src/
  api/          client.ts (requests, error normalisation), index.ts (endpoint bindings),
                types.ts (mirror of the backend response model)
  components/   layout and hand-built UI primitives; construct-panels.tsx holds the three
                panels shared by the library page and the results page
  lib/          useAsync.ts (data loading, with a ticket guard against stale responses),
                display.ts, score.ts, derive.ts, sequence.ts
  pages/        one module per route
```

There is no state-management library. Each page holds its own data, and anything that has to cross a page boundary goes into the route parameters.

Two rules run through the frontend and have to be respected when changing it:

**No static data.** There is no `src/data/` and no `src/types/`. Every rendered value comes from an endpoint. Field names in `api/types.ts` deliberately keep the backend's snake_case spelling, so that comparing OpenAPI with TypeScript is a mechanical check rather than a translation.

**No threshold logic.** The composite score, the safety verdict and the per-route immunogenicity threshold are all computed by the backend and returned with the response. The frontend does not compare a score with a threshold and does not weight anything. Thresholds therefore exist in one place only; an earlier approach had the same set of safety thresholds written in several places, one of which disagreed with the route definition.

## Technology stack

React 19 with TypeScript, built on Vite 8. Styling uses Tailwind CSS v4 with CSS-first `@theme` configuration; the component layer is built by hand on Radix UI primitives rather than using a generated component library. Routing uses `react-router-dom` v7, icons use Lucide, and linting uses Oxlint. The interface is in English throughout.

## Status

All five pages read data from the database — in the static deployment, from its exported snapshot. Every value on the library page, the builder, the results page and the scaffold page traces to a field in some table.

The builder runs five steps — route, function, scaffold, linker, results. The last step calls `/api/build`, and the server ranks the candidates and assembles each fusion sequence rather than the browser doing it.

Four things are still temporary and are visible in the interface rather than hidden:

- Neither assembly target narrows the candidate set. A construct archive already records one scaffold and one linker (that scaffold is the placeholder row, see the next item), and both steps override the archive; the two selections change the sequence each candidate is assembled into, and the fusion length reported beside it.
- The linker library does not narrow by route. All five routes receive the same entries, because `linker_library` has no route dimension yet.
- The fusion sequence is not emitted in full. The archived bindings of the 496 constructs still point at the same placeholder scaffold, so the scaffold segment is always marked unavailable and only the linker and functional-peptide segments are drawn — those two are real. Explicitly specifying a real scaffold reassembles the sequence and marks the binding as inferred.
- The library browser has filters but no search box and no sort control, and "show more" increases the page size rather than paginating.

Unknown paths now have an explicit fallback page. `src/App.css` is still unreferenced and can be removed or wired back into the global style system when the styling is tidied up.

## Documentation

The project documentation is in `../docs/PeptiCraft-文档体系/` and is written in English. It covers product form and user experience, data assets, biology and the screening pipeline, architecture and development progress, and a development handoff technical reference.
