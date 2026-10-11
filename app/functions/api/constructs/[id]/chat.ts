/**
 * The model proxy. The one endpoint that is not served from a file.
 *
 * Why a function at all
 * ---------------------
 * The deployment has no Python runtime — `psycopg` ships a native binary and Cloudflare's
 * isolate cannot load it — so the platform is static. But a question cannot be answered from
 * a file, and the model key must not be in the browser bundle, where anyone could read it out
 * of the JavaScript. A Pages Function sits between the two: the browser calls the same
 * `/api/constructs/{id}/chat` path it always did, and the key stays in an environment
 * variable that only the function can read.
 *
 * What it sends the model
 * -----------------------
 * The construct's record, assembled the way the Python service assembles it. The fact block is
 * rebuilt here rather than shipped from the service because there is no service at runtime: the
 * static export already holds the detail, so the function reads it, adds the gate table and the
 * route metadata the export carries, and formats it. The prompt and the six rules are stated in
 * full below rather than imported, because a Python module cannot be imported into a Worker —
 * the one place where this duplicates the service, and it is duplicated deliberately and
 * visibly. `service/app/services/llm.py` carries the same rules with the reasoning, and
 * `service/tests/test_llm.py` compares the two: the prompt word for word, and the fact block by
 * the sections and score keys it is built from, so a section dropped on one side fails the
 * suite instead of shipping as a deployment that gives the model less than development does.
 *
 * What it will not do
 * -------------------
 * It does not decide anything. No score is computed here, no verdict is reached, no gate is
 * evaluated — the model is given the numbers and asked to explain them. If the function cannot
 * reach the model it returns the deterministic answer instead, with `provider: "template"`, so
 * a reader is told which of the two they are looking at rather than guessing.
 */

interface Env {
  /** OpenAI-compatible endpoint. A bare host is expanded to `/v1/chat/completions`. */
  LLM_BASE_URL: string
  LLM_API_KEY: string
  /** Model id. A domestic provider's own naming, e.g. `qwen-plus`. */
  LLM_MODEL: string
}

const TIMEOUT_MS = 20_000
const MAX_TURNS = 6

/**
 * The most of one turn that is forwarded. The question is capped at 2,000 characters and the
 * reply at 700 tokens, so the interface cannot reach this; it is here because the endpoint
 * takes a question from anyone who can reach the site, and `history` arrives unvalidated.
 */
const MAX_TURN_CHARS = 4_000

/** The id shape the export uses. Checked because the id becomes part of a file path. */
const CONSTRUCT_ID = /^con_\d+$/

/**
 * A number written the way the service writes it.
 *
 * The service formats every figure in the fact block with `f"{value:.6g}"`, which keeps six
 * significant digits, drops the trailing zeros that padding produced, and switches to
 * exponential notation once the rounded value's exponent leaves [-4, 5]. Neither of
 * JavaScript's two obvious answers agrees with it. `toPrecision(6)` rounds the same way but
 * keeps the zeros, so `0.31` would be written `0.310000`; parsing that back to a number drops
 * the zeros but hands the notation back to JavaScript's default, which switches to exponential
 * on a different rule — `0.0000123` comes out `0.0000123` where the service writes `1.23e-05`,
 * and `1234567` comes out `1234570` where the service writes `1.23457e+06`. Either way a model
 * quoting the deployed block quotes a figure the reader cannot find on the page, which is the
 * one property the block exists to provide.
 *
 * So the rounding is `toPrecision(6)` and the notation is chosen here, by `%g`'s rule. Both
 * halves are compared against the service's own output rather than trusted:
 * `service/tests/test_llm.py` runs the same values through Python's formatter, and
 * `app/verify/number-format-cases.json` holds the agreed strings, which this function is run
 * against. The cases sit on both sides of the notation switch, because that is the only place
 * the two languages differ and a check that stayed inside the fixed-notation range would pass
 * however badly this function got the switch wrong.
 *
 * The single `toPrecision(6)` call is asserted by the test suite: a call site that formatted a
 * number on its own would reintroduce the divergence for that one field, silently.
 */
