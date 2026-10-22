/**
 * Drives the static data layer end to end, with no backend and no bundler running.
 *
 * This is the check the static deployment needs and the existing two cannot provide. Both of
 * those load the app through Vite's SSR pipeline and talk to the real service over HTTP, which
 * was the right shape when a service was always present. A deployment served from Cloudflare
 * Pages has no service at all: every response is a file. If the static layer has a mistake in
 * it — a wrong path, a filter that drops a row, an assembled sequence that does not match what
 * the service produced — nothing else in the project would notice, because the backend tests
 * still pass and the dev proxy still answers.
 *
 * So this serves `public/data` over HTTP and lets the app's own modules read it exactly as a
 * browser would. The modules are loaded with Node's built-in TypeScript stripping rather than
 * through Vite: Vite's SSR pipeline takes long enough on this machine that the check would
 * dominate the run, and the modules under test here have no JSX and no CSS import, so the
 * bundler has nothing to do for them. The type checking is `npm run build`'s job, not this
 * script's.
 *
 * The one thing it also checks is the part a static build has to get right that nothing else
 * would catch: the sequences. `assembly.json` carries a worked example the service itself
 * produced, so the interface's own concatenation is compared against it residue by residue. A
 * static layer that assembled a candidate differently from the service would otherwise ship a
 * wrong sequence while every other assertion still passed.
 *
 * Run:
 *   npm install                      # once; this script needs nothing beyond the app's own deps
 *   node verify/static-export-check.mjs
 *
 * It also runs the Pages Function's fact-block number formatter over
 * `verify/number-format-cases.json`, the table the service's own tests are checked against. The
 * function has no imports and nothing at module scope, so Node's type stripping runs it
 * directly.
 */
