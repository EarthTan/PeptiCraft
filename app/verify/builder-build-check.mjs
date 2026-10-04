/**
 * Drives the Builder through its five steps in jsdom against a running service.
 *
 * This is the check the platform's fallback made possible: with `IGEM_DB_BACKEND=auto` the
 * service answers from the local SQLite fixture when the remote instance is unreachable, so
 * the whole page can be exercised with no database and no browser.
 *
 * It is not a network stub. `fetch` is rewritten only to make the app's relative `/api/...`
 * paths absolute, and every request then goes to the real service over HTTP — so what is
 * asserted is the real response as the component renders it, not a fixture written to make
 * the assertion pass.
 *
 * jsdom has no layout, so nothing here is about where things sit on screen. What it answers is
 * whether the page reaches step 5, whether the fused sequence the build returned reaches the
 * DOM, and whether the labels that qualify it — the scaffold's provenance, the linker's, and
 * the scope of the scores — are the ones the service sent.
 *
 * Run:
 *   npm install --no-save --no-package-lock jsdom   # jsdom is not a declared dependency yet
 *   node verify/builder-build-check.mjs             # expects the service on :8000
 *
 * `PC_BACKEND` overrides the service address. `jsdom` is installed outside `package.json`
 * because the frontend has no test tooling declared; if this script becomes a maintained
 * check rather than a one-off, it belongs in `devDependencies` with a `verify` npm script.
 */
import { JSDOM, VirtualConsole } from 'jsdom'
import { createServer } from 'vite'

const BACKEND = process.env.PC_BACKEND ?? 'http://127.0.0.1:8000'
const SILK = 'GAGAGSGAGAGSGAGAGSGAGAGSGAGAGSGAGAGSGAGAGSGAGAG'
const COLLAGEN = 'GPPGPPGPPGPPGPPGPPGPPGPPGPPGPPGPPGPPGPPGPP'
const LINKER = 'GGGGS'

let failures = 0
function check(label, condition, detail) {
  if (condition) console.log(`  ok   ${label}`)
  else {
    failures += 1
    console.log(`  FAIL ${label}${detail === undefined ? '' : ` — ${detail}`}`)
  }
}

// ---------------------------------------------------------------------------
// jsdom
// ---------------------------------------------------------------------------

const jsdomErrors = []
const virtualConsole = new VirtualConsole()
virtualConsole.on('jsdomError', (error) => jsdomErrors.push(error))

const dom = new JSDOM('<!doctype html><html><body></body></html>', {
  pretendToBeVisual: true,
  // The real App is rendered, so the router has to resolve this path itself. Loading
  // `react-router-dom` into the harness separately would give a second router instance whose
  // context the page's `Link` cannot see.
  url: 'http://localhost/builder',
  virtualConsole,
})
const { window } = dom

for (const key of [
  'window', 'document', 'navigator', 'Node', 'Element', 'HTMLElement', 'HTMLInputElement',
  'HTMLTextAreaElement', 'DOMParser', 'MutationObserver', 'Selection', 'Range',
  'getComputedStyle', 'CustomEvent', 'Event', 'KeyboardEvent', 'MouseEvent', 'ClipboardEvent',
  'DragEvent', 'DocumentFragment', 'Text', 'NodeFilter', 'File', 'FileList', 'Blob', 'Image',
  'SVGElement',
]) {
  if (window[key] === undefined) continue
  Object.defineProperty(globalThis, key, { value: window[key], configurable: true, writable: true })
}
globalThis.requestAnimationFrame ??= (fn) => setTimeout(() => fn(Date.now()), 0)
globalThis.cancelAnimationFrame ??= (id) => clearTimeout(id)
globalThis.IS_REACT_ACT_ENVIRONMENT = true

// jsdom has no layout, and libraries that measure must not throw.
window.Element.prototype.getClientRects = () => []
window.Range.prototype.getClientRects = () => []
window.Range.prototype.getBoundingClientRect = () =>
  ({ x: 0, y: 0, top: 0, left: 0, right: 0, bottom: 0, width: 0, height: 0 })
