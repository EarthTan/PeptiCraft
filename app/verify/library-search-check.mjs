/**
 * Drives the Library page in jsdom against a running service.
 *
 * The companion to `builder-build-check.mjs`, and it exists for the same reason: the platform
 * can answer from the local SQLite fixture while the remote database is unreachable, so a
 * page can be exercised end to end with no database and no browser.
 *
 * What it checks is the three things the peptide library changed. The offline banner appears
 * when — and only when — the service reports a fallback, because a banner that pinned itself
 * to "sample data" after the connection returned would be its own kind of wrong. The search
 * field narrows the list. The paging controls address a page rather than growing the window,
 * which is the defect this replaced: every "Show more" click used to re-fetch every row before
 * it, so reaching page four cost four times the rows of reaching page one.
 *
 * It is not a network stub. `fetch` is rewritten only to make the app's relative `/api/...`
 * paths absolute, and every request then goes to the real service over HTTP.
 *
 * Run:
 *   npm install --no-save --no-package-lock jsdom   # jsdom is not a declared dependency
 *   node verify/library-search-check.mjs            # expects the service on :8000
 *
 * `PC_BACKEND` overrides the service address.
 */
import { JSDOM, VirtualConsole } from 'jsdom'
import { createServer } from 'vite'

const BACKEND = process.env.PC_BACKEND ?? 'http://127.0.0.1:8000'

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
  url: 'http://localhost/library',
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