export function formatNumber(value: number): string {
  if (!Number.isFinite(value)) return String(value)
  const rounded = Number(value.toPrecision(6))
  if (rounded === 0) return "0"
  const exponent = Math.floor(Math.log10(Math.abs(rounded)))
  if (exponent < -4 || exponent >= 6) {
    // `%g` always signs the exponent and pads it to at least two digits: `1e+06`, `1.23e-05`.
    const [mantissa, power] = rounded.toExponential(5).split("e")
    const sign = power.startsWith("-") ? "-" : "+"
    const digits = Math.abs(Number(power)).toString().padStart(2, "0")
    return `${mantissa.replace(/\.?0+$/, "")}e${sign}${digits}`
  }
  return String(rounded)
}

/**
 * The six rules, re-stated from `service/app/services/llm.py`'s `SYSTEM_PROMPT`.
 *
 * Kept the same on purpose. The Python service is the reference implementation and its
 * docstring holds the reasoning; this copy exists because a Worker cannot import Python, and a
 * divergent copy would let the same construct be described two different ways depending on
 * which path answered. `service/tests/test_llm.py` compares the two, so they cannot drift
 * quietly.
 */
const SYSTEM_PROMPT = `You are the analysis assistant for PeptiCraft, a platform that screens short peptide candidates for functional proteins used in topical and injectable biomaterials.

A reader is looking at one construct and has asked you a question about it. Answer from the fact block you have been given, which is the construct's own record.

Rules, in order of importance:

1. Never produce a number that is not in the fact block. Do not compute a score, convert a score to a percentage, average two values, estimate a molecular weight, or recall a figure from training. If the reader asks for something the block does not contain, say the record does not contain it.

2. "Not assessed" means the predictor did not cover this peptide. It is not a zero and not a pass. A construct can clear every gate that was assessed while one of them was never measured, and that is a different statement from clearing everything.

3. Some scores are marked as ranking-only. They order candidates; they are not probabilities and must never be described as confidence or likelihood.

4. Scores describe the functional peptide alone. The scaffold and the linker change the concatenation; no predictor was run on the fusion protein. Do not describe the assembled protein as characterised.

5. An assembled sequence is a reproduction of three real sequences joined together. When the scaffold was named by the reader rather than recorded against the construct, say that the pairing is a reconstruction.

6. Where a score sits near its threshold, say so plainly and give both numbers. Do not soften a borderline result into a pass or a fail.

Write in plain prose, two short paragraphs at most. No bullet lists, no headings, no markdown. Be direct: the reader has the numbers on the screen and wants the reading of them, not a restatement. British or American spelling are both acceptable; be consistent within an answer.`

// ---------------------------------------------------------------------------

/** The exported files, resolved relative to the site's own origin. */
function dataUrl(path: string, origin: string): string {
  return `${origin}/data/${path}`
}

async function readJson(origin: string, path: string): Promise<any | null> {
  const response = await fetch(dataUrl(path, origin))
  if (!response.ok) return null
  return response.json()
}

/** The route metadata the export carries, as much of it as the fact block refers to. */
interface RouteSummary {
  id: string
  name?: string
  barrier_label?: string
  immune_exposure?: string
  screening?: {
    cpp_weight?: string
    solubility_weight?: string
    thermal_stability_weight?: string
  }
}

/**
 * The construct's record as the model sees it.
 *
 * Mirrors `build_fact_block` in the service, section for section. Two things cannot be read
 * off the detail file directly. The gate table carries one route's verdict per construct, and
 * a reader who switched routes is looking at a different verdict than the one the detail
 * holds, so the per-route table is read instead. And the route's own description — its name,
 * its barrier and the weights its screening profile uses — lives in the metadata bundle, so
 * that is passed in. Without it the model would be told which route is in force but nothing
 * about what that route means for the screening.
 */
