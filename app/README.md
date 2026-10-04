# PeptiCraft — front end

PeptiCraft is a web platform for designing recombinant fusion proteins. A construct is three
parts joined together: a functional peptide, a structural scaffold protein, and a linker
between them. The platform exposes a pre-computed library of screened constructs and a guided
builder that scores new combinations against criteria specific to the application route.

This directory holds the front end only. Everything it renders comes from the backend service
in `../service/`, which reads the `igem_peptides` PostgreSQL instance. The project is built by
the DKU iGEM 2026 team.

## Running it

The front end needs the backend running. Start the backend first, from `../service/`:

```bash
python -m uvicorn app.main:app --port 8000
```

Then, in this directory:

```bash
npm install
npm run dev
```

The dev server listens on `http://127.0.0.1:5173`. It proxies `/api` to the backend, so the
front end only ever requests relative paths and no CORS configuration is needed in
development. The proxy target defaults to `http://127.0.0.1:8000` and can be overridden with
`VITE_API_PROXY_TARGET`.

```bash
npm run build     # type-check and produce a production bundle in dist/
npm run preview   # serve the built bundle locally
npm run lint      # oxlint
```

The backend runs without automatic reload. Restart it manually after changing backend code.

## Routes

| Path | Page |
|---|---|
| `/` | Landing page: platform framing, direction counts, application routes, pipeline rounds |
| `/library` | Library browser: peptides and constructs, scaffolds, linkers |
| `/builder` | Construct builder: a five-step guided flow |
| `/results/:id` | Results for one construct |
| `/library/scaffold/:id` | Scaffold details |

## Source layout

```
src/
  api/          client.ts (fetch, error normalisation), index.ts (endpoint bindings),
                types.ts (mirrors of the backend response models)
  components/   Layout and hand-built UI primitives; construct-panels.tsx holds the three
                panels the Library and Results pages share
  lib/          useAsync.ts (data loading, with a ticket guard against stale responses),
                display.ts, score.ts, derive.ts, sequence.ts
  pages/        one module per route
```

There is no state management library. Each page holds its own data, and route parameters
carry what has to cross a page boundary.

Two rules hold across the front end and matter when changing it:

**No static data.** There is no `src/data/` and no `src/types/`. Every value rendered comes
from an endpoint. The field names in `api/types.ts` keep the backend's snake_case spelling
deliberately, so an OpenAPI-to-TypeScript diff is a mechanical comparison rather than a
translation.

**No threshold logic.** Composite scores, safety verdicts and route-specific immunogenicity
thresholds are all computed by the backend and returned with the response. The front end does
not compare a score against a threshold or weight anything. This is what keeps a threshold in
exactly one place; the alternative produced a period where the same safety thresholds were
written out in several places and one copy disagreed with the route definitions.

## Tech stack

React 19 with TypeScript, built on Vite 8. Styling is Tailwind CSS v4 using the CSS-first
`@theme` configuration, with a component layer assembled by hand on top of Radix UI primitives
rather than a generated component library. Routing is `react-router-dom` v7, icons are Lucide,
and linting is Oxlint. The interface is English throughout.

## Status

The five pages read real data from the database. Every value on the Library, Builder, Results
and Scaffold pages can be traced to a table and a field.

The builder walks five steps — route, function, scaffold, linker, results. The last step calls
`/api/build`, which ranks the candidates and assembles each fused sequence on the server rather
than in the browser.

Four things are still provisional, and they are visible in the interface rather than hidden:

- Neither assembly target narrows the candidate set. Every stored construct binds a placeholder
  scaffold, and every one records the same sample-table linker; both steps say so. What the two
  choices change is the sequence each candidate is assembled into, and the fused length
  reported beside it.
- The linker library is not narrowed by route. All five routes are offered the same entries,
  because `linker_library` carries no route dimension yet.
- The fused sequence is not emitted in full. The scaffold segment is marked unavailable, and
  only the linker and peptide segments — which are real — are drawn. Naming a scaffold
  explicitly re-assembles the sequence and labels the binding as inferred.
- The Library browser has filtering but no search field and no sorting controls, and "show
  more" increases the page size rather than paging.

Two engineering points are known and unfixed: there is no catch-all route, so an unknown path
renders blank, and `src/App.css` is unreferenced.

## Documentation

Project documentation lives in `../docs/PeptiCraft-文档体系/` and is written in Chinese. It
covers the product form and user experience, the data assets, the biology and screening
pipeline, the architecture and development progress, and a technical handover reference.
