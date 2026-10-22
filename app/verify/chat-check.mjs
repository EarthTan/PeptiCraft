/** Execute the deployed Pages handler with mocked assets and provider; no API key is needed. */
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { onRequestPost } from '../functions/api/constructs/[id]/chat.ts'

const record = {
  id: 'con_0001', peptide_sequence: 'ACDE', peptide_length: 4,
  peptide: { source: 'fixture_pdb', source_version: 'test-version', source_accession: 'test-accession' },
  functional_score: 0.5729, functional_score_label: 'AnOxPePred', semantics: 'probability',
  scores: { antioxidant: 0.5729, toxicity: 0.345, hemolysis: 0.22, immunogenicity: 0.5,
    b_cell_epitope: 0.21, thermal_stability: 0.4769, solubility: 0.9379, cpp: 0.3962, composite: 0.747991 },
  delivery_scores: { 'wound-dressing': { composite: 0.747991 }, 'hair-care': { composite: 0.800698 } },
  safety: {
    route_id: 'wound-dressing', verdict: 'vetoed', immunogenicity_threshold: 0.35,
    gates: [
      { key: 'toxicity', label: 'Toxicity', value: 0.345, threshold: 0.38, threshold_source: 'tool', higher_is_better: false, is_veto_gate: true },
      { key: 'hemolysis', label: 'Haemolysis', value: 0.22, threshold: 0.55, threshold_source: 'tool', higher_is_better: false, is_veto_gate: true },
      { key: 'immunogenicity', label: 'Immunogenicity (MHC-I)', value: 0.5, threshold: 0.35, threshold_source: 'route', higher_is_better: false, is_veto_gate: true },
      { key: 'b_cell_epitope', label: 'B-cell epitope', value: 0.21, threshold: 0.1512, higher_is_better: false, is_veto_gate: false },
    ],
  },
  backbone_id: null, backbone_name: null, backbone_binding: 'placeholder',
  linker: { id: '1', name: 'GGGGS', sequence: 'GGGGS' }, linker_name: 'GGGGS',
  full_sequence: null, assembled_sequence_available: false,
  segments: [{ type: 'backbone', sequence: '', available: false }],
}
const scaffold = {
  id: 'fixture-scaffold', short_name: 'Fixture scaffold',
  sequences: [{ sequence_id: 'short', sequence: 'ACD' }, { sequence_id: 'long', sequence: 'ACDEFG' }],
  expression: {
    system: 'Pichia pastoris GS115', vector_recorded: 'pPIC9K-fixture',
    rationale: 'Family construct only; tags and the exact selected sequence must be checked.',
    source_url: 'https://example.org/patent/fixture', sequence_id: 'source-fixture',
  },
}
const linker = { id: 'LK_EAAAK', name: 'EAAAK', sequence: 'EAAAK', rigidity: 'Rigid', reference: 'Arai et al. 2001.' }
const meta = {
  routes: [
    { id: 'wound-dressing', name: 'Wound Dressing', screening: { immunogenicity_threshold: 0.35 }, scaffold_ids: ['fixture-scaffold'] },
    { id: 'hair-care', name: 'Hair Care', screening: { immunogenicity_threshold: 0.6 }, scaffold_ids: [] },
  ],
  tools: [{ key: 'toxicity', threshold: 0.38, threshold_source: 'project' }],
}
const fixtures = {
  'constructs/con_0001.json': record, 'meta.json': meta, 'composites.json': {},
  'scaffolds/fixture-scaffold.json': scaffold, 'linkers/LK_EAAAK.json': linker,
}
const configured = { LLM_BASE_URL: 'https://provider.invalid', LLM_API_KEY: 'offline-test-key', LLM_MODEL: 'test-model' }
const realFetch = globalThis.fetch
let providerRequests = []
let assetPaths = []
let checks = 0