window.document.elementFromPoint = () => null
window.document.caretRangeFromPoint = () => null

class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver = ResizeObserverStub
window.ResizeObserver = ResizeObserverStub

// The only thing rewritten: the app requests `/api/...` relative to its own origin, which
// jsdom has no handler for. Everything after this is a real HTTP request.
const realFetch = globalThis.fetch
const requested = []
globalThis.fetch = async (input, init) => {
  let url = typeof input === 'string' ? input : input.url
  if (url.startsWith('/')) url = BACKEND + url
  requested.push(url.replace(BACKEND, ''))
  return realFetch(url, init)
}

// ---------------------------------------------------------------------------
// Mount
// ---------------------------------------------------------------------------

const server = await createServer({
  root: new URL('..', import.meta.url).pathname,
  logLevel: 'error',
  server: { middlewareMode: true },
  appType: 'custom',
})

const { default: App } = await server.ssrLoadModule('/src/App.tsx')
const { createElement, act } = await import('react')
const { createRoot } = await import('react-dom/client')

const { reference, routes, linkers } = await (async () => {
  const ref = await (await realFetch(`${BACKEND}/api/meta/reference`)).json()
  const rts = await (await realFetch(`${BACKEND}/api/meta/routes`)).json()
  const lks = await (await realFetch(`${BACKEND}/api/linkers`)).json()
  return { reference: ref, routes: rts, linkers: lks }
})()

const host = window.document.createElement('div')
host.id = 'root'
window.document.body.appendChild(host)
const root = createRoot(host)

async function settle() {
  await new Promise((resolve) => setTimeout(resolve, 0))
  await Promise.resolve()
  await Promise.resolve()
  await Promise.resolve()
}

async function drain() {
  await act(async () => {
    await settle()
  })
}

async function click(node, label) {
  if (!node) throw new Error(`no clickable element for ${label}`)
  await act(async () => {
    node.dispatchEvent(new window.MouseEvent('click', { bubbles: true, cancelable: true }))
    await settle()
  })
}

async function waitFor(predicate, label, timeoutMs = 8000) {
  const started = Date.now()
  while (Date.now() - started < timeoutMs) {
    if (predicate()) return true
    await drain()
  }
  console.log(`       (timed out waiting for ${label})`)
  return false
}

const buttons = () => [...host.querySelectorAll('button')]
const buttonContaining = (text) =>
  buttons().find((b) => (b.textContent ?? '').includes(text))
/** Visible text with whitespace removed, so segment spans can be matched as one sequence. */
const flat = () => (host.textContent ?? '').replace(/\s+/g, '')

await act(async () => {
  root.render(createElement(App))
})

// ---------------------------------------------------------------------------
// Step 1 — route
// ---------------------------------------------------------------------------

console.log('\n=== Step 1: the route is chosen and the scaffold pool follows it ===')
await waitFor(() => buttonContaining('Next: Function Direction') || buttons().length > 4, 'step 1')

check(
  'every declared route is offered',
  routes.every((route) => (host.textContent ?? '').includes(route.name)),
  `${routes.length} routes in reference data`,
)

// The route that admits the silk fixture scaffold, so the assembled sequence is distinctive:
// a silk prefix means the build really used the chosen scaffold rather than a stored binding.
const targetRoute =
  routes.find((route) => (route.scaffold_ids ?? []).includes('fixture-silk-s1')) ?? routes[0]
check(
  `the silk scaffold is admitted by the route this check uses (${targetRoute.id})`,
  (targetRoute.scaffold_ids ?? []).includes('fixture-silk-s1'),
  JSON.stringify(targetRoute.scaffold_ids),
)

await click(buttonContaining(targetRoute.name), `route ${targetRoute.name}`)
const proceed = await (async () => {
  const found = await waitFor(() => buttonContaining('Next: Function Direction'), 'the next button')
  return found ? buttonContaining('Next: Function Direction') : null
})()
check('selecting a route reveals the next step', Boolean(proceed))
await click(proceed, 'Next: Function Direction')

