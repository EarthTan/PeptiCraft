import { memo } from "react"
import Markdown, { type Components } from "react-markdown"
import remarkBreaks from "remark-breaks"
import remarkGfm from "remark-gfm"
import { cn } from "@/lib/utils"

/**
 * Markdown rendering for an answer written by the model.
 *
 * The model writes prose with lists, emphasis and occasional tables, but the answer used to be
 * printed as one preformatted string. This renders that Markdown inside the same bubble.
 *
 * Two constraints shape the element mapping. Record-mode answers do not pass through here:
 * their field names contain underscores that CommonMark would read as emphasis, so they stay
 * plain. And a model answer is untrusted text, so raw HTML is skipped and link targets are
 * limited to http(s); no answer can add markup or a `javascript:` link to the page.
 *
 * Sizes are relative (`em`) because the same bubble is rendered at two text sizes, in the
 * inline conversation bar and in the larger side panel.
 */

const httpUrlOnly = (url: string): string => (/^https?:\/\//iu.test(url) ? url : "")
const remarkPlugins = [remarkGfm, remarkBreaks]

const components: Components = {
  p: ({ children }) => <p className="mb-2 break-words last:mb-0">{children}</p>,
  strong: ({ children }) => <strong className="font-semibold text-primary-900">{children}</strong>,
  em: ({ children }) => <em className="italic">{children}</em>,
  del: ({ children }) => <del className="text-gray-500 line-through">{children}</del>,
  a: ({ children, href }) => (
    /^https?:\/\//iu.test(href ?? "")
      ? (
        <a
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          className="break-words text-primary-700 underline decoration-primary-300 underline-offset-2 hover:decoration-primary-600"
        >
          {children}
        </a>
      )
      : <span>{children}</span>
  ),
  // Remote images would either break the narrow bubble or load an unknown host; the evidence
  // catalog already links its sources.
  img: () => null,
  ul: ({ children }) => (
    <ul className="my-2 list-disc space-y-1 pl-4 first:mt-0 last:mb-0 marker:text-accent-600">{children}</ul>
  ),
  ol: ({ children }) => (
    <ol className="my-2 list-decimal space-y-1 pl-4 first:mt-0 last:mb-0 marker:text-accent-600">{children}</ol>
  ),
  li: ({ children }) => (
    <li className="break-words pl-0.5 [&>p:last-child]:mb-0 [&>ul]:my-1 [&>ol]:my-1">{children}</li>
  ),
  h1: ({ children }) => (
    <h1 className="mb-1.5 mt-3 text-[1.15em] font-semibold leading-snug text-primary-900 first:mt-0">{children}</h1>
  ),
  h2: ({ children }) => (
    <h2 className="mb-1.5 mt-3 text-[1.1em] font-semibold leading-snug text-primary-900 first:mt-0">{children}</h2>
  ),
  h3: ({ children }) => (
    <h3 className="mb-1 mt-2.5 text-[1.05em] font-semibold leading-snug text-primary-900 first:mt-0">{children}</h3>
  ),
  h4: ({ children }) => (
    <h4 className="mb-1 mt-2 text-[1em] font-semibold leading-snug text-primary-900 first:mt-0">{children}</h4>
  ),
  h5: ({ children }) => (
    <h5 className="mb-1 mt-2 text-[1em] font-semibold leading-snug text-primary-900 first:mt-0">{children}</h5>
  ),
  h6: ({ children }) => (
    <h6 className="mb-1 mt-2 text-[1em] font-semibold leading-snug text-primary-900 first:mt-0">{children}</h6>
  ),
  blockquote: ({ children }) => (
    <blockquote className="my-2 border-l-2 border-accent-300 pl-3 text-gray-600">{children}</blockquote>
  ),
  hr: () => <hr className="my-3 border-gray-200" />,
  pre: ({ children }) => (
    <pre className="my-2 overflow-x-auto rounded-md border border-gray-200 bg-white p-2.5 font-mono text-[0.85em] leading-relaxed [&_code]:border-0 [&_code]:bg-transparent [&_code]:p-0">
      {children}
    </pre>
  ),
  code: ({ children }) => (
    <code className="rounded border border-gray-200 bg-white px-1 py-0.5 font-mono text-[0.9em]">{children}</code>
  ),
  table: ({ children }) => (
    <div className="my-2 overflow-x-auto">
      <table className="w-full border-collapse text-left align-top">{children}</table>
    </div>
  ),
  th: ({ children }) => (
    <th className="border-b border-gray-300 px-2 py-1 text-left align-top font-semibold text-primary-900">{children}</th>
  ),
  td: ({ children }) => (
    <td className="break-words border-b border-gray-100 px-2 py-1 align-top">{children}</td>
  ),
}

export const ChatMarkdown = memo(function ChatMarkdown({
  content,
  className,
}: {
  content: string
  className?: string
}) {
  return (
    <div
      className={cn(
        "chat-markdown min-w-0 break-words [&>*:first-child]:mt-0 [&>*:last-child]:mb-0",
        className,
      )}
    >
      <Markdown
        remarkPlugins={remarkPlugins}
        components={components}
        skipHtml
        urlTransform={httpUrlOnly}
      >
        {content}
      </Markdown>
    </div>
  )
})