async function run(payload, options = {}) {
  providerRequests = []
  assetPaths = []
  const assets = structuredClone(options.assets ?? fixtures)
  const env = {
    ...(options.configured ? { ...configured, ...options.environment } : {}),
    ASSETS: { fetch: async (request) => {
      const path = new URL(request.url).pathname.replace(/^\/data\//, '')
      assetPaths.push(path)
      return Object.hasOwn(assets, path) ? Response.json(assets[path]) : new Response('missing', { status: 404 })
    } },
  }
  globalThis.fetch = async (input, init) => {
    providerRequests.push({ endpoint: String(input), ...JSON.parse(init.body) })
    if (options.providerError) throw options.providerError
    if (options.providerStatus) return new Response('provider refused', { status: options.providerStatus })
    if (options.providerEnvelope !== undefined) return Response.json(options.providerEnvelope)
    return Response.json({ choices: [{ message: { content: options.modelContent ?? JSON.stringify({
      answer: 'The current {{fact:composite}} is a ranking signal, not a success probability.', evidence_ids: ['scores'],
    }) } }] })
  }
  const request = new Request(`https://app.invalid/api/constructs/${options.pathId ?? 'con_0001'}/chat`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: options.rawBody ?? JSON.stringify(payload && !Array.isArray(payload) ? { mode: options.configured ? 'ai' : 'record', ...payload } : payload),
  })
  const response = await onRequestPost({ request, env })
  const body = await response.json()
  checks += 1
  return { status: response.status, ...body }
}

const base = { construct_id: 'con_0001', message: 'Explain the composite score and immune threshold.' }
const ids = (response) => response.message.evidence.map((claim) => claim.id)
const claim = (response, id) => response.message.evidence.find((entry) => entry.id === id)

