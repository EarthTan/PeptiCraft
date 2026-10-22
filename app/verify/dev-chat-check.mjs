/**
 * Exercise the real Vite development server and production Pages handler over HTTP.
 * No model credentials, database or external network are needed.
 * Run from app/: node verify/dev-chat-check.mjs
 */
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import http from 'node:http'
import { once } from 'node:events'
import { fileURLToPath } from 'node:url'
import { createServer } from 'vite'

const appRoot = fileURLToPath(new URL('..', import.meta.url))
const configFile = fileURLToPath(new URL('../vite.config.ts', import.meta.url))
const variables = ['VITE_STATIC', 'VITE_API_PROXY_TARGET', 'npm_lifecycle_event', 'LLM_BASE_URL', 'LLM_API_KEY', 'LLM_MODEL']
const originalEnvironment = Object.fromEntries(variables.map((key) => [key, process.env[key]]))
const servers = []
let proxy
let provider
let providerMode = 'answer'
const providerRequests = []

async function startDevelopmentServer() {
  const server = await createServer({
    root: appRoot,
    configFile,
    logLevel: 'error',
    server: { host: '127.0.0.1', port: 0, strictPort: true, open: false },
  })
  servers.push(server)
  await server.listen()
  return `http://127.0.0.1:${server.httpServer.address().port}`
}

function rawPost(origin, body, headers) {
  return new Promise((resolve, reject) => {
    const request = http.request(`${origin}/api/constructs/con_0001/chat`, {
      method: 'POST', headers: { 'Content-Type': 'application/json', ...headers },
    }, (response) => {
      let text = ''
      response.setEncoding('utf8')
      response.on('data', (chunk) => { text += chunk })
      response.on('end', () => resolve({ status: response.statusCode, text }))
    })
    request.on('error', reject)
    request.end(body)
  })
}

async function chatRequest(origin, selection) {
  const response = await fetch(`${origin}/api/constructs/con_0001/chat`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(selection),
  })
  assert.equal(response.headers.get('content-type'), 'application/json')
  assert.equal(response.headers.get('cache-control'), 'no-store')
  return { status: response.status, body: await response.json() }
}

async function closeHttpServer(server) {
  if (!server) return
  const closed = new Promise((resolve) => server.close(resolve))
  server.closeAllConnections()
  await closed
}