function factBlock(
  detail: any,
  routeId: string | null,
  verdicts: Record<string, Record<string, string>> | null,
  routes: RouteSummary[],
): string {
  const scores = detail.scores ?? {}
  const meta = detail.score_meta ?? {}
  const safety = detail.safety ?? {}
  const lines: string[] = []

  const scoreLine = (key: string): string => {
    const value = scores[key]
    const label = meta[key]
    const assessed = value === null || value === undefined ? 'NOT ASSESSED' : 'assessed'
    const rendered =
      value === null || value === undefined ? 'not assessed' : formatNumber(value)
    const parts = [`- ${key}: ${rendered} (${assessed})`]
    if (label) {
      parts.push(`measured by ${label.tool}`)
      parts.push(`higher is ${label.higher_is_better ? 'better' : 'worse'}`)
      if (label.semantics && label.semantics !== 'probability') {
        parts.push(`this number is ${label.semantics}, NOT a probability`)
      }
      if (label.is_veto_gate) parts.push('a failure here eliminates the candidate')
      if (label.applied_threshold) {
        parts.push(
          `threshold ${label.applied_threshold.value} (from the ${label.applied_threshold.source})`,
        )
      }
    }
    return parts.join(' | ')
  }

  lines.push('CONSTRUCT')
  lines.push(`- id: ${detail.id}`)
  lines.push(`- direction: ${detail.direction} (${detail.direction_label})`)
  lines.push(`- channel: ${detail.channel}`)
  lines.push(`- status: ${detail.status}`)
  lines.push(`- peptide: ${detail.peptide_sequence} (${detail.peptide_length} aa)`)
  lines.push(
    `- peptide provenance: ${detail.peptide?.source} ${detail.peptide?.source_version}` +
      (detail.peptide?.source_accession ? `, accession ${detail.peptide.source_accession}` : ''),
  )

  // The route the reader is looking at. A request that named one the record has a composite
  // for is taken at its word; otherwise the record's own route is named, because the verdict
  // below is that route's and a block saying "no route was named" beside it would contradict
  // itself.
  const requested = routeId && (detail.delivery_scores ?? {})[routeId] ? routeId : null
  const shownRoute: string | null =
    requested ?? (typeof safety.route_id === 'string' ? safety.route_id : null)
  const route = routes.find((candidate) => candidate.id === shownRoute) ?? null

  lines.push('')
  lines.push('APPLICATION ROUTE AND ITS SCREENING PROFILE')
  if (shownRoute) {
    lines.push(`- route: ${route?.name ? `${route.name} (${shownRoute})` : shownRoute}`)
    if (route?.barrier_label) lines.push(`- barrier: ${route.barrier_label}`)
    if (route?.immune_exposure) lines.push(`- immune exposure: ${route.immune_exposure}`)
    if (route?.screening) {
      lines.push(
        `- weight tiers: expression ${route.screening.cpp_weight}, ` +
          `solubility ${route.screening.solubility_weight}, ` +
          `thermal stability ${route.screening.thermal_stability_weight}`,
      )
    }
  } else {
    lines.push('- no route was named for this response')
  }

  lines.push('')
  lines.push('SAFETY VERDICT')
  // The verdict for the route the reader actually has on screen, which is not always the one
  // baked into the detail file.
  const shownVerdict =
    (shownRoute ? verdicts?.[detail.id]?.[shownRoute] : undefined) ?? safety.verdict
  const verdictWord: Record<string, string> = {
    clear: 'clears every assessed gate',
    vetoed: 'is stopped by a veto gate',
    borderline: 'clears every assessed gate but sits close to one',
    indeterminate: 'has no assessed veto gate and cannot be cleared or stopped',
  }
  lines.push(`- verdict: ${shownVerdict} (${verdictWord[shownVerdict] ?? shownVerdict})`)
  if (safety.immunogenicity_threshold !== null && safety.immunogenicity_threshold !== undefined) {
    lines.push(
      `- the immunogenicity gate for this route is ${safety.immunogenicity_threshold}`,
    )
  }
  for (const gate of safety.gates ?? []) {
    const value =
      gate.value === null || gate.value === undefined
        ? 'not assessed'
        : formatNumber(gate.value)
    const outcome =
      gate.passed === null || gate.passed === undefined
        ? 'no value, so it eliminates nothing'
        : gate.passed
          ? 'PASS'
          : 'FAIL'
    const failing = gate.higher_is_better
      ? 'a value below the threshold fails'
      : 'a value above the threshold fails'
    lines.push(
      `- ${gate.label}: ${value} against ${gate.threshold} -> ${outcome} ` +
        `(${failing}; veto gate: ${gate.is_veto_gate ? 'yes' : 'no'})`,
    )
  }
  if (safety.vetoed_by?.length) lines.push(`- stopped by: ${safety.vetoed_by.join(', ')}`)
  if (safety.unassessed?.length) lines.push(`- not assessed: ${safety.unassessed.join(', ')}`)

  lines.push('')
  lines.push('SCORES')
  for (const key of [
    'antioxidant', 'toxicity', 'hemolysis', 'immunogenicity', 'b_cell_epitope',
    'thermal_stability', 'solubility', 'cpp', 'composite',
  ]) {
    lines.push(scoreLine(key))
  }

  const supplementary = detail.supplementary ?? {}
  lines.push('')
  lines.push('SUPPLEMENTARY MEASUREMENTS')
  // The keys are the record's own field names, which is what the value is read by. Spelling
  // one of them differently here does not fail loudly — it renders as "not assessed", which is
  // a false claim about a measurement that exists — so `service/tests/test_llm.py` checks that
  // both fact blocks read the same three.
  for (const key of ['immunogenicity_ii_pct_rank', 'allergenicity', 'aggregation_a3v']) {
    const value = supplementary[key]
    lines.push(
      `- ${key}: ${
        value === null || value === undefined ? 'not assessed' : formatNumber(value)
      }`,
    )
  }
  if (supplementary.immunogenicity_ii_pct_rank !== null &&
      supplementary.immunogenicity_ii_pct_rank !== undefined) {
    lines.push(
      '- the MHC-II figure is a percent rank, not a probability: lower means a stronger predicted binder',
    )
  }

  lines.push('')
  lines.push('COMPOSITE UNDER EVERY ROUTE')
  for (const [id, delivery] of Object.entries(detail.delivery_scores ?? {})) {
    const named = routes.find((candidate) => candidate.id === id)
    const composite = (delivery as { composite?: number | null }).composite
    lines.push(
      `- ${named?.name ? `${named.name} (${id})` : id}: ${
        composite === null || composite === undefined ? 'not assessed' : formatNumber(composite)
      }`,
    )
  }

  lines.push('')
  lines.push('ASSEMBLY')
  lines.push(`- scaffold binding: ${detail.backbone_binding}`)
  lines.push(`- scaffold: ${detail.backbone_name ?? 'none named'}`)
  lines.push(`- linker: ${detail.linker_name ?? 'none recorded'}`)
  lines.push(`- fused sequence: ${detail.assembled_sequence_available ? 'available' : 'not available'}`)
  if (detail.full_sequence) lines.push(`- fused length: ${detail.full_sequence.length} aa`)
  if (detail.status === 'WIP') {
    lines.push("- this construct's direction has not been signed off")
  }

  return lines.join('\n')
}