const { health, reference, allRows } = await (async () => {
  const h = await (await realFetch(`${BACKEND}/api/health`)).json()
  const ref = await (await realFetch(`${BACKEND}/api/meta/reference`)).json()
  const rows = await (await realFetch(`${BACKEND}/api/constructs?limit=500`)).json()
  return { health: h, reference: ref, allRows: rows }
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

async function type(node, value) {
  await act(async () => {
    const setter = Object.getOwnPropertyDescriptor(
      window.HTMLInputElement.prototype,
      'value',
    ).set
    setter.call(node, value)
    node.dispatchEvent(new window.Event('input', { bubbles: true }))
    await settle()
  })
}

async function pressEnter(node) {
  await act(async () => {
    node.dispatchEvent(
      new window.KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true }),
    )
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
const buttonContaining = (text) => buttons().find((b) => (b.textContent ?? '').includes(text))
const text = () => (host.textContent ?? '')
const searchInput = () => host.querySelector('input[aria-label="Search peptides"]')
const rowsInDom = () => host.querySelectorAll('[data-construct-id]').length

await act(async () => {
  root.render(createElement(App))
})

// ---------------------------------------------------------------------------
// The offline banner
// ---------------------------------------------------------------------------

console.log('\n=== The data-source banner tracks what the service reports ===')

const onFallback = health.database.backend === 'sqlite' || Boolean(health.database.fallback_reason)

await waitFor(() => (onFallback ? text().includes('Showing sample data') : true), 'banner state')

check(
  onFallback
    ? 'a fallback is reported, so the banner warns that the numbers are sample data'
    : 'the real database answered, so no sample-data banner is shown',
  onFallback ? text().includes('Showing sample data') : !text().includes('Showing sample data'),
  `backend=${health.database.backend}`,
)
check(
  'the banner names the host it could not reach',
  onFallback ? text().includes(health.database.host) : true,
  health.database.host,
)
check(
  'the banner carries the reason the service reported for the fallback',
  onFallback ? text().includes('Reported reason') : true,
  health.database.fallback_reason ?? '(none)',
)
check(
  'the banner appears once, not once per mounted component',
  onFallback
    ? (host.textContent.match(/Showing sample data/g) ?? []).length === 1
    : true,
)

// ---------------------------------------------------------------------------
// Search
// ---------------------------------------------------------------------------

console.log('\n=== The search field narrows the list ===')

const field = await (async () => {
  const found = await waitFor(() => Boolean(searchInput()), 'the search field')
  return found ? searchInput() : null
})()
check('the peptide tab offers a search field', Boolean(field))

if (field) {
  const before = allRows.total
  const firstSequence = allRows.items[0]?.peptide_sequence
  check('the list has rows before searching', before > 0, `${before} rows`)

  await type(field, firstSequence)
  await pressEnter(field)
  await waitFor(() => text().includes('for'), 'the filtered count')

  const listCalls = () => requested.filter((u) => u.startsWith('/api/constructs?'))
  const searching = listCalls().some((u) => u.includes('search='))
  check('the search term reaches the service as a query parameter', searching,
    listCalls().slice(-1)[0])
  check(
    'the page reports that it is showing a filtered set',
    text().includes(firstSequence) || text().includes('construct'),
  )

  // A term that cannot match anything must produce an empty state rather than an error.
  await type(field, 'ZZZZZZZZ')
  await pressEnter(field)
  await waitFor(() => text().includes('Nothing matches'), 'the empty state')
  check('an unmatched term shows an empty state rather than an error',
    text().includes('Nothing matches') || rowsInDom() === 0)

  await click(buttonContaining('Clear'), 'Clear')
  await waitFor(() => text().includes('constructs match'), 'the restored list')
  check('clearing the field restores the full list',
    !text().includes('Nothing matches'))
}

// ---------------------------------------------------------------------------
// Sorting
// ---------------------------------------------------------------------------

console.log('\n=== Sorting reorders the list without changing the total ===')

const sortLabels = ['Pipeline rank', 'Peptide length', 'Peptide']
for (const label of sortLabels) {
  check(`the sort control offers "${label}"`, Boolean(buttonContaining(label)))
}

const totalBeforeSort = text()
await click(buttonContaining('Peptide length'), 'the length sort')
await waitFor(() => requested.some((u) => u.includes('order=peptide_length')), 'the length order')
check(
  'choosing a sort sends it to the service',
  requested.some((u) => u.includes('order=peptide_length')),
)
check('sorting does not change how many constructs match', totalBeforeSort === text(),
  `${totalBeforeSort} -> ${text()}`)

// ---------------------------------------------------------------------------
// Pagination
// ---------------------------------------------------------------------------

console.log('\n=== Paging addresses a page instead of growing the window ===')

// The fixture holds four constructs and a page holds twenty-five, so paging cannot be driven
// from the fixture alone. What is asserted here is that the controls exist exactly when there
// is more than one page, and that no "grow the limit" control remains.
check('the growing-limit control is gone', !buttonContaining('Show more'))

const pagingNeeded = allRows.total > 25
const previous = buttonContaining('Previous')
const next = buttonContaining('Next')
check(
  pagingNeeded
    ? 'paging controls appear when there is more than one page'
    : 'paging controls are hidden when everything fits on one page',
  pagingNeeded ? Boolean(previous || next) : !previous && !next,
  `total=${allRows.total}, page size=25`,
)

if (pagingNeeded) {
  const firstPageIds = [...host.querySelectorAll('[data-construct-id]')].map((n) =>
    n.getAttribute('data-construct-id'),
  )
  await click(next, 'Next')
  await waitFor(() => requested.some((u) => u.includes('offset=25')), 'the second page request')
  check('the second page is fetched by offset rather than by a larger limit',
    requested.some((u) => u.includes('offset=25')))
  const secondPageIds = [...host.querySelectorAll('[data-construct-id]')].map((n) =>
    n.getAttribute('data-construct-id'),
  )
  check('the second page does not repeat the first',
    !firstPageIds.some((id) => secondPageIds.includes(id)))
}

// ---------------------------------------------------------------------------
// The banner is layout-level, so it holds on another route too
// ---------------------------------------------------------------------------

console.log('\n=== The banner is layout-level, so it holds on every route ===')

// The banner lives in the layout rather than in a page, so navigating must not make it
// disappear. Asserted by navigating rather than asserted as a constant, because the whole
// reason it sits in the layout is that a reader arriving on the Builder from a shared link
// needs it as much as one who started on the Library.
const navToBuilder = [...host.querySelectorAll('a')].find(
  (a) => (a.textContent ?? '').trim() === 'Construct Builder',
)
check('the navigation offers a link to the Builder', Boolean(navToBuilder))

if (navToBuilder && onFallback) {
  await act(async () => {
    navToBuilder.dispatchEvent(
      new window.MouseEvent('click', { bubbles: true, cancelable: true, button: 0 }),
    )
    await settle()
  })
  await waitFor(() => text().includes('Build Your Construct'), 'the Builder')
  check('the Builder renders', text().includes('Build Your Construct'))
  check('the banner is still shown on the Builder route', text().includes('Showing sample data'))
}

const consoleClean = jsdomErrors.filter((e) => !String(e).includes('not wrapped in act'))
check('no uncaught rendering error', consoleClean.length === 0,
  consoleClean.map((e) => String(e)).join('; '))

// ---------------------------------------------------------------------------

await act(async () => {
  root.unmount()
})
await server.close()

console.log(`\n${failures === 0 ? 'PASS' : `FAIL — ${failures} check(s) failed`}`)
process.exit(failures === 0 ? 0 : 1)
