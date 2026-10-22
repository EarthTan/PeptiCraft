import { ExternalLink } from "lucide-react"

import type { ScaffoldExpression } from "@/api/types"

/**
 * The expression-system recommendation behind a scaffold.
 *
 * The value is the source's, not ours: the scaffold sheet states a host, the vector the patent
 * records, the vector it recommends, and the basis for that recommendation, one set per patent
 * sequence. Nothing here is derived from the peptide, so the block sits beside the assembly
 * rather than inside the score panels — it says what to build the construct in, not how good
 * the construct is.
 *
 * The strings stay in the language the source wrote them in. `无明确推荐` and `宿主 DE3 状态
 * 需确认` are conclusions with a scope, and a translation that reads `no recommendation` and
 * `confirm the host` would look like an editorial note rather than a finding.
 */
export function ExpressionBlock({
  expression,
  variantLabel = true,
}: {
  expression: ScaffoldExpression
  /** Whether to name the sequence the values describe. On the Results page the assembly uses
   *  one variant and the reader needs to know which; inside that variant's own card the
   *  identifier is already on screen. */
  variantLabel?: boolean
}) {
  const rows: [string, string | null][] = [
    ["Host", expression.system],
    ["Vector in the source", expression.vector_recorded],
    ["Recommended vector", expression.vector_recommended],
  ]

  return (
    <div>
      <dl className="space-y-1.5 text-xs">
        {rows.map(([label, value]) => (
          <div key={label} className="flex gap-3">
            <dt className="text-gray-400 flex-shrink-0 w-40">{label}</dt>
            <dd className="text-gray-700 leading-relaxed break-words">{value ?? "—"}</dd>
          </div>
        ))}
      </dl>

      {expression.rationale && (
        <p className="text-[11px] text-gray-500 leading-relaxed mt-3 pt-3 border-t border-gray-100">
          {expression.rationale}
        </p>
      )}

      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-2">
        {expression.source_url && (
          <a
            href={expression.source_url}
            target="_blank"
            rel="noreferrer"
            className="text-[11px] text-primary-600 hover:text-primary-800 inline-flex items-center gap-1"
          >
            <ExternalLink className="w-3 h-3" />
            Expression source
          </a>
        )}
        {variantLabel && expression.sequence_id && (
          <span className="text-[11px] text-gray-400 font-mono break-all">
            stated for {expression.sequence_id}
          </span>
        )}
      </div>
    </div>
  )
}
