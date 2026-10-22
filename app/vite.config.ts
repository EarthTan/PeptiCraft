import { readFile } from 'node:fs/promises'
import { resolve, sep } from 'node:path'
import type { IncomingMessage } from 'node:http'
import { defineConfig, loadEnv } from 'vite'
import type { Plugin } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

const MAX_CHAT_BODY_BYTES = 32_768

interface ChatEnvironment {
  LLM_BASE_URL?: string
  LLM_API_KEY?: string
  LLM_MODEL?: string
  ASSETS: { fetch(request: Request): Promise<Response> }
}

/** Bound both ordinary and chunked bodies without closing the response socket on overflow. */
async function readChatBody(request: IncomingMessage): Promise<Buffer | null> {
  if (Number(request.headers['content-length'] ?? 0) > MAX_CHAT_BODY_BYTES) {
    request.resume()
    return null
  }
  const chunks: Buffer[] = []
  let size = 0
  for await (const chunk of request.iterator({ destroyOnReturn: false })) {
    const bytes = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk)
    size += bytes.byteLength
    if (size > MAX_CHAT_BODY_BYTES) {
      request.resume()
      return null
    }
    chunks.push(bytes)
  }
  return Buffer.concat(chunks, size)
}

/** Run the production Pages handler against the same exported assets during static dev. */
function staticChat(environment: () => Pick<ChatEnvironment, 'LLM_BASE_URL' | 'LLM_API_KEY' | 'LLM_MODEL'>): Plugin {
  return {
    name: 'pepticraft-static-chat',
    apply: 'serve',
    configureServer(server) {
      // dev:api keeps the Python proxy even if a parent shell happened to set VITE_STATIC.
      if (process.env.VITE_STATIC !== '1' || process.env.npm_lifecycle_event === 'dev:api') return
      const publicRoot = resolve(server.config.root, 'public')
      const assets: ChatEnvironment['ASSETS'] = {
        async fetch(request) {
          const pathname = decodeURIComponent(new URL(request.url).pathname)
          const file = resolve(publicRoot, `.${pathname}`)
          if (!pathname.startsWith('/data/') || !pathname.endsWith('.json') || !file.startsWith(`${publicRoot}${sep}`)) {
            return new Response(null, { status: 404 })
          }
          try {
            return new Response(await readFile(file), { headers: { 'Content-Type': 'application/json' } })
          } catch {
            return new Response(null, { status: 404 })
          }
        },
      }
      server.middlewares.use(async (incoming, outgoing, next) => {
        try {
          const url = new URL(incoming.url ?? '/', server.resolvedUrls?.local[0] ?? 'http://127.0.0.1:5173')
          if (incoming.method === 'GET' && url.pathname === '/api/chat/status') {
            const settings = environment()
            const configured = [settings.LLM_BASE_URL, settings.LLM_API_KEY, settings.LLM_MODEL]
              .every((value) => Boolean(value?.trim()))
            outgoing.statusCode = 200
            outgoing.setHeader('Content-Type', 'application/json')
            outgoing.setHeader('Cache-Control', 'no-store')
            outgoing.end(JSON.stringify({ llm_configured: configured, model: configured ? settings.LLM_MODEL : null }))
            return
          }
          if (incoming.method !== 'POST') {
            next()
            return
          }
          if (!/^\/api\/constructs\/[^/]+\/chat\/?$/.test(url.pathname)) {
            next()
            return
          }
          const body = await readChatBody(incoming)
          if (body === null) {
            outgoing.statusCode = 413
            outgoing.setHeader('Content-Type', 'application/json')
            outgoing.setHeader('Cache-Control', 'no-store')
            outgoing.end(JSON.stringify({ error: 'bad_request', detail: 'request body is too large' }))
            return
          }
          const headers = new Headers()
          for (const [name, value] of Object.entries(incoming.headers)) {
            if (Array.isArray(value)) value.forEach((item) => headers.append(name, item))
            else if (value !== undefined) headers.set(name, value)
          }
          const { onRequestPost } = await server.ssrLoadModule('/functions/api/constructs/[id]/chat.ts') as {
            onRequestPost(context: { request: Request; env: ChatEnvironment }): Promise<Response>
          }
          const response = await onRequestPost({
            request: new Request(url, { method: 'POST', headers, body }),
            env: { ...environment(), ASSETS: assets },
          })
          outgoing.statusCode = response.status
          response.headers.forEach((value, name) => outgoing.setHeader(name, value))
          outgoing.end(Buffer.from(await response.arrayBuffer()))
        } catch (error) {
          next(error)
        }
      })
    },
  }
}

export default defineConfig(({ mode }) => {
  // Only these server-side settings reach the Pages handler. Never expose them as VITE_*.
  const environment = () => loadEnv(mode, import.meta.dirname, 'LLM_')
  return {
    plugins: [react(), tailwindcss(), staticChat(() => {
      const settings = environment()
      return {
        LLM_BASE_URL: settings.LLM_BASE_URL,
        LLM_API_KEY: settings.LLM_API_KEY,
        LLM_MODEL: settings.LLM_MODEL,
      }
    })],
    resolve: {
      alias: {
        '@': import.meta.dirname + '/src',
      },
    },
    // 本地调试用：固定 127.0.0.1:5173，端口被占用时直接报错而不是悄悄换端口
    server: {
      host: '127.0.0.1',
      port: 5173,
      strictPort: true,
      // Static chat is handled above. Other API calls and dev:api use the Python proxy.
      // 后端地址可用 VITE_API_PROXY_TARGET 覆盖（例如指向另一台机器上的服务）。
      proxy: {
        '/api': {
          target: process.env.VITE_API_PROXY_TARGET ?? 'http://127.0.0.1:8000',
          changeOrigin: false,
        },
      },
    },
  }
})