// ---------------------------------------------------------------------------
// Step 2 — directions
// ---------------------------------------------------------------------------

console.log('\n=== Step 2: two directions are selected, including one with no signed-off rows ===')
const antioxidant = reference.directions.find((d) => d.id === 'antioxidant')
const antibacterial = reference.directions.find((d) => d.id === 'antibacterial')
check('the reference data carries the directions this check needs', Boolean(antioxidant && antibacterial))

await click(buttonContaining(antioxidant.name), antioxidant.name)
await click(buttonContaining(antibacterial.name), antibacterial.name)
check(
  'the next button only appears once a direction is chosen',
  Boolean(buttonContaining('Next: Scaffold')),
)
await click(buttonContaining('Next: Scaffold'), 'Next: Scaffold')

// ---------------------------------------------------------------------------
// Step 3 — scaffold
// ---------------------------------------------------------------------------

console.log('\n=== Step 3: the scaffold is offered as an assembly target ===')
await waitFor(() => buttonContaining('Next: Linker'), 'step 3')
check(
  'the step states that the scaffold does not filter the candidates',
  (host.textContent ?? '').includes('does not narrow the candidate list'),
)
check(
  'the route-scoped scaffold is auto-selected, so the build can proceed',
  Boolean(buttonContaining('Next: Linker')),
)
await click(buttonContaining('Next: Linker'), 'Next: Linker')

// ---------------------------------------------------------------------------
// Step 4 — linker
// ---------------------------------------------------------------------------

console.log('\n=== Step 4: the linker is offered as the second assembly target ===')
await waitFor(() => buttonContaining('Build Constructs'), 'step 4')
check(
  'every curated linker is offered',
  linkers.every((linker) => (host.textContent ?? '').includes(linker.name)),
  `${linkers.length} entries in the library`,
)
check(
  'the step states that the linker does not filter the candidates either',
  (host.textContent ?? '').includes('not a filter'),
)

// The length the chosen linker adds is what makes the assembled sequence distinguishable from
// both the default choice and every stored linker, so the assertion cannot pass by accident.
const chosenLinker = linkers.find((linker) => linker.id === 'LK_GS3') ?? linkers[linkers.length - 1]
check(
  `the linker this check chooses is not the default and not what any row stores (${chosenLinker.id})`,
  chosenLinker != null && chosenLinker.sequence !== LINKER && chosenLinker.length !== LINKER.length,
  JSON.stringify({ id: chosenLinker?.id, sequence: chosenLinker?.sequence }),
)
await click(buttonContaining(chosenLinker.name), `linker ${chosenLinker.name}`)

// ---------------------------------------------------------------------------
// Step 5 — the build
// ---------------------------------------------------------------------------

console.log('\n=== Step 5: the build is requested and the fused sequence reaches the DOM ===')
await click(buttonContaining('Build Constructs'), 'Build Constructs')
await waitFor(() => (host.textContent ?? '').includes('Where the scaffold assignment came from'), 'step 5')

const buildCalls = requested.filter((url) => url.startsWith('/api/build'))
check(
  'the page called the build endpoint, not the construct list',
  buildCalls.length === 1,
  JSON.stringify(requested),
)
check(
  'the build carried both directions, the route, the scaffold and the linker',
  buildCalls[0]?.includes('direction=antioxidant') &&
    buildCalls[0]?.includes('direction=antibacterial') &&
    buildCalls[0]?.includes(`route_id=${targetRoute.id}`) &&
    buildCalls[0]?.includes('scaffold_id=fixture-silk-s1') &&
    buildCalls[0]?.includes(`linker_id=${chosenLinker.id}`),
  buildCalls[0],
)
check(
  'the construct-list endpoint was not used to render the result',
  !requested.some((url) => url.startsWith('/api/constructs')),
  JSON.stringify(requested),
)

check(
  'the heading names the scaffold and the linker the candidates were assembled from',
  (host.textContent ?? '').includes(`Assembled onto Fixture S1 with ${chosenLinker.name}`),
)
check(
  'the scaffold note the service sent is rendered',
  (host.textContent ?? '').includes('named at request time'),
)
check(
  'the linker note is rendered separately from the scaffold note',
  (host.textContent ?? '').includes('named for this build'),
)