import { createReadStream, existsSync, statSync } from 'node:fs'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { createServer } from 'node:http'
import { dirname, extname, join, normalize, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const DATA_DIR = join(ROOT, 'public', 'data')
const PORT = Number(process.env.PC_STATIC_PORT ?? 4399)

let failures = 0
function check(label, condition, detail) {
  if (condition) console.log(`  ok   ${label}`)
  else {
    failures += 1
    console.log(`  FAIL ${label}${detail === undefined ? '' : ` — ${detail}`}`)
  }
}

// ---------------------------------------------------------------------------
// A static host for the exported files, which is all a Pages deployment is
// ---------------------------------------------------------------------------

const MIME = {
  '.json': 'application/json',
  '.js': 'text/javascript',
  '.css': 'text/css',
  '.html': 'text/html',
}

const escaped = []
// Request-local test snapshots, without changing the deployment's exported files on disk.
const assetOverrides = new Map()

const realFetch = globalThis.fetch
globalThis.fetch = (input, init) => {
  const url = typeof input === 'string' ? input : input.url
  if (url.startsWith('/data/')) {
    return realFetch(`http://127.0.0.1:${PORT}${url}`, init)
  }
  if (url.startsWith('/api/')) {
    // No backend is running. A request that escapes the static layer is recorded and
    // rejected, so a check that expects the network to be used can assert that it was, and
    // a check that does not can assert that it was not.
    escaped.push(url)
    return Promise.reject(new Error(`no service running: ${url}`))
  }
  return realFetch(input, init)
}

const staticServer = createServer((req, res) => {
  const url = new URL(req.url ?? '/', 'http://localhost')
  // The app asks for `/data/...` because that is the path Vite serves `public/data` at, so
  // the prefix is stripped here to reach the directory. A real deployment does the same thing
  // by publishing `public/` at the site root.
  const relative = url.pathname.replace(/^\/data\/?/, '')
  if (assetOverrides.has(relative)) {
    const payload = assetOverrides.get(relative)
    res.writeHead(payload === null ? 404 : 200, { 'Content-Type': 'application/json' })
    res.end(JSON.stringify(payload))
    return
  }
  const file = join(DATA_DIR, normalize(relative).replace(/^(\.\.[/\\])+/, ''))
  if (!existsSync(file) || !statSync(file).isFile()) {
    res.writeHead(404, { 'Content-Type': 'application/json' })
    res.end(JSON.stringify({ error: 'not_found', detail: url.pathname }))
    return
  }
  res.writeHead(200, {
    'Content-Type': MIME[extname(file)] ?? 'application/octet-stream',
    'Cache-Control': 'public, max-age=60',
  })
  createReadStream(file).pipe(res)
})

await new Promise((done) => staticServer.listen(PORT, '127.0.0.1', done))
console.log(`static export served on 127.0.0.1:${PORT}\n`)

// ---------------------------------------------------------------------------
// The app's own modules
// ---------------------------------------------------------------------------
//
// `import.meta.env` is a Vite construct with no meaning outside a bundle, and the static layer
// reads its values. Node cannot inject them into a module specifier, so `static.ts` reads
// `import.meta.env` defensively and defaults to the path Vite serves `public/data` at. The
// value under test is therefore the value that ships.
//
// The extensionless specifier (`./static` in `client.ts`) is resolved here rather than in the
// source, because adding `.ts` to it would be a change made for the checker's benefit: Vite
// resolves extensionless imports and the production bundle already builds. Node's ESM resolver
// does not, so the loader below supplies the one extension Node is missing.

const MODULE_CACHE = new Map()

async function loadAppModule(specifier) {
  const url = pathToFileURL(join(ROOT, 'src', specifier))
  return import(url.href)
}

/** Import a module with extensionless relative specifiers resolved to `.ts`. */
async function loadModuleWithTs(specifier) {
  const target = join(ROOT, 'src', specifier)
  const source = await readFile(target, 'utf8')
  const rewritten = source.replace(
    /(\bfrom\s+["'])(\.[^"']*?)(["'])/g,
    (match, prefix, spec, quote) =>
      spec.endsWith('.ts') ? match : `${prefix}${spec}.ts${quote}`,
  )
  // The cache file keeps the `.ts` extension on purpose: Node strips types from `.ts` and not
  // from `.mjs`, so writing it out as `.mjs` would hand the parser raw TypeScript.
  //
  // Sibling modules are copied next to it rather than imported from `src/`, because a relative
  // specifier rewritten to `.ts` resolves against the cache directory. The copy is the same
  // source the bundler would compile.
  const cacheDir = join(ROOT, '.verify-cache')
  await mkdir(cacheDir, { recursive: true })
  const shim = join(cacheDir, `${specifier.replace(/[/.]/g, '_')}.ts`)
  await writeFile(shim, rewritten)
  for (const sibling of ['static.ts']) {
    const from = join(ROOT, 'src', 'api', sibling)
    await writeFile(join(cacheDir, sibling), await readFile(from, 'utf8'))
  }
  return import(pathToFileURL(shim).href)
}

console.log('manifest and reference data')
{
  const staticMod = await loadAppModule('api/static.ts')
  check('an export is detected', (await staticMod.staticAvailable()) === true)

  const health = await staticMod.serveStatic('GET', '/api/health', new URLSearchParams())
  check('health names a static backend', health?.database?.backend === 'static', health?.database?.backend)
  check('health carries an export date', typeof health?.static !== 'undefined')
  // A static deployment has no database to be unreachable, so `backend` alone cannot tell the
  // interface whether these files are pipeline output or the sample fixture. `source_backend`
  // is what the banner reads, and without it a fixture-derived build would be silent on every
  // page — which is the failure the banner exists to prevent.
  check(
    'health names the database the export came from',
    typeof health?.source_backend === 'string',
    health?.source_backend,
  )
  // Which value it carries depends on the export sitting on disk: `sqlite` when it came from
  // the bundled fixture, `postgres` when it came from the real instance. Pinning it to one of
  // them would make this a statement about the machine the check runs on rather than about the
  // code, so what is asserted is that the two records agree and that the value is one the
  // banner knows how to describe.
  const manifestBackend = JSON.parse(
    await readFile(join(ROOT, 'public', 'data', 'manifest.json'), 'utf8'),
  ).source_backend
  check(
    'the export source is declared, matches the manifest, and is one the interface knows',
    health?.source_backend === manifestBackend &&
      ['postgres', 'sqlite'].includes(health?.source_backend),
    `health=${health?.source_backend} manifest=${manifestBackend}`,
  )
  // The field is only worth writing if something reads it. The banner is the reader, and it
  // cannot be rendered from here — it is JSX and this script loads the data layer directly — so
  // the guard is on its source: the condition that decides whether a static deployment
  // announces itself must consult `source_backend` and not only `database.backend`, which is
  // `static` either way.
  const banner = await readFile(join(ROOT, 'src', 'components', 'DataSourceBanner.tsx'), 'utf8')
  check(
    'the data-source banner reads the export source',
    /source_backend\s*===\s*["']sqlite["']/.test(banner),
    'DataSourceBanner.tsx no longer treats an sqlite-sourced export as sample data',
  )

  const meta = await staticMod.serveStatic('GET', '/api/meta/reference', new URLSearchParams())
  check('four directions', meta?.directions?.length === 4, meta?.directions?.length)
  check('five routes', meta?.routes?.length === 5, meta?.routes?.length)
  check('nine tool definitions', meta?.tools?.length === 9, meta?.tools?.length)
  // The model proxy reads the route descriptions out of this bundle to describe the route in
  // force — its name, its barrier, the weights its profile uses. A bundle without those fields
  // would leave the deployed fact block thinner than the development one.
  check(
    'every route carries what the fact block describes it by',
    meta?.routes?.every(
      (r) => r.name && r.barrier_label && r.immune_exposure && r.screening?.cpp_weight,
    ),
    meta?.routes?.map((r) => r.id).join(','),
  )
}

console.log('\nthe fact block numbers are written the same way on both paths')
{
  const cases = JSON.parse(
    await readFile(join(ROOT, 'verify', 'number-format-cases.json'), 'utf8'),
  ).cases

  // The deployed formatter, loaded straight from the Pages Function. It imports nothing and has
  // no side effects at module scope, so Node's type stripping can run it as-is — which is the
  // only way to check its notation branches, since a source-level assertion cannot see which
  // branch a value takes. The other half of the comparison is
  // `service/tests/test_llm.py`, which runs Python's own formatter over this same table.
  const chat = await import(
    pathToFileURL(join(ROOT, 'functions', 'api', 'constructs', '[id]', 'chat.ts')).href
  )
  check(
    `the model proxy exports the formatter this check runs (${cases.length} cases)`,
    typeof chat.formatNumber === 'function',
  )
  const wrong = cases.filter((entry) => chat.formatNumber(entry.value) !== entry.expected)
  check(
    'every fact-block number matches the table the service is checked against',
    wrong.length === 0,
    wrong
      .map((entry) => `${entry.value} -> ${chat.formatNumber(entry.value)}, want ${entry.expected}`)
      .join('; '),
  )
  // The table is only a guard if it straddles the notation switch: `%g` writes exponential
  // notation below 1e-4 and at or above 1e6, JavaScript's defaults do not, and a table that
  // stayed in the fixed range would pass however badly the switch were written.
  check(
    'the table holds values in both notations',
    cases.some((entry) => entry.expected.includes('e')) &&
      cases.some((entry) => !entry.expected.includes('e')),
  )
}

console.log('\nconstruct list: filters, search, ordering, pagination')
{
  const staticMod = await loadAppModule('api/static.ts')
  const call = (q) => staticMod.serveStatic('GET', '/api/constructs', new URLSearchParams(q))

  const all = await call({ limit: '500' })
  check('every construct is listed', all.total >= 4, all.total)
  check(
    'rows carry what a card needs',
    all.items.every((r) => r.id && r.direction && typeof r.peptide_length === 'number'),
  )

  const single = await call({ direction: all.items[0].direction, limit: '500' })
  check(
    'a direction filter narrows the list',
    single.total <= all.total && single.items.every((r) => r.direction === single.items[0].direction),
    `${single.total} of ${all.total}`,
  )

  const seq = all.items[0].peptide_sequence
  const needle = seq.slice(1, 4)
  const found = await call({ search: needle, limit: '500' })
  check(
    'a sequence substring search finds its own row',
    found.total >= 1 && found.items.some((r) => r.peptide_sequence.includes(needle)),
    `${needle} matched ${found.total}`,
  )

  const miss = await call({ search: 'zzzznotapeptide', limit: '500' })
  check('a search with no match returns an empty page, not an error', miss.total === 0, miss.total)

  // The search covers four columns, three of which are provenance. A filter that only ever
  // looked at the sequence answered a provenance term with nothing — which is what the
  // deployment did until the exported row carried these fields, while the service answered the
  // same term with four rows.
  const provenance = String(all.items[0].peptide_source ?? '')
  const accession = String(all.items[0].peptide_source_accession ?? '')
  if (provenance) {
    const bySource = await call({ search: provenance, limit: '500' })
    check(
      'a provenance term finds the rows the service would find',
      bySource.total >= 1 &&
        bySource.items.every((r) => String(r.peptide_source ?? '').includes(provenance)),
      `${JSON.stringify(provenance)} matched ${bySource.total}`,
    )
  }
  if (accession) {
    const byAccession = await call({ search: accession, limit: '500' })
    check(
      'an accession term finds its own row',
      byAccession.total >= 1 &&
        byAccession.items.some((r) => String(r.peptide_source_accession ?? '') === accession),
      `${accession} matched ${byAccession.total}`,
    )
  }

  // A term spanning the seam between two columns has to match nothing: the service writes four
  // separate `LIKE`s and ORs them, so no term is ever a substring of two columns at once.
  if (provenance.length >= 2) {
    const seam = `${seq.slice(-2)} ${provenance.slice(0, 2)}`
    const crossed = await call({ search: seam, limit: '500' })
    check(
      'a term spanning the seam between two columns matches nothing',
      crossed.total === 0,
      `${JSON.stringify(seam)} matched ${crossed.total}`,
    )
  }

  // A column the row does not hold must not reach the filter as text. The previous
  // implementation joined the four columns into one string, so a missing one became the literal
  // word "undefined" and searching for that word returned every row.
  const undefinedTerm = await call({ search: 'undefined', limit: '500' })
  check(
    'a column the row does not hold is not searchable as the word "undefined"',
    undefinedTerm.total === 0,
    undefinedTerm.total,
  )

  // `%` and `_` are literal in the service (ESCAPE '\'), so they must be literal here too. If
  // they acted as wildcards this would return every row and the check would catch the
  // divergence between the two implementations.
  const wildcard = await call({ search: '%', limit: '500' })
  check(
    'a percent sign is matched literally, not as a wildcard',
    wildcard.total === 0 || wildcard.items.every((r) => r.peptide_sequence.includes('%')),
    wildcard.total,
  )

  const byLength = await call({ order: 'peptide_length', limit: '500' })
  const lengths = byLength.items.map((r) => r.peptide_length)
  check(
    'ordering by length is ascending',
    lengths.every((n, i) => i === 0 || lengths[i - 1] <= n),
    lengths.join(','),
  )

  const byRank = await call({ order: 'rank', limit: '500' })
  const ranks = byRank.items.filter((r) => r.rank !== null).map((r) => r.rank)
  check(
    'ordering by rank is ascending',
    ranks.every((n, i) => i === 0 || ranks[i - 1] <= n),
    ranks.join(','),
  )

  const page0 = await call({ limit: '1', offset: '0' })
  const page1 = await call({ limit: '1', offset: '1' })
  check('total is the match size, not the page size', page0.total === all.total, page0.total)
  check(
    'offset really moves through the list',
    all.total < 2 || page0.items[0].id !== page1.items[0].id,
  )
}

console.log('\nroute-dependent numbers')
{
  const staticMod = await loadAppModule('api/static.ts')
  const id = (await staticMod.serveStatic('GET', '/api/constructs', new URLSearchParams({ limit: '1' })))
    .items[0].id
  const detailDefault = await staticMod.serveStatic('GET', `/api/constructs/${id}`, new URLSearchParams())
  check('a detail carries its scores', detailDefault?.scores !== undefined)
  check(
    'a detail carries a composite for every route',
    Object.keys(detailDefault?.delivery_scores ?? {}).length >= 5,
    Object.keys(detailDefault?.delivery_scores ?? {}).join(','),
  )

  const detailRouted = await staticMod.serveStatic(
    'GET', `/api/constructs/${id}`, new URLSearchParams({ route_id: 'injectable-filler' }),
  )
  check(
    'a named route replaces the composite with that route s',
    detailRouted?.scores?.composite === detailRouted?.delivery_scores?.['injectable-filler']?.composite,
    `${detailRouted?.scores?.composite} vs ${detailRouted?.delivery_scores?.['injectable-filler']?.composite}`,
  )
  check('a named route reports its own safety verdict', typeof detailRouted?.safety_verdict === 'string')
  const reference = await staticMod.serveStatic('GET', '/api/meta/reference', new URLSearchParams())
  for (const route of reference.routes) {
    const shown = await staticMod.serveStatic('GET', `/api/constructs/${id}`, new URLSearchParams({ route_id: route.id }))
    const expected = detailDefault.route_contexts?.[route.id]
    check(`${route.id}: a complete service-authored context is exported`, Boolean(expected?.safety))
    check(`${route.id}: the entire safety table follows the selected route`,
      JSON.stringify(shown?.safety) === JSON.stringify(expected?.safety))
    check(`${route.id}: both composite fields follow the same context`,
      shown?.composite === expected?.composite && shown?.scores?.composite === expected?.composite)
    const gate = shown?.safety?.gates?.find((candidate) => candidate.key === 'immunogenicity')
    check(`${route.id}: immunogenicity threshold labels follow the selected safety gate`,
      shown?.safety?.route_id === route.id &&
      shown?.safety?.immunogenicity_threshold === route.screening.immunogenicity_threshold &&
      shown?.score_meta?.immunogenicity?.applied_threshold?.value === gate?.threshold &&
      shown?.score_meta?.immunogenicity?.applied_threshold?.source === gate?.threshold_source)
    const analysis = await staticMod.serveStatic('GET', `/api/constructs/${id}/analysis`, new URLSearchParams({ route_id: route.id }))
    check(`${route.id}: the prose names its actual route`, analysis?.route_id === route.id)
    const byRoute = JSON.parse(await readFile(join(DATA_DIR, `constructs/${id}/analysis_by_route.json`), 'utf8'))
    check(`${route.id}: all analysis prose comes from that route's export`,
      JSON.stringify(analysis) === JSON.stringify(byRoute[route.id]))
  }
}

console.log('\nold or incomplete snapshots cannot substitute a different route')
{
  const staticMod = await loadAppModule('api/static.ts')
  const source = JSON.parse(await readFile(join(DATA_DIR, 'constructs/con_0001.json'), 'utf8'))
  const old = structuredClone(source)
  old.id = 'con_90000001'
  delete old.route_contexts
  assetOverrides.set(`constructs/${old.id}.json`, old)
  assetOverrides.set(`constructs/${old.id}/analysis_by_route.json`, null)
  const defaultAnalysis = JSON.parse(await readFile(join(DATA_DIR, 'constructs/con_0001/analysis.json'), 'utf8'))
  assetOverrides.set(`constructs/${old.id}/analysis.json`, { ...defaultAnalysis, construct_id: old.id })
  const ownRoute = await staticMod.serveStaticResult('GET', `/api/constructs/${old.id}`, new URLSearchParams({ route_id: old.safety.route_id }))
  check('a legacy snapshot still supports its stored route', ownRoute.payload?.safety?.route_id === old.safety.route_id && !ownRoute.error)
  for (const suffix of ['', '/analysis']) {
    const result = await staticMod.serveStaticResult('GET', `/api/constructs/${old.id}${suffix}`, new URLSearchParams({ route_id: 'hair-coating' }))
    check(`legacy ${suffix || 'detail'}: a different route is explicitly unavailable`,
      result.covered && result.payload === null && result.error?.kind === 'data_unavailable')
  }
  const clientMod = await loadModuleWithTs('api/client.ts')
  const before = escaped.length
  let clientError
  try { await clientMod.request(`/api/constructs/${old.id}?route_id=hair-coating`) } catch (error) { clientError = error }
  check('the client distinguishes missing route context from database failure or not-found',
    clientError?.kind === 'data_unavailable' && clientError?.status === 503, clientError?.kind)
  check('an unavailable exported context never falls through to the network', escaped.length === before)

  const incomplete = structuredClone(source)
  incomplete.id = 'con_90000002'
  incomplete.route_contexts['hair-coating'].safety.gates = incomplete.route_contexts['hair-coating'].safety.gates.filter((gate) => gate.key !== 'toxicity')
  assetOverrides.set(`constructs/${incomplete.id}.json`, incomplete)
  const broken = await staticMod.serveStaticResult('GET', `/api/constructs/${incomplete.id}`, new URLSearchParams({ route_id: 'hair-coating' }))
  check('an incomplete authoritative gate table is explicitly unavailable', broken.error?.kind === 'data_unavailable')

  const nullComposite = structuredClone(source)
  nullComposite.id = 'con_90000003'
  nullComposite.route_contexts['hair-coating'].composite = null
  assetOverrides.set(`constructs/${nullComposite.id}.json`, nullComposite)
  const nullShown = await staticMod.serveStatic('GET', `/api/constructs/${nullComposite.id}`, new URLSearchParams({ route_id: 'hair-coating' }))
  check('an authoritative null composite stays null in both fields', nullShown?.composite === null && nullShown?.scores?.composite === null)
}

console.log('\nscaffolds, linkers, analysis')
{
  const staticMod = await loadAppModule('api/static.ts')
  const scaffolds = await staticMod.serveStatic('GET', '/api/scaffolds', new URLSearchParams())
  check('scaffolds are listed', Array.isArray(scaffolds) && scaffolds.length > 0, scaffolds?.length)

  const routed = await staticMod.serveStatic(
    'GET', '/api/scaffolds', new URLSearchParams({ route_id: 'topical-film' }),
  )
  check(
    'a route narrows the scaffold list',
    Array.isArray(routed) && routed.length <= scaffolds.length,
    `${routed?.length} of ${scaffolds.length}`,
  )

  const linkers = await staticMod.serveStatic('GET', '/api/linkers', new URLSearchParams())
  check('the curated linker library is listed', Array.isArray(linkers) && linkers.length > 0, linkers?.length)
  check(
    'every linker carries its rigidity band',
    linkers.every((l) => typeof l.rigidity === 'string' && l.rigidity.length > 0),
  )
  // The order this list arrives in is the order the Builder displays and the order its standing
  // choice is taken from, so a list in query order was a statement nobody had made. It is now
  // the recommendation, and the position and its reason travel with each entry.
  check(
    'the library is served in recommendation order, 1 first with no gaps',
    linkers.every((l, i) => l.priority_rank === i + 1),
    linkers.map((l) => l.priority_rank).join(','),
  )
  check(
    'every ranked entry states why it sits where it does',
    linkers.every((l) => (l.priority_reason ?? '').length > 40),
  )

  const id = (await staticMod.serveStatic('GET', '/api/constructs', new URLSearchParams({ limit: '1' })))
    .items[0].id
  const analysis = await staticMod.serveStatic(
    'GET', `/api/constructs/${id}/analysis`, new URLSearchParams({ route_id: 'topical-film' }),
  )
  check('analysis prose is exported', Array.isArray(analysis?.blocks) && analysis.blocks.length > 0)
  check('every block carries its citations', analysis?.blocks?.every((b) => Array.isArray(b.citations)))
}

console.log('\nthe Builder ranking')
{
  const staticMod = await loadAppModule('api/static.ts')
  const all = await staticMod.serveStatic(
    'GET', '/api/build', new URLSearchParams({ direction: 'antioxidant', route_id: 'topical-film' }),
  )
  check('a ranking is exported per route and direction', Array.isArray(all?.items) && all.items.length > 0)
  check('the ranking reports its counts', typeof all?.counts?.ranked === 'number')
  check(
    'counts describe the whole candidate set, not the page',
    all.counts.ranked === all.total,
    `${all.counts.ranked} vs ${all.total}`,
  )
  check('the ranking states its route', all?.route?.id === 'topical-film')
  check(
    'the ranking states what the scores do not cover',
    typeof all?.scope_note === 'string' && all.scope_note.length > 0,
  )

  const combined = await staticMod.serveStatic(
    'GET', '/api/build',
    new URLSearchParams({ direction: 'antioxidant,antibacterial', route_id: 'topical-film' }),
  )
  check('several directions rank together', Array.isArray(combined?.items) && combined.items.length > 0)
  check(
    'the combined ranking names the set it was asked for',
    Array.isArray(combined?.directions) &&
      combined.directions.length === 2 &&
      ['antioxidant', 'antibacterial'].every((d) => combined.directions.includes(d)),
    combined?.directions?.join(','),
  )

  const ranked = combined.items.map((r) => r.composite).filter((c) => c !== null && c !== undefined)
  check(
    'the ranking is descending by composite',
    ranked.every((c, i) => i === 0 || ranked[i - 1] >= c),
    ranked.slice(0, 5).join(','),
  )

  // A subset must be ranked as a subset. A two-direction request answered from the
  // four-direction ranking would still look right — non-empty, still descending — so the
  // demonstration has to be a set whose candidate count differs from the full set's. The
  // comparison is against the full set rather than against a fixed number: the counts belong
  // to whichever export is on disk, and a check that hardcoded them would be testing the
  // dataset rather than the ranking.
  const everything = await staticMod.serveStatic(
    'GET', '/api/build',
    new URLSearchParams({
      direction: 'antioxidant,antibacterial,anti_inflammatory,antimelanin',
      route_id: 'topical-film',
    }),
  )
  const subset = await staticMod.serveStatic(
    'GET', '/api/build',
    new URLSearchParams({ direction: 'antioxidant,anti_inflammatory', route_id: 'topical-film' }),
  )
  check(
    'a direction subset is ranked as a subset, not as the whole set',
    typeof subset?.total === 'number' && subset.total > 0 &&
      subset.total !== everything.total,
    `total ${subset?.total} against the full set's ${everything.total}`,
  )
  check(
    'the subset ranking holds only the selected directions',
    Array.isArray(subset?.items) &&
      subset.items.every((r) => ['antioxidant', 'anti_inflammatory'].includes(r.direction)),
    [...new Set(subset?.items?.map((r) => r.direction) ?? [])].join(','),
  )
  check(
    'the subset ranking is the same set in either order',
    (
      await staticMod.serveStatic(
        'GET', '/api/build',
        new URLSearchParams({ direction: 'anti_inflammatory,antioxidant', route_id: 'topical-film' }),
      )
    )?.total === subset?.total,
  )

  const paged = await staticMod.serveStatic(
    'GET', '/api/build',
    new URLSearchParams({ direction: 'antioxidant', route_id: 'topical-film', limit: '1', offset: '0' }),
  )
  check('the ranking slices rather than re-sorting', paged.items.length <= 1 && paged.total === all.total)
  check(
    'a page of the ranking is the head of the whole ranking',
    paged.items[0]?.id === all.items[0]?.id,
  )
}

console.log('\nassembly: the one thing the static layer computes')
{
  const staticMod = await loadAppModule('api/static.ts')
  const manifest = JSON.parse(await (await realFetch(`http://127.0.0.1:${PORT}/manifest.json`)).text())
  check('assembly.json is in the export', 'assembly.json' in manifest.files)

  const assembly = JSON.parse(await (await realFetch(`http://127.0.0.1:${PORT}/assembly.json`)).text())
  const route = assembly.routes['topical-film']
  check(
    'the route admits at least one scaffold and one linker',
    route.scaffolds.length > 0 && route.linkers.length > 0,
  )
  check(
    'the worked example pairs parts the route admits',
    route.scaffolds.includes(route.example.scaffold_id) &&
      route.linkers.includes(route.example.linker_id),
  )

  // The decisive assertion: the interface's own concatenation, compared residue by residue
  // against the sequence the service itself produced.
  const sample = route.example.items[0]
  const scaffoldFile = JSON.parse(
    await (await realFetch(
      `http://127.0.0.1:${PORT}/scaffolds/${encodeURIComponent(route.example.scaffold_id)}.json`,
    )).text(),
  )
  const linkerFile = JSON.parse(
    await (await realFetch(
      `http://127.0.0.1:${PORT}/linkers/${encodeURIComponent(route.example.linker_id)}.json`,
    )).text(),
  )
  const constructFile = JSON.parse(
    await (await realFetch(`http://127.0.0.1:${PORT}/constructs/${sample.id}.json`)).text(),
  )
  const backbone = scaffoldFile.sequences
    .map((s) => s.sequence)
    .filter(Boolean)
    .sort((a, b) => b.length - a.length)[0]
  const rebuilt = `${backbone}${linkerFile.sequence}${constructFile.peptide_sequence}`
  check(
    'the static concatenation matches the service residue for residue',
    rebuilt === sample.full_sequence,
    `${rebuilt.slice(0, 40)} vs ${String(sample.full_sequence).slice(0, 40)}`,
  )
  check('the fused length is the length of the concatenation', rebuilt.length === sample.fused_length)

  // And through the public entry point, the way a page reaches it.
  const detail = await staticMod.serveStatic('GET', `/api/constructs/${sample.id}`, new URLSearchParams())
  const applied = await staticMod.applyAssemblyTargets(
    detail, route.example.scaffold_id, route.example.linker_id,
  )
  check('a named scaffold is reported as inferred, never as a pipeline result',
    applied.backbone_binding === 'inferred')
  check('the assembled detail carries the fused sequence', applied.full_sequence === rebuilt)
  // The names, not the identifiers. The service resolves a request-time scaffold to its short
  // name and a linker to its name; the pages print `backbone_name` into a heading, so an
  // assembly that put the id there showed a reader `fixture-silk-s1` where the development
  // build shows `Fixture S1`.
  check(
    'the assembled detail names the scaffold the way the service does',
    applied.backbone_name === scaffoldFile.short_name,
    `${applied.backbone_name} vs ${scaffoldFile.short_name}`,
  )
  check(
    'the backbone segment is labelled with that name too',
    applied.segments?.[0]?.label === `Backbone: ${scaffoldFile.short_name}`,
    applied.segments?.[0]?.label,
  )
  check(
    'the assembled detail names the linker the way the service does',
    applied.linker_name === linkerFile.name,
    `${applied.linker_name} vs ${linkerFile.name}`,
  )
  check('the segments name all three parts', applied.segments?.length === 3)
  check(
    'the segments carry real sequences, not placeholders',
    applied.segments?.every((s) => s.available && s.sequence.length > 0),
  )
  check(
    'a detail with no pairing keeps the stored placeholder and emits no sequence',
    detail.full_sequence === null && detail.backbone_binding === 'placeholder',
    `${detail.full_sequence} / ${detail.backbone_binding}`,
  )

  // The same request as the page actually makes, with the pairing in the query string. The
  // assembly happens inside the static layer's own detail handler, so a response that came
  // from the service — which assembles it itself — is never overwritten by a file.
  const paired = await staticMod.serveStatic(
    'GET', `/api/constructs/${sample.id}`,
    new URLSearchParams({ scaffold_id: route.example.scaffold_id, linker_id: route.example.linker_id }),
  )
  check(
    'a pairing in the query string is assembled by the static layer itself',
    paired?.full_sequence === rebuilt,
    `${String(paired?.full_sequence).slice(0, 30)} vs ${rebuilt.slice(0, 30)}`,
  )
  check('the assembled detail keeps its own route composite', typeof paired?.composite === 'number')

  // A detail page can be opened as `?scaffold_id=…` with no linker — the page's own preview
  // selector sets the scaffold alone and deletes the linker. When the request names no linker
  // the service uses the one the construct's own row records, and the linker's residues sit in
  // the middle of the sequence, so omitting it would emit a fusion shorter than the service's
  // and show two different sequences for the same URL.
  const scaffoldOnly = await staticMod.serveStatic(
    'GET', `/api/constructs/${sample.id}`,
    new URLSearchParams({ scaffold_id: route.example.scaffold_id }),
  )
  const storedLinker = constructFile.linker?.sequence ?? ''
  check(
    'a scaffold named without a linker keeps the stored linker, as the service does',
    scaffoldOnly?.full_sequence === `${backbone}${storedLinker}${constructFile.peptide_sequence}`,
    `${String(scaffoldOnly?.full_sequence).slice(0, 24)}… (${String(scaffoldOnly?.full_sequence).length} aa vs ${backbone.length + storedLinker.length + constructFile.peptide_sequence.length})`,
  )
  check(
    'and reports the stored linker rather than calling it unavailable',
    scaffoldOnly?.linker_name === (constructFile.linker?.name ?? null),
    `${scaffoldOnly?.linker_name} vs ${constructFile.linker?.name}`,
  )

  // The two objects the pages read instead of the names. A construct response carries the
  // `scaffold` summary and the `linker` view themselves: the heading prints
  // `scaffold.short_name`, the summary card prints it again and takes the linker's name from
  // `linker.name`, the eligible-scaffold list highlights the entry whose id matches, and the
  // linker tab is rendered from `linker` alone. Emitting only the names left every one of them
  // reading a null, so the page showed `scaffold unassigned` and the stored linker directly
  // above a fused sequence it had just assembled from the scaffold the reader picked.
  check(
    'the assembled detail carries the scaffold summary the pages print',
    applied.scaffold?.short_name === scaffoldFile.short_name,
    `${applied.scaffold?.short_name} vs ${scaffoldFile.short_name}`,
  )
  check(
    'and the id the eligible-scaffold list matches on',
    applied.scaffold?.id === route.example.scaffold_id,
    applied.scaffold?.id,
  )
  check(
    'the assembled detail carries the linker view, not only its name',
    applied.linker?.name === linkerFile.name && applied.linker?.length === linkerFile.length,
    `${applied.linker?.name} / ${applied.linker?.length}`,
  )
  check(
    'the embedded linker says which table it came from',
    typeof applied.linker?.source_table === 'string' && applied.linker.source_table.length > 0,
    applied.linker?.source_table,
  )
  check(
    "a scaffold named without a linker embeds the construct's stored linker",
    scaffoldOnly?.linker?.id === String(constructFile.linker?.id ?? ''),
    `${scaffoldOnly?.linker?.id} vs ${constructFile.linker?.id}`,
  )

  // The other direction of the same pairing: a linker named with no scaffold. It changes no
  // sequence — there is no scaffold to build on — but the response still has to report which
  // linker the build was pointed at, or the page would fall back to the stored one and name a
  // linker the reader did not choose.
  const linkerOnly = await staticMod.applyAssemblyTargets(detail, null, route.example.linker_id)
  check(
    'a linker named without a scaffold is still reported',
    linkerOnly?.linker?.name === linkerFile.name,
    `${linkerOnly?.linker?.name} vs ${linkerFile.name}`,
  )
  check(
    'and no fused sequence is invented for it',
    linkerOnly?.full_sequence === null,
    String(linkerOnly?.full_sequence),
  )

  // The Builder's own path, which is the one a reader actually takes.
  const built = await staticMod.serveStatic(
    'GET', '/api/build',
    new URLSearchParams({
      direction: 'antioxidant',
      route_id: 'topical-film',
      scaffold_id: route.example.scaffold_id,
      linker_id: route.example.linker_id,
      limit: '20',
    }),
  )
  const assembledItem = built.items.find((r) => r.id === sample.id)
  check('the Builder assembles the candidate it ranks', assembledItem?.full_sequence === rebuilt,
    `${String(assembledItem?.full_sequence).slice(0, 30)} vs ${rebuilt.slice(0, 30)}`)
  check('the Builder reports the fused length', assembledItem?.fused_length === rebuilt.length)
  check('the Builder marks the pairing as inferred', assembledItem?.backbone_binding === 'inferred')
  check(
    'the Builder names the scaffold the way the service does',
    assembledItem?.backbone_name === scaffoldFile.short_name,
    `${assembledItem?.backbone_name} vs ${scaffoldFile.short_name}`,
  )
  check('the Builder still counts the whole candidate set', built.counts.ranked === all_total(built))
}

function all_total(built) {
  // The exported ranking reports `total` for the direction set the file holds; for a
  // single-direction request that is the file's own item count before slicing.
  return built.total
}

console.log('\nthe static layer must not swallow what it cannot serve')
{
  const staticMod = await loadAppModule('api/static.ts')
  const chat = await staticMod.serveStatic(
    'POST', '/api/constructs/con_0001/chat', new URLSearchParams(),
  )
  check('chat is never served statically', chat === null)
  check('answering the check above did not reach the network', escaped.length === 0, escaped.join(', '))

  // A POST must fall through to the network, because only the model proxy can answer it.
  const before = escaped.length
  const clientMod = await loadModuleWithTs('api/client.ts')
  let threw = null
  try {
    await clientMod.postJson('/api/constructs/con_0001/chat', { message: 'why is this one vetoed' })
  } catch (error) {
    threw = error
  }
  check(
    'a chat POST falls through to the network rather than being answered from a file',
    threw !== null && escaped.length === before + 1,
    `escaped ${escaped.slice(before).join(', ')}`,
  )
}

console.log('\na record the export does not hold is a not-found, not a fall-through')
{
  const staticMod = await loadAppModule('api/static.ts')

  // Three answers, and the two empty ones are acted on differently. "Not covered" falls through
  // to the service. "Covered and empty" is a record that is not in the snapshot: falling
  // through would send it to a service a static deployment does not have, and on Pages the
  // request reaches the SPA fallback, comes back as HTML, and is reported to the reader as a
  // malformed response instead of as a missing record.
  const missing = await staticMod.serveStaticResult(
    'GET', '/api/constructs/con_999999', new URLSearchParams(),
  )
  check(
    'an id the export does not hold is covered but empty',
    missing.covered === true && missing.payload === null,
    `covered=${missing.covered} payload=${missing.payload}`,
  )
  const unhandled = await staticMod.serveStaticResult(
    'GET', '/api/not-an-endpoint', new URLSearchParams(),
  )
  check(
    'a path the export does not answer is not covered',
    unhandled.covered === false,
    `covered=${unhandled.covered}`,
  )
  const present = await staticMod.serveStaticResult('GET', '/api/health', new URLSearchParams())
  check(
    'a path the export answers returns its payload',
    present.covered === true && present.payload !== null,
  )

  // And the client acts on it, which is the whole point of the distinction: the request must
  // not leave for the network.
  const before = escaped.length
  const clientMod = await loadModuleWithTs('api/client.ts')
  let threw = null
  try {
    await clientMod.request('/api/constructs/con_999999')
  } catch (error) {
    threw = error
  }
  check(
    'a missing construct is reported as not found',
    threw?.kind === 'not_found',
    `${threw?.kind}: ${threw?.message}`,
  )
  check(
    'and the reader is not sent to a service that is not there',
    escaped.length === before,
    `escaped ${escaped.slice(before).join(', ')}`,
  )

  // The other direction: a path the export does not answer still reaches the network, which is
  // what keeps a deployment with an API working off the API.
  const beforeUnhandled = escaped.length
  let fellThrough = null
  try {
    await clientMod.request('/api/not-an-endpoint')
  } catch (error) {
    fellThrough = error
  }
  check(
    'a path the export does not answer still reaches the network',
    fellThrough !== null && escaped.length === beforeUnhandled + 1,
    `${fellThrough?.kind} / escaped ${escaped.slice(beforeUnhandled).join(', ')}`,
  )
}

console.log('\nthe endpoint bindings all resolve')
{
  // Every export in `api/index.ts` must be answerable from the export, because a page that
  // calls one and gets nothing degrades to an error state. This walks the list rather than
  // trusting that the paths look right.
  const staticMod = await loadAppModule('api/static.ts')
  const id = (await staticMod.serveStatic('GET', '/api/constructs', new URLSearchParams({ limit: '1' })))
    .items[0].id
  const scaffoldId = (await staticMod.serveStatic('GET', '/api/scaffolds', new URLSearchParams()))[0].id
  const linkerId = (await staticMod.serveStatic('GET', '/api/linkers', new URLSearchParams()))[0].id

  const probes = [
    ['/api/health', {}],
    ['/api/meta/reference', {}],
    ['/api/meta/directions', {}],
    ['/api/meta/routes', {}],
    ['/api/meta/tools', {}],
    ['/api/meta/pipeline', {}],
    ['/api/meta/coverage', {}],
    ['/api/scaffolds', {}],
    [`/api/scaffolds/${scaffoldId}`, {}],
    ['/api/linkers', {}],
    [`/api/linkers/${linkerId}`, {}],
    ['/api/constructs', {}],
    [`/api/constructs/${id}`, {}],
    [`/api/constructs/${id}/scaffolds`, {}],
    [`/api/constructs/${id}/analysis`, { route_id: 'topical-film' }],
    ['/api/build', { direction: 'antioxidant', route_id: 'topical-film' }],
  ]
  const unresolved = []
  for (const [path, query] of probes) {
    const payload = await staticMod.serveStatic('GET', path, new URLSearchParams(query))
    if (payload === null || payload === undefined) unresolved.push(path)
  }
  check('every GET the interface makes is answerable from the export', unresolved.length === 0,
    unresolved.join(', '))
}

staticServer.close()
console.log(`\n${failures === 0 ? 'all checks passed' : `${failures} check(s) failed`}`)
process.exit(failures === 0 ? 0 : 1)
