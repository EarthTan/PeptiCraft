/**
 * Renders the chat answer component and checks the Markdown subset it must support.
 *
 * The AI answer used to be printed as one preformatted string, so lists, emphasis and tables
 * arrived as literal punctuation. This check fixes the contract in both directions: the
 * constructs a model actually writes must become elements, and raw HTML or script URLs must
 * not. It uses Vite's module loader so the component is exercised exactly as the browser
 * builds it, without adding a test runner.
 */
import assert from 'node:assert/strict'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createServer } from 'vite'
import react from '@vitejs/plugin-react'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = dirname(dirname(fileURLToPath(import.meta.url)))

const answer = `好的！如果你愿意，我可以继续帮你梳理当前候选的具体情况，例如：
- 解释各项预测评分与筛查阈值的含义
- 分析当前骨架与连接肽组合的已知依据和证据缺口
- 总结表达记录及其适用限制
- 明确下一步最需要补充的验证信息

你也可以直接告诉我想重点了解哪一项。

### 下一步

| 项目 | 状态 |
| --- | --- |
| 表达 | 未验证 |

\`composite\` 是**排序分**，*不是*成功率。

第一行
第二行

<script>alert(1)</script>
[x](javascript:alert(1))
`

const server = await createServer({
  configFile: false,
  root,
  logLevel: 'silent',
  appType: 'custom',
  plugins: [react()],
  resolve: { alias: { '@': join(root, 'src') } },
  server: { middlewareMode: true, hmr: false },
})

try {
  const { ChatMarkdown } = await server.ssrLoadModule('/src/components/chat-markdown.tsx')
  const markup = renderToStaticMarkup(createElement(ChatMarkdown, { content: answer }))
  const checks = {
    'unordered list is an element': /<ul[\s>]/u.test(markup),
    'all four list items render': (markup.match(/<li[\s>]/gu) ?? []).length === 4,
    'bold text renders': /<strong[^>]*>排序分<\/strong>/u.test(markup),
    'italic text renders': /<em[^>]*>不是<\/em>/u.test(markup),
    'heading renders': /<h3[^>]*>下一步<\/h3>/u.test(markup),
    'table renders': /<table[\s>]/u.test(markup) && /<td[^>]*>未验证<\/td>/u.test(markup),
    'inline code renders': /<code[^>]*>composite<\/code>/u.test(markup),
    'single newlines become breaks': (markup.match(/<br\s*\/?>/gu) ?? []).length === 1,
    'raw HTML is not emitted': !/<script/iu.test(markup),
    'script URLs are dropped': !/javascript:/iu.test(markup),
    'prose is preserved': markup.includes('明确下一步最需要补充的验证信息'),
  }
  const failed = Object.entries(checks).filter(([, ok]) => !ok).map(([name]) => name)
  assert.deepEqual(failed, [], `Markdown rendering checks failed: ${failed.join(', ')}`)
  console.log(`markdown-check: ${Object.keys(checks).length} checks passed`)
} finally {
  await server.close()
}