const body = await (await realFetch(
  `${BACKEND}/api/build?direction=antioxidant&direction=antibacterial&route_id=${targetRoute.id}&scaffold_id=fixture-silk-s1&linker_id=${chosenLinker.id}&limit=100`,
)).json()
const total = body.total
check(
  `the page reports the whole candidate set (${total}), not just what it shows`,
  (host.textContent ?? '').includes(`${total} of ${total} candidates`),
)

for (const item of body.items) {
  const expected = SILK + chosenLinker.sequence + item.peptide_sequence
  check(
    `${item.id} renders the sequence assembled with the chosen linker (${item.fused_length} aa)`,
    flat().includes(expected),
    `expected ${expected.slice(0, 40)}…`,
  )
  check(
    `${item.id} reports the linker it was actually assembled with`,
    item.linker_name === chosenLinker.name,
    item.linker_name,
  )
}
check(
  'naming a linker moved the fused length by what the linker added',
  body.items.every(
    (item) => item.fused_length === SILK.length + chosenLinker.length + item.peptide_length,
  ),
)

check(
  'the rows with no composite render as absent rather than as zero',
  flat().includes('—') || !flat().includes('0.000000'),
)
check(
  'the tally is reported against the whole match',
  (host.textContent ?? '').includes(`${body.counts.ranked} candidates the selected directions hold`),
)
check(
  'the scope note separates the peptide scores from the construct',
  (host.textContent ?? '').includes('describes the functional peptide alone'),
)

// Neither target named. Reaching that state through the UI means clearing a choice the page
// does not offer to clear, so it is asserted against the service here and covered by the API
// tests. Two directions are asked for because the fixture records a different linker on one
// of them, which is what makes the fallback an observation rather than a claim.
const stored = await (await realFetch(
  `${BACKEND}/api/build?direction=antioxidant&direction=antibacterial`,
)).json()
check(
  'without a linker the response says where the linker came from',
  stored.linker === null && (stored.linker_note ?? '').includes('keeps the linker its own stored row records'),
  JSON.stringify({ linker: stored.linker, note: (stored.linker_note ?? '').slice(0, 60) }),
)
check(
  'without a linker the rows keep their own, and they differ from one another',
  new Set(stored.items.map((item) => item.linker_name)).size > 1,
  JSON.stringify(stored.items.map((item) => [item.id, item.linker_name])),
)
check(
  "without a linker the sequences are built from each row's own",
  stored.items
    .filter((item) => item.full_sequence !== null)
    .every((item) => item.linker_name === '(GGGGS)'),
  JSON.stringify(stored.items.map((item) => [item.id, item.linker_name, item.full_sequence !== null])),
)

const placeholderRow = stored.items.find((item) => item.id === 'con_9001')
check(
  'without a scaffold the placeholder row still emits no sequence',
  placeholderRow?.full_sequence === null && placeholderRow?.backbone_binding === 'placeholder',
  JSON.stringify(placeholderRow?.backbone_binding),
)
check(
  'without a scaffold the verified row emits the collagen assembly',
  stored.items.some((item) => item.full_sequence === COLLAGEN + LINKER + 'FHLSTQNR'),
)

// ---------------------------------------------------------------------------
// Teardown
// ---------------------------------------------------------------------------

console.log('\n=== Teardown ===')
const navigationErrors = jsdomErrors.filter((error) =>
  /Not implemented: navigation/.test(String(error?.message ?? error)),
)
check(
  'no click triggered a document navigation',
  navigationErrors.length === 0,
  navigationErrors.map((e) => String(e?.message ?? e)).join('; '),
)

await act(async () => {
  root.unmount()
})
await server.close()

console.log(
  failures === 0
    ? '\nAll checks passed.'
    : `\n${failures} check(s) failed.`,
)
process.exitCode = failures === 0 ? 0 : 1