/** The deterministic answer, used when no model is configured or the call failed. */
function templateAnswer(detail: any, question: string): string {
  const q = question.toLowerCase()
  const safety = detail.safety ?? {}
  const verdict = safety.verdict ?? 'indeterminate'

  const safetyText = (): string => {
    const parts = [
      `The safety verdict under this route is ${verdict}.`,
    ]
    for (const gate of safety.gates ?? []) {
      const value =
        gate.value === null || gate.value === undefined ? 'not assessed' : String(gate.value)
      parts.push(
        `${gate.label} reads ${value} against a threshold of ${gate.threshold}` +
          (gate.passed === null || gate.passed === undefined
            ? ', so it eliminates nothing'
            : gate.passed
              ? ', which passes'
              : ', which fails'),
      )
    }
    if (safety.unassessed?.length) {
      parts.push(`Not assessed: ${safety.unassessed.join(', ')}.`)
    }
    return parts.join(' ')
  }

  const assemblyText = (): string => {
    const parts = [
      `The scaffold binding is ${detail.backbone_binding}`,
      detail.backbone_name ? `against ${detail.backbone_name}` : 'with no scaffold named',
    ]
    parts.push(
      detail.assembled_sequence_available
        ? 'and a fused sequence is available'
        : 'and no fused sequence can be emitted',
    )
    if (detail.linker_name) parts.push(`The linker recorded is ${detail.linker_name}.`)
    return parts.join(', ') + '.'
  }

  const scoreText = (): string => {
    const scores = detail.scores ?? {}
    const parts: string[] = []
    for (const key of ['cpp', 'solubility', 'thermal_stability']) {
      const value = scores[key]
      parts.push(
        `${key.replace(/_/g, ' ')} ${value === null || value === undefined ? 'was not assessed' : value}`,
      )
    }
    return `On developability: ${parts.join(', ')}.`
  }

  if (['safe', 'safety', 'tox', 'hemo', 'immun', 'gate', 'veto'].some((w) => q.includes(w))) {
    return safetyText()
  }
  if (['sequence', 'assembl', 'backbone', 'scaffold', 'fuse', 'linker'].some((w) => q.includes(w))) {
    return assemblyText()
  }
  if (['solubility', 'express', 'purif', 'yield', 'stability', 'thermal', 'develop'].some((w) => q.includes(w))) {
    return scoreText()
  }

  const composite = detail.scores?.composite
  return (
    `This answer is composed from the record for ${detail.id}, not from a language model, so it ` +
    `covers the fields the record actually holds. The safety verdict under this route is ${verdict}` +
    (composite === null || composite === undefined
      ? ' and no composite could be computed for it.'
      : `, and the composite reads ${composite}.`) +
    ' Topics the record can answer: the safety gates and the route threshold; the peptide ' +
    'origin and composition; the linker and the state of the scaffold binding; solubility ' +
    'and thermal stability; and the metrics that were not assessed.'
  )
}

