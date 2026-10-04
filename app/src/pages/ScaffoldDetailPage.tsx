import { useCallback, type ReactNode } from "react"
import { Link, useParams } from "react-router-dom"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { ErrorState } from "@/components/ui/error-state"
import { LoadingBlock } from "@/components/ui/loading-state"
import { Notice } from "@/components/ui/notice"
import {
  ArrowRight,
  Building2,
  ChevronRight,
  Dna,
  ExternalLink,
  FlaskConical,
  Layers,
  Microscope,
  ScrollText,
} from "lucide-react"
import { fetchReference, fetchScaffold, fetchScaffolds } from "@/api"
import type { ScaffoldSummary } from "@/api/types"
import { formLabel, materialFormLabels } from "@/lib/derive"
import { useAsync } from "@/lib/useAsync"

/**
 * Scaffold detail.
 *
 * Two things this page does that its predecessor could not. It names the fields the interface
 * declares but the source dataset does not carry — `unavailable_fields` comes from the
 * service, so a reader can tell an empty block apart from a broken one. And it renders the
 * patent variant sequences and the experiments that back the evidence label, both of which
 * live in the imported table and were previously shown as counts without their content.
 */
export default function ScaffoldDetailPage() {
  const { id } = useParams<{ id: string }>()

  const load = useCallback(async () => {
    if (!id) throw new Error("No scaffold identifier in the route.")
    const [detail, reference, all] = await Promise.all([
      fetchScaffold(id),
      fetchReference(),
      fetchScaffolds(),
    ])
    return { detail, reference, others: all.filter((item) => item.id !== id) }
  }, [id])

  const { data, loading, error, reload } = useAsync(load, [id])

  if (loading) {
    return (
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        <LoadingBlock label="Loading scaffold record" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        <ErrorState error={error} onRetry={reload} />
        <div className="text-center mt-6">
          <Link to="/library">
            <Button variant="outline">
              <ChevronRight className="w-4 h-4 rotate-180" />
              Back to Library
            </Button>
          </Link>
        </div>
      </div>
    )
  }

  if (!data) return null
  const { detail, reference, others } = data

  const categoryLabel =
    reference.categories.find((category) => category.id === detail.category)?.label ??
    detail.category

  const admittedBy = reference.routes.filter((route) => detail.route_ids.includes(route.id))

  return (
    <div className="min-h-[calc(100vh-8rem)]">
      <section className="bg-surface-alt border-b border-gray-200">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
          <Link
            to="/library"
            className="text-sm text-primary-500 hover:text-primary-700 flex items-center gap-1 mb-4 w-fit"
          >
            <ChevronRight className="w-4 h-4 rotate-180" />
            Back to Library
          </Link>

          <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
            <div className="min-w-0">
              <Badge variant="accent" className="mb-3">
                Scaffold
              </Badge>
              <h1 className="text-2xl sm:text-3xl font-bold text-primary-900">{detail.name}</h1>
              {detail.short_name && detail.short_name !== detail.name && (
                <p className="text-sm text-primary-600 mt-1">{detail.short_name}</p>
              )}
              {detail.species && (
                <p className="text-sm text-gray-500 italic mt-1">{detail.species}</p>
              )}
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {categoryLabel && (
                <Badge variant="outline" className="text-xs">
                  {categoryLabel}
                </Badge>
              )}
              {detail.length !== null && (
                <Badge variant="secondary" className="text-xs">
                  {detail.length} aa
                </Badge>
              )}
              {detail.max_evidence && (
                <Badge variant="accent" className="text-xs">
                  Evidence {detail.max_evidence}
                </Badge>
              )}
              <Link to="/builder">
                <Button variant="gradient" size="sm">
                  <FlaskConical className="w-4 h-4" />
                  Use in Builder
                </Button>
              </Link>
            </div>
          </div>

          <p className="text-sm text-gray-600 mt-4 leading-relaxed max-w-3xl">
            {detail.description}
          </p>
        </div>
      </section>

      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        {detail.unavailable_fields.length > 0 && (
          <Notice tone="caution" title="Fields the source dataset does not carry">
            The entry declares {detail.unavailable_fields.join(", ")}. The scaffold dataset has
            no column for these, so they are reported as absent rather than left blank — an
            empty card would not say whether the value is missing or the page is broken.
          </Notice>
        )}

        {!detail.has_sequence && (
          <Notice tone="warning" title="No sequence in the source table">
            This cluster has no amino-acid sequence in the scaffold dataset. It cannot
            contribute a backbone segment to a fused sequence, so a construct built on it has no
            assembled sequence to show.
          </Notice>
        )}

        <Card className="border-gray-200">
          <CardContent className="p-5">
            <h2 className="text-base font-semibold text-primary-900 mb-4 flex items-center gap-2">
              <Microscope className="w-4 h-4 text-primary-500" />
              Provenance
            </h2>
            <dl className="grid sm:grid-cols-2 gap-x-6 gap-y-4 text-sm">
              {detail.species && (
                <InfoRow icon={<Dna className="w-3.5 h-3.5" />} label="Source species" value={detail.species} />
              )}
              <InfoRow
                icon={<Building2 className="w-3.5 h-3.5" />}
                label="Applicant"
                value={detail.applicant}
                span
              />
              {detail.patent && (
                <InfoRow
                  icon={<ScrollText className="w-3.5 h-3.5" />}
                  label="Patent"
                  value={detail.patent}
                  span
                />
              )}
              {detail.product_use && (
                <InfoRow
                  icon={<Layers className="w-3.5 h-3.5" />}
                  label="Product / use"
                  value={detail.product_use}
                  span
                />
              )}
              {detail.potential_uses && (
                <InfoRow
                  icon={<ArrowRight className="w-3.5 h-3.5" />}
                  label="Potential applications"
                  value={detail.potential_uses}
                  span
                />
              )}
            </dl>

            {(detail.patent_source_url || detail.regulatory_evidence_url) && (
              <div className="flex flex-wrap gap-3 mt-4 pt-4 border-t border-gray-100">
                {detail.patent_source_url && (
                  <a
                    href={detail.patent_source_url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-xs text-primary-600 hover:text-primary-800 inline-flex items-center gap-1"
                  >
                    <ExternalLink className="w-3 h-3" />
                    Patent source
                  </a>
                )}
                {detail.regulatory_evidence_url && (
                  <a
                    href={detail.regulatory_evidence_url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-xs text-primary-600 hover:text-primary-800 inline-flex items-center gap-1"
                  >
                    <ExternalLink className="w-3 h-3" />
                    Regulatory evidence
                  </a>
                )}
              </div>
            )}
          </CardContent>
        </Card>

        {detail.sequences.length > 0 && (
          <Card className="border-gray-200">
            <CardContent className="p-5">
              <h2 className="text-base font-semibold text-primary-900 mb-1">
                Patent sequence variants
              </h2>
              <p className="text-xs text-gray-400 mb-4">
                {detail.sequences.length} sequence{detail.sequences.length > 1 ? "s" : ""} in this
                cluster. The longest is treated as the representative when a construct is
                assembled against it.
              </p>

              <div className="space-y-3">
                {detail.sequences.map((variant) => (
                  <div key={variant.sequence_id} className="rounded-lg border border-gray-200">
                    <div className="flex items-center justify-between gap-3 p-3 border-b border-gray-100">
                      <div className="min-w-0">
                        <span className="font-mono text-xs font-semibold text-primary-800">
                          {variant.sequence_id}
                        </span>
                        {variant.evidence_level && (
                          <Badge variant="outline" className="text-[10px] ml-2">
                            {variant.evidence_level}
                          </Badge>
                        )}
                        {variant.product_use && (
                          <p className="text-[11px] text-gray-400 mt-0.5">{variant.product_use}</p>
                        )}
                      </div>
                      <span className="font-mono text-xs text-gray-400 flex-shrink-0">
                        {variant.length} aa
                      </span>
                    </div>
                    <div className="p-3">
                      <div className="rounded-lg bg-surface-alt border border-gray-200 p-3">
                        <p className="font-mono text-[11px] text-primary-600 break-all leading-relaxed">
                          {variant.sequence}
                        </p>
                      </div>
                      <dl className="mt-3 space-y-1 text-[11px]">
                        {variant.regulatory_status && (
                          <div className="flex gap-2">
                            <dt className="text-gray-400 flex-shrink-0 w-28">Regulatory</dt>
                            <dd className="text-gray-600">{variant.regulatory_status}</dd>
                          </div>
                        )}
                        {variant.fasta_filename && (
                          <div className="flex gap-2">
                            <dt className="text-gray-400 flex-shrink-0 w-28">FASTA</dt>
                            <dd className="text-gray-600 font-mono break-all">
                              {variant.fasta_filename}
                            </dd>
                          </div>
                        )}
                        {variant.sha256 && (
                          <div className="flex gap-2">
                            <dt className="text-gray-400 flex-shrink-0 w-28">SHA256</dt>
                            <dd className="text-gray-500 font-mono break-all">{variant.sha256}</dd>
                          </div>
                        )}
                      </dl>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        <Card className="border-gray-200">
          <CardContent className="p-5">
            <h2 className="text-base font-semibold text-primary-900 mb-3">
              Where it is used
            </h2>

            {detail.application_tags.length > 0 && (
              <div className="mb-4">
                <p className="text-xs text-gray-400 uppercase tracking-wide mb-2">
                  Application tags in the source table
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {detail.application_tags.map((tag) => (
                    <Badge key={tag} variant="accent" className="text-xs">
                      {tag}
                    </Badge>
                  ))}
                </div>
              </div>
            )}

            {detail.material_forms.length > 0 && (
              <div className="mb-4">
                <p className="text-xs text-gray-400 uppercase tracking-wide mb-2">
                  Material forms
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {detail.material_forms.map((form) => (
                    <Badge key={form} variant="outline" className="text-xs">
                      {formLabel(materialFormLabels(reference), form)}
                    </Badge>
                  ))}
                </div>
                <p className="text-[11px] text-gray-400 mt-1.5">
                  Form is inferred from the product-use and result notes in the source database,
                  pending team confirmation.
                </p>
              </div>
            )}

            {admittedBy.length > 0 && (
              <div>
                <Separator className="mb-3" />
                <p className="text-xs text-gray-400 uppercase tracking-wide mb-2">
                  Reached from {admittedBy.length} application route
                  {admittedBy.length > 1 ? "s" : ""} in the Builder
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {admittedBy.map((route) => (
                    <Badge key={route.id} variant="outline" className="text-[11px]">
                      {route.name} · {route.barrier_label} · immuno ≤{" "}
                      {route.screening.immunogenicity_threshold.toFixed(2)}
                    </Badge>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {detail.experiments.length > 0 && (
          <Card className="border-gray-200">
            <CardContent className="p-5">
              <h2 className="text-base font-semibold text-primary-900 mb-3">
                Evidence behind the label
              </h2>
              <div className="space-y-3">
                {detail.experiments.map((experiment, index) => (
                  <div
                    key={index}
                    className="rounded-lg border border-gray-200 p-3.5 bg-surface-alt/40"
                  >
                    <div className="flex items-center gap-2 mb-2 flex-wrap">
                      {experiment.group && (
                        <Badge variant="secondary" className="text-[10px]">
                          {experiment.group}
                        </Badge>
                      )}
                      {experiment.level && (
                        <Badge variant="accent" className="text-[10px]">
                          {experiment.level}
                        </Badge>
                      )}
                    </div>
                    {experiment.specific_experiments && (
                      <p className="text-xs text-gray-700 leading-relaxed">
                        {experiment.specific_experiments}
                      </p>
                    )}
                    {experiment.principal_result && (
                      <p className="text-xs text-gray-500 leading-relaxed mt-1.5">
                        {experiment.principal_result}
                      </p>
                    )}
                    {experiment.evidence_limitations && (
                      <p className="text-[11px] text-amber-700 leading-relaxed mt-1.5">
                        Limit: {experiment.evidence_limitations}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        <Card className="border-gray-200">
          <CardContent className="p-5">
            <h2 className="text-base font-semibold text-primary-900 mb-3">
              Regulatory status
            </h2>

            <div className="flex items-center gap-2 mb-4">
              <span className="text-xs text-gray-400 uppercase tracking-wide">
                Highest evidence
              </span>
              <Badge variant="accent" className="text-xs">
                {detail.max_evidence ?? "—"}
              </Badge>
            </div>

            {detail.registrations.length > 0 ? (
              <ul className="space-y-2 mb-3">
                {detail.registrations.map((registration) => (
                  <li key={registration} className="flex gap-2.5 text-sm text-gray-600">
                    <span className="w-1.5 h-1.5 rounded-full bg-accent-500 flex-shrink-0 mt-1.5" />
                    <span className="leading-relaxed">{registration}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-gray-500 mb-3">
                No cleared registration traced for this cluster.
              </p>
            )}

            {detail.registration_note && (
              <p className="text-xs text-gray-400 leading-relaxed border-l-2 border-gray-200 pl-3">
                {detail.registration_note}
              </p>
            )}

            {detail.evidence_limits && (
              <p className="text-xs text-gray-400 leading-relaxed mt-3">
                {detail.evidence_limits}
              </p>
            )}
          </CardContent>
        </Card>

        {others.length > 0 && (
          <Card className="border-gray-200 bg-surface-alt/50">
            <CardContent className="p-5">
              <h2 className="text-base font-semibold text-primary-900 mb-3">Other scaffolds</h2>
              <div className="flex flex-wrap gap-2">
                {others.map((scaffold: ScaffoldSummary) => (
                  <Link key={scaffold.id} to={`/library/scaffold/${scaffold.id}`}>
                    <Button variant="outline" size="sm" className="text-xs">
                      {scaffold.short_name}
                      <ArrowRight className="w-3 h-3" />
                    </Button>
                  </Link>
                ))}
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  )
}

function InfoRow({
  icon,
  label,
  value,
  span,
}: {
  icon: ReactNode
  label: string
  value: string
  span?: boolean
}) {
  return (
    <div className={span ? "sm:col-span-2" : ""}>
      <dt className="flex items-center gap-1.5 text-xs text-gray-400 mb-1">
        {icon}
        {label}
      </dt>
      <dd className="text-sm text-gray-700 leading-relaxed">{value}</dd>
    </div>
  )
}
