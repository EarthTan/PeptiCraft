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
check('the panel opens', await page.getByText('Activity score floor').isVisible())
check(
  'the allergenicity ceiling is offered, named after the predictor it comes from',
  await page.getByText('AlgPred2 allergenicity ceiling').isVisible(),
)
check('the peptide length range is offered', await page.getByText('Peptide length').isVisible())
check('the per-function cap is offered', await page.getByText('Candidates per function').isVisible())
check(
  'the score floor quotes the boundary the predictor declares',
  (await page.getByText(/boundary 0\.50/).count()) > 0,
)

// The route's own immunogenicity gate is stated in the panel, because it varies by
// application route and a fixed number in the same panel reads as the same thing. It is
// the gate of the route selected in step one — Wound Dressing, at 0.35.
check(
  'the panel states the route\'s immunogenicity gate',
  await page.getByText('MHC-I ≤ 0.35').isVisible(),
  (await panel.textContent())?.match(/.{0,60}MHC-I.{0,60}/)?.[0],
)
check(
  'the gate says the route owns it',
  /route owns it/i.test((await panelBody.textContent()) ?? ''),
)
check(
  'the allergenicity card says it is a different predictor',
  /different predictor from the route's immunogenicity gate/i.test(
    (await panelBody.textContent()) ?? '',
  ),
)

// The floor is a switch per function rather than one switch over all of them: a switch
// over several could not say which of them were on.
const floorSwitch = page.getByRole('switch', { name: 'Antioxidant activity score floor' })
check('the floor has a switch of its own', (await floorSwitch.count()) === 1)
check('the floor starts off', (await floorSwitch.getAttribute('aria-checked')) === 'false')

const floorBox = page.locator('input[aria-label="Antioxidant activity score floor"]')
await floorSwitch.click()
check('the floor input appears', (await floorBox.count()) === 1)
await floorBox.fill('0.5')

// The allergenicity ceiling at the boundary the predictor declares
const allergenSwitch = page.getByRole('switch', { name: 'AlgPred2 allergenicity ceiling' })
const allergenBox = page.locator('input[aria-label="AlgPred2 allergenicity ceiling"]')
await allergenSwitch.click()
check('the allergenicity input appears', (await allergenBox.count()) === 1)
await allergenBox.fill('0.3')

// The panel counts what is set
check('the panel counts what is set', (await panel.textContent())?.includes('2 set'))

// A direction whose score orders candidates rather than measuring activity gets no floor
// control: the note below the panel says so, and a control that does nothing would read as
// one that does. This is checked on a second page so it does not disturb the build above.
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
  'a ranking-only direction gets no floor control',
  (await rankingPage
    .getByRole('switch', { name: 'Anti-melanin Deposition activity score floor' })
    .count()) === 0,
)
check(
  'the panel says why',
  /orders candidates rather than measuring activity/i.test(
    (await rankingPage.locator('body').innerText()) ?? '',
  ),
  (await rankingPage.locator('body').innerText())?.match(/.{0,60}orders candidates.{0,90}/i)?.[0],
)
check(
  'the cap is offered as the substitute',
  await rankingPage.getByText('Candidates per function', { exact: true }).isVisible(),
)
await rankingPage.close()

// The gate follows the route: the same panel, a different application, a different number.
const hairPage = await browser.newPage()
await hairPage.goto(`${SITE}/builder?new=1`, { waitUntil: 'networkidle' })
const hairNameDialog = hairPage.getByRole('button', { name: 'Start building', exact: true })
if (await hairNameDialog.count()) await hairNameDialog.click()
await hairPage.getByRole('button', { name: /Hair Care/i }).first().click()
await hairPage.getByRole('button', { name: /Next: Function Direction/i }).click()
await hairPage.getByRole('button', { name: /^Antioxidant/ }).first().click()
await hairPage.locator('[data-panel="thresholds"]').click()
const hairPanelBody = hairPage.locator('[data-panel-body="thresholds"]')
check(
  'the gate follows the route',
  await hairPage.getByText('MHC-I ≤ 0.60').isVisible(),
  (await hairPanelBody.textContent())?.match(/.{0,60}MHC-I.{0,60}/)?.[0],
)
check(
  'the panel names the route the gate came from',
  /Hair Care/.test((await hairPanelBody.textContent()) ?? ''),
)
await hairPage.close()

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

// The two thresholds move together in this pool: the candidates with the highest antioxidant
// score are also the ones the allergenicity predictor scores highest, so only one of the 27
// that clear the floor is under the ceiling.
check('the floor and the ceiling together leave one candidate', /antioxidant: 1 of 113/.test(body), body.match(/antioxidant:.{0,60}/i)?.[0])
check('a narrow set is called out', /narrow set/i.test(body), body.match(/.{0,60}narrow.{0,60}/i)?.[0])

await page.screenshot({ path: '/tmp/pc-verify/threshold-results.png', fullPage: false })

// The thresholds are remembered with the rest of the build
const stored = await page.evaluate(() =>
  window.sessionStorage.getItem('pepticraft.builder-session.v2'),
)
const session = stored ? JSON.parse(stored) : {}
check(
  'the thresholds are kept with the build',
  session.thresholds?.functional_floor?.antioxidant === 0.5 &&
    session.thresholds?.max_allergenicity === 0.3,
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