async function callModel(env: Env, messages: any[]): Promise<string | null> {
  const base = env.LLM_BASE_URL.replace(/\/+$/, '')
  const endpoint = base.endsWith('/chat/completions')
    ? base
    : base.endsWith('/v1')
      ? `${base}/chat/completions`
      : `${base}/v1/chat/completions`

  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS)
  try {
    const response = await fetch(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${env.LLM_API_KEY}`,
      },
      body: JSON.stringify({
        model: env.LLM_MODEL,
        messages,
        temperature: 0.2,
        max_tokens: 700,
      }),
      signal: controller.signal,
    })
    if (!response.ok) {
      console.error(`model responded ${response.status}: ${(await response.text()).slice(0, 400)}`)
      return null
    }
    const body = (await response.json()) as any
    const content = body?.choices?.[0]?.message?.content
    return typeof content === 'string' && content.trim() ? content.trim() : null
  } catch (error) {
    console.error('model call failed:', error instanceof Error ? error.message : String(error))
    return null
  } finally {
    clearTimeout(timer)
  }
}

// ---------------------------------------------------------------------------

export const onRequestPost = async ({ request, env }: { request: Request; env: Env }) => {
  const origin = new URL(request.url).origin

  let payload: any
  try {
    payload = await request.json()
  } catch {
    return json({ error: 'bad_request', detail: 'the request body is not JSON' }, 400)
  }

  const constructId = String(payload.construct_id ?? '')
  const question = String(payload.message ?? '').trim()
  const routeId = payload.route_id ? String(payload.route_id) : null

  if (!constructId || !question) {
    return json({ error: 'bad_request', detail: 'a construct id and a message are required' }, 400)
  }
  if (!CONSTRUCT_ID.test(constructId)) {
    // The id becomes part of a path below. Unconstrained, `../../assets/x.js#` would resolve
    // through the URL parser and read a file this site already serves — harmless in itself,
    // but it turns the endpoint into an arbitrary-file fetch instead of a construct lookup.
    return json({ error: 'bad_request', detail: 'the construct id is not a construct id' }, 400)
  }
  if (question.length > 2000) {
    return json({ error: 'bad_request', detail: 'the message is longer than 2000 characters' }, 400)
  }

  // The construct's record, from the same export the rest of the site reads.
  const detail = await readJson(origin, `constructs/${constructId}.json`)
  if (!detail) {
    return json({ error: 'not_found', detail: `construct ${constructId} not found` }, 404)
  }
  const verdicts = await readJson(origin, 'verdicts.json')
  // The route descriptions, so the fact block can say what the route in force means for the
  // screening rather than only naming it.
  const meta = await readJson(origin, 'meta.json')
  const routes: RouteSummary[] = Array.isArray(meta?.routes) ? meta.routes : []

  // No model configured: answer from the record and say so. This is the path a deployment
  // without a key takes, and it is a working answer rather than an error page.
  if (!env.LLM_BASE_URL || !env.LLM_API_KEY || !env.LLM_MODEL) {
    return json(respond(constructId, templateAnswer(detail, question), 'template', []))
  }

  const messages: any[] = [{ role: 'system', content: SYSTEM_PROMPT }]
  const history = Array.isArray(payload.history) ? payload.history : []
  // Bounded on both axes before anything is forwarded: the last few turns only, and only the
  // head of each. Without it a request could put an unbounded amount of text in front of the
  // model, which is the one cost the endpoint passes on to the key.
  const turns = history
    .filter(
      (turn: any) =>
        (turn?.role === 'user' || turn?.role === 'assistant') &&
        typeof turn?.content === 'string' &&
        turn.content.trim(),
    )
    .slice(-MAX_TURNS * 2)
    .map((turn: any) => ({ role: turn.role, content: turn.content.slice(0, MAX_TURN_CHARS) }))
  // A client that sends the question it is asking as the last turn of the history would have
  // the model read it twice, and the question is appended below with the fact block under it.
  if (turns.length && turns[turns.length - 1].role === 'user' &&
      turns[turns.length - 1].content.trim() === question) {
    turns.pop()
  }
  for (const turn of turns.slice(-MAX_TURNS)) {
    messages.push({ role: turn.role, content: turn.content })
  }
  messages.push({
    role: 'user',
    content: `FACT BLOCK\n${factBlock(detail, routeId, verdicts, routes)}\n\nQUESTION\n${question}`,
  })

  const answer = await callModel(env, messages)
  if (!answer) {
    // The model was configured and did not answer. The reader still gets an answer, and the
    // response names the generator that produced it.
    return json(respond(constructId, templateAnswer(detail, question), 'template', []))
  }

  return json(respond(constructId, answer, 'llm', suggested(detail, question)))
}

function respond(constructId: string, content: string, provider: string, suggested: string[]) {
  return {
    provider,
    construct_id: constructId,
    message: {
      id: `msg_${crypto.randomUUID().replace(/-/g, '').slice(0, 12)}`,
      role: 'assistant',
      content,
      timestamp: new Date().toISOString(),
      actions: [],
    },
    suggested_questions: suggested,
    llm_configured: provider === 'llm',
  }
}

/**
 * The suggestions a reader gets after a generated answer.
 *
 * Deliberately not generated. They are the standing questions worth asking of any construct in
 * this direction, and a model asked to invent follow-ups would produce a different set on every
 * turn — which reads as the platform not knowing what its own data can answer.
 */
function suggested(detail: any, question: string): string[] {
  const out = [
    'How does the safety gate read under this route?',
    'Which metrics were not assessed?',
    'What is the state of the scaffold binding?',
  ]
  if (detail.semantics === 'ranking_only') {
    out.push('Why is the functional score a ranking signal rather than a probability?')
  }
  return out.filter((q) => q.toLowerCase() !== question.trim().toLowerCase())
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' },
  })
}