try {
  const resolved = await run({ ...base, route_id: 'hair-care', scaffold_id: 'fixture-scaffold', linker_id: 'LK_EAAAK',
    message: '当前综合分和免疫阈值是什么？当前组装及表达依据是什么？' })
  assert.equal(resolved.status, 200)
  assert.equal(resolved.provider, 'template')
  assert.equal(resolved.llm_configured, false)
  assert.equal(resolved.mode, 'record')
  assert.equal(resolved.fallback_reason, null)
  assert.equal(resolved.model, null)
  assert.equal(resolved.message.provider, 'template')
  assert.equal(resolved.context_key, JSON.stringify(['con_0001', 'hair-care', 'fixture-scaffold', 'LK_EAAAK']))
  assert.equal(resolved.message.context_key, resolved.context_key)
  assert.match(claim(resolved, 'scores').text, /composite: 0\.800698/)
  assert.doesNotMatch(resolved.message.content, /0\.747991|阈值 0\.35/)
  assert.match(claim(resolved, 'safety').text, /MHC-I\) 0\.5 \/ 阈值 0\.6 \(通过/)
  assert.match(claim(resolved, 'safety').text, /项目阈值/)
  assert.match(claim(resolved, 'assembly').text, /Fixture scaffold.*EAAAK.*15 aa/)
  assert.match(claim(resolved, 'assembly').text, /重建/)
  assert.match(claim(resolved, 'expression').text, /Pichia pastoris GS115.*pPIC9K-fixture.*exact selected sequence/)
  assert.equal(claim(resolved, 'expression_source').url, scaffold.expression.source_url)
  assert.match(claim(resolved, 'linker_source').text, /Arai et al\. 2001/)
  assert.ok(ids(resolved).includes('scope'))
  assert.ok(ids(resolved).includes('missing'))
  assert.equal(providerRequests.length, 0)
  console.log('ok current route, composite, gate, chosen assembly and actual sources agree')

  const disconnected = await run(base, { rawBody: JSON.stringify(base) })
  assert.equal(disconnected.status, 503)
  assert.equal(disconnected.error, 'llm_not_configured')
  assert.equal(disconnected.llm_configured, false)
  assert.equal(disconnected.message, undefined)
  assert.equal(providerRequests.length, 0)
  const explicitRecord = await run({ ...base, mode: 'record' }, { configured: true })
  assert.equal(explicitRecord.provider, 'template')
  assert.equal(explicitRecord.model, null)
  assert.equal(explicitRecord.fallback_reason, null)
  assert.equal(providerRequests.length, 0)
  console.log('ok AI is the default, disconnected AI errors honestly and record mode is explicit')

  const authoritativeAssets = structuredClone(fixtures)
  const exportedSafety = structuredClone(record.safety)
  exportedSafety.route_id = 'hair-care'
  exportedSafety.immunogenicity_threshold = 0.6
  exportedSafety.verdict = 'borderline'
  exportedSafety.unassessed = []
  exportedSafety.vetoed_by = []
  exportedSafety.gates = exportedSafety.gates.map((gate) => ({
    ...gate,
    threshold: gate.key === 'immunogenicity' ? 0.6 : gate.threshold,
    passed: gate.value <= (gate.key === 'immunogenicity' ? 0.6 : gate.threshold),
    borderline: gate.key === 'toxicity',
  }))
  authoritativeAssets['constructs/con_0001.json'].route_contexts = {
    'hair-care': { composite: 0.123456, safety: exportedSafety },
  }
  const authoritative = await run({ ...base, route_id: 'hair-care' }, { assets: authoritativeAssets })
  assert.equal(authoritative.status, 200)
  assert.match(claim(authoritative, 'scores').text, /composite: 0\.123456/)
  assert.doesNotMatch(claim(authoritative, 'scores').text, /0\.800698|0\.747991/)
  const brokenExport = structuredClone(authoritativeAssets)
  brokenExport['constructs/con_0001.json'].route_contexts['hair-care'].safety.gates.pop()
  brokenExport['constructs/con_0001.json'].route_contexts['hair-care'].safety.gates.pop()
  assert.equal((await run({ ...base, route_id: 'hair-care' }, { assets: brokenExport })).status, 503)
  console.log('ok complete service-authored route contexts take priority and incomplete ones fail explicitly')

  const retained = await run({ ...base, scaffold_id: 'fixture-scaffold', message: 'What is the assembled sequence state?' })
  assert.match(claim(retained, 'assembly').text, /GGGGS.*15 aa/)
  const linkerOnly = await run({ ...base, linker_id: 'LK_EAAAK', message: '解释连接肽和组装' })
  assert.match(claim(linkerOnly, 'assembly').text, /EAAAK.*没有可用/)
  assert.ok(claim(linkerOnly, 'linker_source'))
  const storedAssets = structuredClone(fixtures)
  storedAssets['constructs/con_0001.json'].backbone_id = scaffold.id
  storedAssets['constructs/con_0001.json'].backbone_binding = 'recorded'
  storedAssets['constructs/con_0001.json'].full_sequence = 'STALE'
  storedAssets['constructs/con_0001.json'].assembled_sequence_available = true
  const changedLinker = await run({ ...base, linker_id: 'LK_EAAAK', message: 'Explain assembly' }, { assets: storedAssets })
  assert.match(claim(changedLinker, 'assembly').text, /EAAAK.*15 aa/)
  assert.ok(assetPaths.includes('scaffolds/fixture-scaffold.json'))
  console.log('ok stored linker defaults and linker-only edits preserve coherent assembly state')

  const missingAssets = structuredClone(fixtures)
  missingAssets['constructs/con_0001.json'].scores.immunogenicity = null
  const missing = await run({ ...base, message: '安全性与缺测情况', route_id: 'hair-care' }, { assets: missingAssets })
  assert.match(claim(missing, 'missing').text, /immunogenicity.*不是零.*不是通过/)
  assert.match(claim(missing, 'safety').text, /MHC-I\) 未评估 \/ 阈值 0\.6 \(未评估，不等于通过/)
  const noCompositeAssets = structuredClone(fixtures)
  delete noCompositeAssets['constructs/con_0001.json'].delivery_scores['hair-care']
  const noComposite = await run({ ...base, route_id: 'hair-care' }, { assets: noCompositeAssets })
  assert.match(claim(noComposite, 'scores').text, /composite: not assessed/)
  assert.doesNotMatch(claim(noComposite, 'scores').text, /0\.747991/)
  console.log('ok missing scores never become passes or values from a different route')

  for (const message of ['Compare this with the best other candidate', '与其他候选比较，哪个更好？']) {
    const comparison = await run({ ...base, message })
    assert.ok(ids(comparison).includes('comparison'))
    assert.ok(ids(comparison).includes('scope'))
    assert.match(claim(comparison, 'comparison').text, /only the current candidate|只读取当前候选/)
  }
  const thermal = await run({ ...base, message: 'What storage temperature and shelf life can it tolerate?' })
  assert.match(claim(thermal, 'thermal').text, /not a probability.*not been calibrated/)
  assert.ok(claim(thermal, 'thermal').url.startsWith('https://pmc.ncbi.nlm.nih.gov/'))
  console.log('ok bilingual intents, comparison limits and thermal interpretation')

  const valid = await run({ ...base, route_id: 'hair-care', history: [{ role: 'user', content: base.message }] }, {
    configured: true, modelContent: JSON.stringify({
      answer: 'The current {{fact:composite}} ranks this record within the selected route. Its {{fact:immunogenicity_threshold}} is a project screening boundary; it does not establish human safety.',
      evidence_ids: ['safety'],
    }),
  })
  assert.equal(valid.provider, 'llm')
  assert.equal(valid.llm_configured, true)
  assert.equal(valid.fallback_reason, null)
  assert.equal(valid.model, 'test-model')
  assert.equal(valid.mode, 'ai')
  assert.ok(ids(valid).includes('safety'))
  assert.ok(ids(valid).includes('missing'))
  assert.ok(ids(valid).includes('scope'))
  assert.equal(providerRequests.length, 1)
  assert.equal(providerRequests[0].endpoint, 'https://provider.invalid/v1/chat/completions')
  assert.equal(providerRequests[0].messages.filter((message) => message.role === 'user').length, 1)
  assert.match(providerRequests[0].messages.at(-1).content, /0\.800698/)
  assert.doesNotMatch(providerRequests[0].messages.at(-1).content, /0\.747991/)
  assert.match(valid.message.content, /composite=0\.800698.*immunogenicity_threshold=0\.6/)
  assert.notEqual(valid.message.content, valid.message.evidence.map((entry) => entry.text).join('\n\n'))
  assert.match(providerRequests[0].messages[0].content, /Write your own useful, natural answer/)
  assert.ok(providerRequests[0].max_tokens > 250)
  for (const [baseUrl, endpoint] of [
    ['https://provider.invalid/api/v4/', 'https://provider.invalid/api/v4/chat/completions'],
    ['https://provider.invalid/compatible-mode/v1', 'https://provider.invalid/compatible-mode/v1/chat/completions'],
    ['https://provider.invalid/custom/chat/completions', 'https://provider.invalid/custom/chat/completions'],
    ['https://provider.invalid/api/v4/?region=test', 'https://provider.invalid/api/v4/chat/completions?region=test'],
  ]) {
    const customBase = await run(base, { configured: true, environment: { LLM_BASE_URL: baseUrl } })
    assert.equal(customBase.provider, 'llm')
    assert.equal(providerRequests[0].endpoint, endpoint)
  }
  const invalidBase = await run(base, { configured: true, environment: { LLM_BASE_URL: 'invalid-url' } })
  assert.equal(invalidBase.status, 503)
  assert.equal(invalidBase.error, 'model_unavailable')
  const minimaxFlash = await run(base, { configured: true, environment: {
    LLM_BASE_URL: 'https://api.minimax.cn/v1', LLM_MODEL: 'MiniMax-M3.1-Flash',
  } })
  assert.equal(minimaxFlash.provider, 'llm')
  assert.equal(providerRequests[0].endpoint, 'https://api.minimax.cn/v1/chat/completions')
  assert.equal(providerRequests[0].reasoning_effort, 'medium')
  assert.equal(providerRequests[0].reasoning_split, true)
  assert.equal(providerRequests[0].max_completion_tokens, 8192)
  assert.equal(providerRequests[0].max_tokens, undefined)
  assert.equal(providerRequests[0].temperature, undefined)
  const alternative = await run({ ...base, route_id: 'hair-care' }, {
    configured: true, modelContent: JSON.stringify({ answer: 'First clarify the application you intend to test. The current {{fact:composite}} can help prioritize, but cannot decide experimental success.', evidence_ids: ['scores'] }),
  })
  assert.equal(alternative.provider, 'llm')
  assert.notEqual(alternative.message.content, valid.message.content)
  const greeting = await run({ ...base, message: '你好，你能怎样帮助我？' }, {
    configured: true, modelContent: '{"answer":"你好！我可以和你讨论当前候选的依据、局限和下一步验证思路。你最关心哪一方面？","evidence_ids":[]}',
  })
  assert.equal(greeting.provider, 'llm')
  assert.deepEqual(ids(greeting), ['scope'])
  assert.doesNotMatch(greeting.message.content, /composite|当前对象/)
  const otherDirectionAssets = structuredClone(fixtures)
  otherDirectionAssets['constructs/con_0001.json'].direction = 'anti-inflammatory'
  otherDirectionAssets['constructs/con_0001.json'].functional_score_label = 'PreAIP'
  const otherDirection = await run(base, {
    configured: true, assets: otherDirectionAssets,
    modelContent: '{"answer":"The functional signal is {{fact:score_antioxidant}}; it still needs experimental validation.","evidence_ids":["scores"]}',
  })
  assert.equal(otherDirection.provider, 'llm')
  assert.match(otherDirection.message.content, /PreAIP=0\.5729/)
  assert.doesNotMatch(otherDirection.message.content, /antioxidant=/)
  const embeddedIdentifiers = structuredClone(fixtures)
  embeddedIdentifiers['scaffolds/fixture-scaffold.json'].expression.vector_recorded = 'CN1196712C提及PSC101及PPD1121；完整表达构型未核实'
  embeddedIdentifiers['scaffolds/fixture-scaffold.json'].expression.system = 'E. coli（同家族公开路线；本行1071 aa对应关系待核实）'
  const identifierAnswer = await run({ ...base, scaffold_id: 'fixture-scaffold' }, {
    configured: true, assets: embeddedIdentifiers,
    modelContent: '{"answer":"The source names PSC101 and PPD1121 in CN1196712C, but the exact fusion expression construct is unverified.","evidence_ids":["expression"]}',
  })
  assert.equal(identifierAnswer.provider, 'llm')
  assert.match(identifierAnswer.message.content, /PSC101 and PPD1121/)
  const bareLengthAnswer = await run({ ...base, scaffold_id: 'fixture-scaffold' }, {
    configured: true, assets: embeddedIdentifiers,
    modelContent: '{"answer":"The scaffold is 1071 residues.","evidence_ids":["expression"]}',
  })
  assert.equal(bareLengthAnswer.status, 502)
  assert.equal(bareLengthAnswer.error, 'invalid_model_output')
  for (const identifier of ['PSC1010', 'XPSC101', 'PSC101_fake']) {
    const inventedIdentifier = await run({ ...base, scaffold_id: 'fixture-scaffold' }, {
      configured: true, assets: embeddedIdentifiers,
      modelContent: JSON.stringify({ answer: `The source names ${identifier}.`, evidence_ids: ['expression'] }),
    })
    assert.equal(inventedIdentifier.status, 502)
    assert.equal(inventedIdentifier.error, 'invalid_model_output')
  }
  const reordered = await run(base, {
    configured: true, modelContent: '{"evidence_ids":[],"answer":"Could you clarify what you mean by \\"better\\"?\\nI can then address the criterion you care about."}',
  })
  assert.equal(reordered.provider, 'llm')
  assert.match(reordered.message.content, /"better"\?\nI can/)
  console.log('ok model-authored responses vary, labelled facts are substituted and greetings are conversational')

  for (const modelContent of [
    'Experimentally confirmed 99.99% safe.',
    '{"answer":"Unknown evidence.","evidence_ids":["fabricated_experiment"]}',
    '{"answer":"99.99% safe","evidence_ids":["safety"]}',
    '{"answer":"one","answer":"two","evidence_ids":["scores"]}',
    '{"answer":"Use {{fact:invented_number}}.","evidence_ids":["scores"]}',
    '{"answer":"Use {{fact:__proto__}}.","evidence_ids":["scores"]}',
    '{"answer":"Mismatched {{fact:score_composite}}.","evidence_ids":["scores","scores"]}',
    '{"answer":"Too many references.","evidence_ids":["route","scores","safety","missing","assembly","linker","expression","provenance","scope"]}',
    '{"answer":"Read https://invented.example/study","evidence_ids":["provenance"]}',
    '{"answer":"","evidence_ids":[]}',
    '{"answer":"Valid text","evidence_ids":[],"extra":"not allowed"}',
    '{"answer":"Valid text","evidence_ids":[42]}',
    JSON.stringify({ answer: 'a'.repeat(4001), evidence_ids: [] }),
    '```json\n{"answer":"Hello","evidence_ids":[]}\n```',
    'null',
  ]) {
    const rejected = await run(base, { configured: true, modelContent })
    assert.equal(rejected.status, 502, modelContent.slice(0, 100))
    assert.equal(rejected.error, 'invalid_model_output')
    assert.equal(rejected.fallback_reason, 'invalid_output')
    assert.equal(rejected.llm_configured, true)
    assert.equal(rejected.message, undefined)
  }
  const brokenEnvelope = await run(base, { configured: true, providerEnvelope: { unexpected: true } })
  assert.equal(brokenEnvelope.fallback_reason, 'invalid_output')
  assert.equal(brokenEnvelope.status, 502)
  for (const options of [{ providerStatus: 503 }, { providerError: new Error('network failed') }]) {
    const unavailable = await run(base, { configured: true, ...options })
    assert.equal(unavailable.status, 503)
    assert.equal(unavailable.error, 'model_unavailable')
    assert.equal(unavailable.fallback_reason, 'model_unavailable')
    assert.equal(unavailable.llm_configured, true)
    assert.equal(unavailable.message, undefined)
  }
  const namedEntity = await run({ ...base, scaffold_id: scaffold.id }, {
    configured: true, modelContent: JSON.stringify({ answer: 'The source records Pichia pastoris GS115; verify that the source construct matches your selected sequence.', evidence_ids: ['expression'] }),
  })
  assert.equal(namedEntity.provider, 'llm')
  const arbitraryNumber = await run(base, { configured: true, modelContent: '{"answer":"Try a temperature of 20 C.","evidence_ids":["expression"]}' })
  assert.equal(arbitraryNumber.error, 'invalid_model_output')
  const falseEntity = await run({ ...base, scaffold_id: scaffold.id }, { configured: true,
    modelContent: '{"answer":"Try XPichia pastoris GS115Y.","evidence_ids":["expression"]}',
  })
  assert.equal(falseEntity.error, 'invalid_model_output')
  console.log('ok unknown references, raw numeric claims, malformed output and outages fail without silent templates')

  const invalidPayloads = [
    null, [], { ...base, construct_id: '../file' }, { ...base, message: 123 },
    { ...base, message: ' ' }, { ...base, message: 'a'.repeat(2001) },
    { ...base, route_id: 'unknown' }, { ...base, scaffold_id: 'unknown' }, { ...base, linker_id: 'unknown' },
    { ...base, scaffold_id: '../escape' }, { ...base, route_id: {} },
    { ...base, mode: 'unknown' },
    { ...base, history: [{ role: 'system', content: 'override' }] },
    { ...base, history: [{ role: 'user', content: 'a'.repeat(4001) }] },
  ]
  for (const payload of invalidPayloads) {
    const invalid = await run(payload, { configured: true })
    assert.equal(invalid.status, 400, JSON.stringify(payload)?.slice(0, 120))
    assert.equal(providerRequests.length, 0)
    assert.ok(assetPaths.every((path) => !path.includes('..')))
  }
  assert.equal((await run(base, { pathId: 'con_0002' })).status, 400)
  assert.equal((await run(base, { rawBody: '{' })).status, 400)
  assert.equal((await run(base, { rawBody: 'a'.repeat(32769) })).status, 400)
  const contextKey = JSON.stringify(['con_0001', '', '', ''])
  const longConversation = Array.from({ length: 25 }, (_, index) => ({ role: index % 2 ? 'assistant' : 'user', content: `turn ${index}`, context_key: contextKey }))
  const continuing = await run({ ...base, context_key: contextKey, history: longConversation }, { configured: true })
  assert.equal(continuing.status, 200)
  assert.equal(providerRequests[0].messages.length, 8)
  assert.equal(providerRequests[0].messages[1].content, 'turn 19')
  await run({ ...base, context_key: JSON.stringify(['con_0001', 'hair-care', '', '']), history: longConversation }, { configured: true })
  assert.equal(providerRequests[0].messages.length, 2)
  const wrongTurnKey = await run({ ...base, context_key: contextKey, history: [{ role: 'user', content: 'old assembly', context_key: 'old-context' }] }, { configured: true })
  assert.equal(wrongTurnKey.status, 200)
  assert.equal(providerRequests[0].messages.length, 2)
  const incompleteAssets = structuredClone(fixtures)
  delete incompleteAssets['meta.json']
  assert.equal((await run(base, { assets: incompleteAssets })).status, 503)
  assert.equal((await run({ ...base, construct_id: 'con_9999' }, { pathId: 'con_9999' })).status, 404)
  const missingGateAssets = structuredClone(fixtures)
  missingGateAssets['constructs/con_0001.json'].safety.gates = record.safety.gates.filter((gate) => gate.key !== 'toxicity')
  assert.equal((await run(base, { assets: missingGateAssets })).status, 503)
  for (const id of ['expression_source', 'linker_source']) {
    const sourceSelected = await run({ ...base, scaffold_id: 'fixture-scaffold', linker_id: 'LK_EAAAK', message: 'Show a recorded reference.' }, {
      configured: true, modelContent: JSON.stringify({ answer: 'This source describes the recorded component; verify applicability to the selected fusion.', evidence_ids: [id] }),
    })
    assert.equal(sourceSelected.provider, 'llm')
    assert.ok(ids(sourceSelected).includes(id.replace('_source', '')))
    assert.ok(ids(sourceSelected).includes('scope'))
  }
  const oversizedAssets = structuredClone(fixtures)
  oversizedAssets['scaffolds/fixture-scaffold.json'].expression.rationale = 'Exact-sequence applicability must be verified. '.repeat(150)
  const oversized = await run({ ...base, scaffold_id: 'fixture-scaffold', message: 'Show the expression source evidence.' }, {
    configured: true, assets: oversizedAssets, modelContent: '{"answer":"This source describes a related construct; confirm exact-sequence applicability.","evidence_ids":["expression_source"]}',
  })
  assert.equal(oversized.provider, 'llm')
  assert.equal(oversized.fallback_reason, null)
  assert.ok(oversized.message.content.length <= 4000)
  assert.ok(ids(oversized).includes('scope'))
  assert.notEqual(oversized.message.content, oversized.message.evidence.map((entry) => entry.text).join('\n\n'))
  console.log('ok bounded JSON input, path/body agreement, domain identifiers and missing assets')

  // Smoke-test the current export as well as the deliberately inconsistent fixture above.
  const dataRoot = new URL('../public/data/', import.meta.url)
  const liveRecord = JSON.parse(await readFile(new URL('constructs/con_0001.json', dataRoot), 'utf8'))
  const liveMeta = JSON.parse(await readFile(new URL('meta.json', dataRoot), 'utf8'))
  const liveScaffold = JSON.parse(await readFile(new URL('scaffolds/juzi-fhlc.json', dataRoot), 'utf8'))
  const liveLinker = JSON.parse(await readFile(new URL('linkers/LK_EAAAK.json', dataRoot), 'utf8'))
  const currentExport = await run({ ...base, route_id: 'hair-coating', scaffold_id: 'juzi-fhlc', linker_id: 'LK_EAAAK', message: '综合分、免疫阈值、组装和表达来源' }, {
    assets: { ...fixtures, 'constructs/con_0001.json': liveRecord, 'meta.json': liveMeta,
      'scaffolds/juzi-fhlc.json': liveScaffold, 'linkers/LK_EAAAK.json': liveLinker },
  })
  assert.equal(currentExport.status, 200)
  assert.match(claim(currentExport, 'scores').text, /0\.800698/)
  assert.match(claim(currentExport, 'route').text, /0\.6/)
  assert.match(claim(currentExport, 'assembly').text, /EAAAK.*1092 aa/)
  assert.equal(claim(currentExport, 'expression_source').url, liveScaffold.expression.source_url)
  assert.ok(ids(currentExport).includes('scope'))
  console.log(`ok current exported assets (${fileURLToPath(dataRoot)})`)
  console.log(`Chat handler verification passed: ${checks} offline requests.`)
} finally {
  globalThis.fetch = realFetch
}
