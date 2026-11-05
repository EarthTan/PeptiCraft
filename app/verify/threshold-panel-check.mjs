import { chromium } from 'playwright'

const SITE = process.env.PC_SITE ?? 'http://127.0.0.1:5175'
let failures = 0
function check(label, condition, detail) {
  if (condition) console.log(`  ok   ${label}`)
  else {
    failures += 1
    console.log(`  FAIL ${label}${detail === undefined ? '' : ` — ${detail}`}`)
  }
}

const browser = await chromium.launch()
const page = await browser.newPage()
const errors = []
page.on('pageerror', (e) => errors.push(String(e)))
page.on('console', (m) => {
  if (m.type() === 'error') errors.push(m.text())
})

await page.goto(`${SITE}/builder?new=1`, { waitUntil: 'networkidle' })

// A fresh build asks for its name before anything else.
const nameDialog = page.getByRole('button', { name: 'Start building', exact: true })
if (await nameDialog.count()) await nameDialog.click()

// Step 1 — a route
await page.getByRole('button', { name: /Wound Dressing/i }).first().click()
await page.getByRole('button', { name: /Next: Function Direction/i }).click()

// Step 2 — a function
await page.getByRole('button', { name: /^Antioxidant/ }).first().click()

const panel = page.locator('[data-panel="thresholds"]')
// The panel's own body, below the button that opens it.
const panelBody = page.locator('[data-panel-body="thresholds"]')
check('the threshold panel appears once a function is held', (await panel.count()) === 1)
check('the panel says nothing is set', (await panel.textContent())?.includes('none set'))

// The panel opens
await panel.click()
const panelText = (await panelBody.innerText()) ?? ''
check('the panel opens', (await panelBody.innerText())?.includes('Peptide length'))
check('the peptide length range is offered', await page.getByText('Peptide length').isVisible())
check('the per-function cap is offered', await page.getByText('Candidates per function').isVisible())

// The platform's own screening standards are not adjustable, so they are not on the panel
// at all: a card that shows a number the reader cannot change is a card that only adds
// noise. The standards themselves are applied by the pipeline and reported beside each
// construct on the results page.
check(
  'the activity boundary is not on the panel',
  !/Activity score floor/i.test(panelText),
  panelText.match(/.{0,40}Activity score floor.{0,40}/i)?.[0],
)
check(
  'the allergenicity ceiling is not on the panel',
  !/allergenicity/i.test(panelText),
  panelText.match(/.{0,40}allergenicity.{0,40}/i)?.[0],
)
check(
  'no platform value is quoted',
  (await page.getByText('platform value').count()) === 0,
)

// The route's immunogenicity gate does not belong to this panel either. It belongs to the
// route, it cannot be set, and putting it here would read as another setting.
check(
  'the route\'s immunogenicity gate is not in the panel',
  !/MHC-I|Immunogenicity gate/i.test(panelText),
  panelText.match(/.{0,40}(MHC-I|Immunogenicity gate).{0,40}/i)?.[0],
)

// The two settings that are the reader's own.
const lengthSwitch = page.getByRole('switch', { name: 'Peptide length' })
const shortest = page.locator('input[aria-label="Shortest peptide to keep"]')
const longest = page.locator('input[aria-label="Longest peptide to keep"]')
await lengthSwitch.click()
check('the peptide length fields appear', (await shortest.count()) === 1 && (await longest.count()) === 1)
await shortest.fill('20')
await longest.fill('30')

const capSwitch = page.getByRole('switch', { name: 'Candidates per function' })
const capBox = page.locator('input[aria-label="Candidates each function contributes"]')
await capSwitch.click()
check('the per-function cap field appears', (await capBox.count()) === 1)
await capBox.fill('5')

// The panel counts what is set
check('the panel counts what is set', (await panel.textContent())?.includes('2 set'))

// A direction whose score orders candidates rather than measuring activity is held by the
// per-function cap alone. This is checked on a second page so it does not disturb the build
// above.
const rankingPage = await browser.newPage()
await rankingPage.goto(`${SITE}/builder?new=1`, { waitUntil: 'networkidle' })
const rankingNameDialog = rankingPage.getByRole('button', { name: 'Start building', exact: true })
if (await rankingNameDialog.count()) await rankingNameDialog.click()
await rankingPage.getByRole('button', { name: /Wound Dressing/i }).first().click()
await rankingPage.getByRole('button', { name: /Next: Function Direction/i }).click()
await rankingPage.getByRole('button', { name: /^Anti-melanin/i }).first().click()
const rankingPanel = rankingPage.locator('[data-panel="thresholds"]')
await rankingPanel.click()
check(
  'the cap is offered as the way to hold that direction',
  await rankingPage.getByText('Candidates per function', { exact: true }).isVisible(),
)
await rankingPage.close()

// On to the results
await page.getByRole('button', { name: /Next: Scaffold/i }).click()
await page.getByRole('button', { name: /Next: Linker/i }).click()
await page.getByRole('button', { name: /Build Constructs/i }).click()

await page.waitForSelector('text=/threshold/i', { timeout: 20000 })
await page.waitForFunction(
  () => /candidates? the ranking|of \d+ candidates kept/.test(document.body.innerText),
  { timeout: 20000 },
)

const body = await page.locator('body').innerText()
check('the results report the thresholds', /screening thresholds removed/i.test(body), body.match(/.{0,60}threshold.{0,60}/i)?.[0])
check(
  'the report names the candidates kept and the pool they came from',
  /of \d+ candidates kept/.test(body),
  body.match(/antioxidant:.{0,80}/i)?.[0],
)

// The peptide length range and the cap are the two settings that can narrow a pool, so the
// report has to account for what they removed.
const kept = Number(body.match(/antioxidant: (\d+) of (\d+)/)?.[1] ?? '0')
const pool = Number(body.match(/antioxidant: \d+ of (\d+)/)?.[1] ?? '0')
check(
  'the range and the cap narrow the pool',
  kept > 0 && kept <= 5 && kept < pool,
  `kept ${kept} of ${pool}`,
)

await page.screenshot({ path: '/tmp/pc-verify/threshold-results.png', fullPage: false })

// The settings are remembered with the rest of the build
const stored = await page.evaluate(() =>
  window.sessionStorage.getItem('pepticraft.builder-session.v2'),
)
const session = stored ? JSON.parse(stored) : {}
check(
  'the settings are kept with the build',
  session.thresholds?.min_peptide_length === 20 &&
    session.thresholds?.max_peptide_length === 30 &&
    session.thresholds?.per_direction_limit === 5,
  JSON.stringify(session.thresholds),
)
check(
  'the platform standards are not carried as settings',
  session.thresholds?.functional_floor === undefined &&
    session.thresholds?.max_allergenicity === undefined,
  JSON.stringify(session.thresholds),
)

if (errors.length) {
  failures += 1
  console.log('  FAIL no page errors —', errors.slice(0, 3).join(' | '))
} else {
  console.log('  ok   no page errors')
}

await browser.close()
console.log(failures === 0 ? '\nall checks passed' : `\n${failures} check(s) failed`)
process.exit(failures === 0 ? 0 : 1)
