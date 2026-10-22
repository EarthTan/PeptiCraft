# Published Front End

> Chinese version: [中文版](README.cn.md)

The static single-page application built from `app/` and copied here. `assets/` holds the hashed frontend scripts and styles, `data/` holds the data snapshot the pages need, and `server.js` is a zero-dependency Node static server that falls back to `index.html` for unknown page paths.

## How it is produced

The content comes from the frontend build and is copied over as a whole:

```bash
cd ../app
npm run build
cp -R dist/. ../publish/
```

The frontend, icons and data files here are all build artefacts. Nothing in this directory is meant to be edited by hand: a change made here is lost the next time the bundle is copied over, so it should be made in `../app/src/` or `../app/public/` and then rebuilt.

## How to run

```bash
node server.js
```

The server listens on port 3000, or on the value of `PORT` when that is set. It accepts no other configuration and needs no dependencies installed.

## Status

Data queries are answered by the static snapshot shipped with the bundle. The chat endpoint is provided by a Cloudflare Pages Function, so chat is unavailable when this Node static server is run on its own. To enable chat, the Pages Function has to be deployed or a compatible backend API provided.