try {
  // Empty server values override any personal .env.local, keeping this check offline.
  process.env.LLM_BASE_URL = ''
  process.env.LLM_API_KEY = ''
  process.env.LLM_MODEL = ''
  process.env.VITE_STATIC = '1'
  process.env.npm_lifecycle_event = 'dev'
  const origin = await startDevelopmentServer()
  const selection = {
    construct_id: 'con_0001', route_id: 'hair-coating',
    scaffold_id: 'juzi-fhlc', linker_id: 'LK_EAAAK',
    message: '综合分、免疫阈值、组装和表达来源',
  }
  const statusResponse = await fetch(`${origin}/api/chat/status`)
  assert.equal(statusResponse.status, 200)
  assert.equal(statusResponse.headers.get('cache-control'), 'no-store')
  assert.deepEqual(await statusResponse.json(), { llm_configured: false, model: null })
  for (const mode of ['ai', undefined]) {
    const unavailable = await chatRequest(origin, { ...selection, mode })
    assert.equal(unavailable.status, 503)
    assert.equal(unavailable.body.error, 'llm_not_configured')
    assert.equal(unavailable.body.llm_configured, false)
    assert.equal(unavailable.body.message, undefined)
    assert.equal(unavailable.body.provider, undefined)
  }
  console.log('ok unconfigured AI status is explicit and AI requests never become template replies')

  const recordResult = await chatRequest(origin, { ...selection, mode: 'record' })
  assert.equal(recordResult.status, 200)
  const answer = recordResult.body
  const evidence = (id) => answer.message.evidence.find((item) => item.id === id)
  const scaffold = JSON.parse(await readFile(new URL('../public/data/scaffolds/juzi-fhlc.json', import.meta.url), 'utf8'))
  assert.equal(answer.provider, 'template')
  assert.equal(answer.llm_configured, false)
  assert.equal(answer.fallback_reason, null)
  assert.equal(answer.context_key, JSON.stringify(['con_0001', 'hair-coating', 'juzi-fhlc', 'LK_EAAAK']))
  assert.match(evidence('route').text, /0\.6/)
  assert.match(evidence('scores').text, /0\.800698/)
  assert.match(evidence('assembly').text, /EAAAK.*1092 aa/)
  assert.equal(evidence('expression_source').url, scaffold.expression.source_url)
  console.log('ok explicit record mode retains route, assembly and source evidence without AI')

  for (const headers of [{ 'Content-Length': '32769' }, { 'Transfer-Encoding': 'chunked' }]) {
    const oversized = await rawPost(origin, 'x'.repeat(32769), headers)
    assert.equal(oversized.status, 413)
    assert.equal(JSON.parse(oversized.text).detail, 'request body is too large')
  }
  const invalid = await rawPost(origin, JSON.stringify({ construct_id: 'con_0002', message: 'overview' }))
  assert.equal(invalid.status, 400)
  assert.equal(JSON.parse(invalid.text).detail, 'path and body construct ids must match')
  console.log('ok ordinary/chunked body limits and handler error statuses')

  // This is an actual loopback HTTP provider. Vite resolves its address from the same
  // server-side environment path used for a real model; no handler fetch is replaced.
  const firstQuestion = '请解释这个候选的综合分应该如何使用。'
  const nextQuestion = '那接下来应该优先补什么验证？'
  provider = http.createServer(async (request, response) => {
    const chunks = []
    for await (const chunk of request) chunks.push(chunk)
    const body = JSON.parse(Buffer.concat(chunks).toString('utf8'))
    providerRequests.push({ url: request.url, authorization: request.headers.authorization, body })
    if (providerMode === 'unavailable') {
      response.writeHead(503, { 'Content-Type': 'application/json' })
      response.end(JSON.stringify({ error: 'local provider unavailable' }))
      return
    }
    const question = body.messages.at(-1)?.content.split('\n\nQUESTION\n').at(-1)
    const content = providerMode === 'invalid'
      ? { answer: '实验已确认其安全率为99.99%。', evidence_ids: ['scores'] }
      : question === firstQuestion
        ? { answer: '综合分在这里用于候选排序，{{fact:composite}}。不能把它解读为成功率。建议结合缺失测量决定下一步。', evidence_ids: ['scores'] }
        : { answer: '接着刚才的排序解释，下一步优先补齐缺失的安全评估，再讨论融合构建体是否值得实验验证。当前排序依据仍是{{fact:composite}}。', evidence_ids: ['scores', 'missing'] }
    response.writeHead(200, { 'Content-Type': 'application/json' })
    response.end(JSON.stringify({ choices: [{ message: { content: JSON.stringify(content) } }] }))
  })
  provider.listen(0, '127.0.0.1')
  await once(provider, 'listening')
  process.env.LLM_BASE_URL = `http://127.0.0.1:${provider.address().port}/v1`
  process.env.LLM_API_KEY = 'offline-test-key'
  process.env.LLM_MODEL = 'local-chat-mock'

  const configuredResponse = await fetch(`${origin}/api/chat/status`)
  assert.equal(configuredResponse.status, 200)
  assert.deepEqual(await configuredResponse.json(), { llm_configured: true, model: 'local-chat-mock' })
  const contextKey = JSON.stringify(['con_0001', 'hair-coating', 'juzi-fhlc', 'LK_EAAAK'])
  const first = await chatRequest(origin, { ...selection, mode: 'ai', context_key: contextKey, message: firstQuestion })
  assert.equal(first.status, 200)
  assert.equal(first.body.provider, 'llm')
  assert.equal(first.body.llm_configured, true)
  assert.equal(first.body.model, 'local-chat-mock')
  assert.equal(first.body.fallback_reason, null)
  assert.equal(first.body.context_key, contextKey)
  assert.match(first.body.message.content, /^综合分在这里用于候选排序/)
  assert.match(first.body.message.content, /composite=0\.800698/)
  assert.doesNotMatch(first.body.message.content, /\{\{|\}\}/)
  assert.ok(first.body.message.evidence.some((item) => item.id === 'scores'))
  const scope = first.body.message.evidence.find((item) => item.id === 'scope')
  assert.ok(scope)
  assert.ok(!first.body.message.content.includes(scope.text), 'scope must be evidence metadata, not a repeated canned paragraph')

  const history = [
    { role: 'user', content: firstQuestion, context_key: contextKey },
    { role: 'assistant', content: first.body.message.content, context_key: contextKey },
  ]
  const next = await chatRequest(origin, {
    ...selection, mode: 'ai', context_key: contextKey, message: nextQuestion, history,
  })
  assert.equal(next.status, 200)
  assert.equal(next.body.provider, 'llm')
  assert.notEqual(next.body.message.content, first.body.message.content)
  assert.match(next.body.message.content, /^接着刚才的排序解释/)
  assert.match(next.body.message.content, /composite=0\.800698/)
  assert.equal(providerRequests.length, 2)
  for (const received of providerRequests) {
    assert.equal(received.url, '/v1/chat/completions')
    assert.equal(received.authorization, 'Bearer offline-test-key')
    assert.equal(received.body.model, 'local-chat-mock')
    assert.equal(received.body.messages[0].role, 'system')
    assert.match(received.body.messages.at(-1).content, /CURRENT CONTEXT/)
    assert.match(received.body.messages.at(-1).content, /AVAILABLE EVIDENCE/)
    assert.match(received.body.messages.at(-1).content, /FACTS/)
  }
  assert.equal(providerRequests[0].body.messages.length, 2)
  assert.ok(providerRequests[0].body.messages.at(-1).content.endsWith(firstQuestion))
  assert.equal(providerRequests[1].body.messages.length, 4)
  assert.deepEqual(providerRequests[1].body.messages.slice(1, 3), history.map(({ role, content }) => ({ role, content })))
  assert.ok(providerRequests[1].body.messages.at(-1).content.endsWith(nextQuestion))
  assert.notEqual(providerRequests[0].body.messages.at(-1).content, providerRequests[1].body.messages.at(-1).content)
  console.log('ok real HTTP model calls produce distinct answers, preserve history and substitute verified numeric facts')

  const configuredRecords = await chatRequest(origin, { ...selection, mode: 'record' })
  assert.equal(configuredRecords.status, 200)
  assert.equal(configuredRecords.body.provider, 'template')
  assert.equal(configuredRecords.body.llm_configured, true)
  assert.equal(providerRequests.length, 2, 'explicit records must bypass the configured provider')
  for (const [mode, status, error] of [
    ['unavailable', 503, 'model_unavailable'],
    ['invalid', 502, 'invalid_model_output'],
  ]) {
    providerMode = mode
    const failed = await chatRequest(origin, { ...selection, mode: 'ai', message: firstQuestion })
    assert.equal(failed.status, status)
    assert.equal(failed.body.error, error)
    assert.equal(failed.body.llm_configured, true)
    assert.equal(failed.body.provider, undefined)
    assert.equal(failed.body.message, undefined)
  }
  assert.equal(providerRequests.length, 4)
  console.log('ok provider failures and unverified output return explicit errors without template fallback')

  proxy = http.createServer((request, response) => {
    assert.ok(['/api/constructs/con_0001/chat', '/api/chat/status'].includes(request.url))
    response.writeHead(202, { 'Content-Type': 'application/json', 'X-Proxy-Check': 'python-path' })
    response.end(JSON.stringify({ provider: 'python-proxy' }))
  })
  proxy.listen(0, '127.0.0.1')
  await once(proxy, 'listening')
  process.env.VITE_API_PROXY_TARGET = `http://127.0.0.1:${proxy.address().port}`
  // The api mode must bypass static chat even with a stale parent-shell VITE_STATIC value.
  process.env.npm_lifecycle_event = 'dev:api'
  const apiOrigin = await startDevelopmentServer()
  const forwarded = await fetch(`${apiOrigin}/api/constructs/con_0001/chat`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(selection),
  })
  assert.equal(forwarded.status, 202)
  assert.equal(forwarded.headers.get('x-proxy-check'), 'python-path')
  assert.equal((await forwarded.json()).provider, 'python-proxy')
  const forwardedStatus = await fetch(`${apiOrigin}/api/chat/status`)
  assert.equal(forwardedStatus.status, 202)
  assert.equal(forwardedStatus.headers.get('x-proxy-check'), 'python-path')
  assert.equal((await forwardedStatus.json()).provider, 'python-proxy')
  console.log('ok dev:api continues to proxy chat and status to the backend')
  console.log('Development chat HTTP verification passed.')
} finally {
  await Promise.all(servers.map((server) => server.close()))
  await closeHttpServer(proxy)
  await closeHttpServer(provider)
  for (const key of variables) {
    if (originalEnvironment[key] === undefined) delete process.env[key]
    else process.env[key] = originalEnvironment[key]
  }
}
