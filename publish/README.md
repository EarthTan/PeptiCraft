# Published front end

The built front end, kept in the repository so a deployment needs nothing from the build
toolchain. It is a static single-page application — `index.html`, one hashed JavaScript bundle and
one hashed stylesheet under `assets/`, two SVG assets — served by `server.js`, a zero-dependency
Node static server that falls back to `index.html` for unknown paths so that client-side routes
resolve.

## Producing it

The contents come out of the front end build and are copied in whole:

```bash
cd ../app
npm run build
cp -R dist/. ../publish/
```

The files are build output. Nothing here is edited by hand: a change made in this directory is
lost the next time the bundle is copied over it, and belongs in `../app/src/` instead.

## Running it

```bash
node server.js
```

The server listens on port 3000, or on `PORT` when that is set. It takes no other configuration
and needs no dependencies installed.

## Status

The platform has never been deployed to a public host, so this directory is a prepared artefact
rather than a running one. The front end requests `/api` on its own origin unless
`VITE_API_BASE` is set at build time, so a deployment either serves the backend at that path on
the same host or rebuilds the bundle pointed at the service's origin.
