/**
 * Response contract of the PeptiCraft service.
 *
 * Field names are copied verbatim from the service's Pydantic models, snake_case included.
 * That is deliberate: keeping one spelling from the database column through the SQL layer
 * to the React prop means a broken field shows up as a type error rather than as a silently
 * undefined value. Translating to camelCase here would reintroduce exactly the drift this
 * rewrite removes — `score_meta` used to be keyed differently from `scores`, and the pair
 * that mismatched was the pair nobody noticed.
 *
 * Every score is nullable. A null means the predictor did not cover this peptide, which is
 * not the same as a score of zero, and the interface renders the two differently.
 */

// ── Enumerations ────────────────────────────────────────────────────────────

export type EvidenceLevel = "E1" | "E2" | "E3" | "E4" | "E5"

export type BarrierTier = "tissue" | "breached" | "intact" | "non-living"

export type MaterialForm =
  | "lyophilized"
  | "self-assembled-hydrogel"
  | "injectable-gel"
  | "film"
  | "fiber"
  | "sheet"
  | "solution"

export type WeightTier = "high" | "medium" | "low"

/**
 * How a functional score may be read. `ranking_only` may order candidates but must never be
 * presented as a probability — the anti-inflammatory and anti-melanin predictors separate
 * "looks like a functional peptide" from "is anti-inflammatory", which makes their output a
 * ranking signal.
 */
export type ScoreSemantics = "probability" | "ranking_only" | "class_label"

/**
 * Where a construct's scaffold came from. Every stored construct currently binds a
 * placeholder, so `placeholder` is what the library shows today; `inferred` marks a scaffold
 * named at request time, which is a faithful assembly but not a pipeline result.
 */
export type BackboneBinding = "verified" | "placeholder" | "inferred"

export type SafetyVerdictKind = "clear" | "vetoed" | "borderline" | "indeterminate"

export type DirectionStatus = "ready" | "wip" | "empty"

export type ScoreGroup = "function" | "safety" | "developability"

// ── Shared value objects ────────────────────────────────────────────────────

export interface Paginated<T> {
  items: T[]
  total: number
  limit: number
  offset: number
}

export interface AppliedThreshold {
  value: number
  /** `tool` when the threshold ships with the predictor, `route` when it comes from the
   *  application route's screening profile, `project` for a platform-wide constant. */
  source: string
  note: string | null
}

export interface ScoreMeta {
  key: string
  tool: string
  measures: string
  higher_is_better: boolean
  group: ScoreGroup
  assessed: boolean
  semantics: ScoreSemantics
  applied_threshold: AppliedThreshold | null
  is_veto_gate: boolean
}

// ── Scores ──────────────────────────────────────────────────────────────────

export interface ConstructScores {
  antioxidant: number | null
  toxicity: number | null
  hemolysis: number | null
  immunogenicity: number | null
  b_cell_epitope: number | null
  thermal_stability: number | null
  solubility: number | null
  cpp: number | null
  composite: number | null
}

export interface SupplementaryScores {
  /** NetMHCIIpan percent rank, 0–100 where lower is a stronger binder. Not a probability. */
  immunogenicity_ii_pct_rank: number | null
  allergenicity: number | null
  aggregation_a3v: number | null
  anoxpepred_frs: number | null
  anoxpepred_chel: number | null
  aopxsvm: number | null
  amp_esm: number | null
  imfp_lg_amp: number | null
  imfp_lg_aip: number | null
  tipred: number | null
}

export interface DeliveryAdjustedScores {
  cpp: number | null
  solubility: number | null
  thermal_stability: number | null
  immunogenicity: number | null
  composite: number | null
  /** Normalised components and the weight each received, so a composite can be reproduced. */
  components: Record<string, number>
  weights: Record<string, number>
}

export interface SafetyGate {
  key: string
  label: string
  tool: string
  value: number | null
  threshold: number
  threshold_source: string
  /** `null` when the metric was not assessed: an unassessed metric does not eliminate. */
  passed: boolean | null
  borderline: boolean
  /** Whether a failure here eliminates the candidate. The service declares the set; the
   *  interface must not restate it, because the two drifted apart once already. */
  is_veto_gate: boolean
  /** Which side of the threshold fails. Every gate but the MHC-II percent rank fails on a
   *  high value; the rank fails on a low one, since a low percent rank is a stronger binder. */
  higher_is_better: boolean
  note: string | null
}

export interface SafetyVerdict {
  route_id: string | null
  immunogenicity_threshold: number | null
  verdict: SafetyVerdictKind
  gates: SafetyGate[]
  /** Gate keys with no measured value, rendered as `Not assessed` rather than as a pass. */
  unassessed: string[]
  vetoed_by: string[]
}

// ── Constructs ──────────────────────────────────────────────────────────────

export interface SequenceSegment {
  label: string
  sequence: string
  color: string
  type: "backbone" | "linker" | "peptide"
  /** False when the part exists in the assembly but its sequence is unknown. */
  available: boolean
}

export interface PeptideInfo {
  id: number
  sequence: string
  length: number
  source: string
  source_version: string
  source_accession: string | null
  seq_md5: string
}

export interface ConstructSummary {
  id: string
  name: string
  direction: string
  channel: "top" | "bottom"
  status: "passed" | "failed_safety" | "failed_score" | "WIP"
  rank: number | null
  direction_label: string
  peptide_sequence: string
  peptide_length: number
  backbone_name: string | null
  backbone_id: string | null
  linker_name: string | null
  functional_score: number | null
  /** The `peptide_enrichment.tool` key the value came from, verbatim. An identifier, not a
   *  label — the four directions use `anoxpepred-frs`, `amp-esm`, `imfp_lg_AIP` and `tipred`,
   *  which do not share a spelling convention because the pipeline wrote them. */
  functional_score_key: string
  /** The predictor's name for display. Print this, never the key. */
  functional_score_label: string
  /** How the functional score may be read. On the list row, not only on the detail, because
   *  the anti-inflammatory and anti-melanin scores order candidates and are not
   *  probabilities. */
  semantics: ScoreSemantics
  composite: number | null
  safety_verdict: SafetyVerdictKind | null
  backbone_binding: BackboneBinding
}

export interface ConstructDetail extends ConstructSummary {
  backbone_binding_note: string
  scaffold: ScaffoldSummary | null
  linker: LinkerView | null
  /** Where the linker came from. Reported separately from `backbone_binding_note` because
   *  the two are answered separately: an assembly can take its scaffold from the record and
   *  its linker from the request, or the other way round. */
  linker_note: string
  peptide: PeptideInfo
  /** The fused sequence, or null while the scaffold sequence is unknown. */
  full_sequence: string | null
  assembled_sequence_available: boolean
  segments: SequenceSegment[]
  scores: ConstructScores
  supplementary: SupplementaryScores
  score_meta: Record<string, ScoreMeta>
  delivery_scores: Record<string, DeliveryAdjustedScores>
  safety: SafetyVerdict
  unassessed_metrics: string[]
  assessed_flags: Record<string, boolean>
}

/** One candidate in a build, assembled against the scaffold and linker the build used.
 *
 *  `ConstructSummary` still holds in full, with one change of meaning: `backbone_name`,
 *  `backbone_binding` and `linker_name` describe what this build assembled the row with —
 *  the caller's choice for whichever of the two was named, the row's stored value otherwise. */
export interface BuiltConstruct extends ConstructSummary {
  /** Backbone + linker + peptide. Null when any segment has no known sequence — which is what
   *  a placeholder-binding row returns from a build that named no scaffold. */
  full_sequence: string | null
  /** Residue count of `full_sequence`. The gap between it and `peptide_length` is what the
   *  build added, which is the figure that makes the scaffold and linker visible on a card. */
  fused_length: number | null
  assembled_sequence_available: boolean
  segments: SequenceSegment[]
}

export interface BuildCounts {
  clear: number
  borderline: number
  vetoed: number
  indeterminate: number
  /** How many candidates the tally covers: the whole match, not `items.length`. A tally over
   *  the returned slice would describe where the page fell rather than the candidate set. */
  ranked: number
  /** Candidates with no composite under the route. Ranked last rather than treated as zero. */
  without_composite: number
}

export interface BuildResult {
  route: DeliveryRoute
  /** The scaffold every candidate was assembled against, or null when none was named and each
   *  row fell back to its stored binding. */
  scaffold: ScaffoldSummary | null
  /** The linker every candidate was assembled with, or null when none was named and each row
   *  fell back to the linker its own stored row records — in which case the rows can differ
   *  from one another, which is what `linker_name` on each row reports. `source_table` on it
   *  says which of the two linker tables answered. */
  linker: LinkerView | null
  /** Where the scaffold assignment came from. A build reproduces a real scaffold with a real
   *  linker and peptide, but the pairing is the caller's choice, not a pipeline result. */
  binding_note: string
  /** Where the linker came from, stated separately because the two decisions are made
   *  separately. Naming a linker changes the sequence and nothing else: the candidate set,
   *  the scores and the ranking are identical to a build that names none. */
  linker_note: string
  /** What the assembled sequence does not support: every score beside a candidate describes
   *  the peptide alone, because no predictor ran on the fusion protein. */
  scope_note: string
  directions: string[]
  /** Candidates per direction before `limit`. A direction with none appears as 0. */
  totals: Record<string, number>
  total: number
  counts: BuildCounts
  items: BuiltConstruct[]
  limit: number
  offset: number
}

// ── Reference data ──────────────────────────────────────────────────────────

export interface DirectionCounts {
  total: number
  top: number
  bottom: number
  by_status: Record<string, number>
}

export interface FunctionDirection {
  id: string
  name: string
  icon: string
  color: string
  description: string
  precursor_count: number
  construct_count: number
  status: DirectionStatus
  counts: DirectionCounts
}

export interface RouteScreening {
  cpp_weight: WeightTier
  solubility_weight: WeightTier
  thermal_stability_weight: WeightTier
  immunogenicity_threshold: number
  threshold_note: string
  extra_gates: string[]
}

export interface DeliveryRoute {
  id: string
  name: string
  icon: string
  application_tag: string
  contact_interface: string
  barrier_tier: BarrierTier
  barrier_label: string
  immune_exposure: string
  screening: RouteScreening
  application_techniques: string[]
  scaffold_ids: string[]
  emerging: boolean
  emerging_note: string | null
}

export interface PipelineStage {
  round: number
  name: string
  input: string
  output: string
  duration: string
  tools: string[]
  description: string
}

export interface PipelineView {
  included: PipelineStage[]
  excluded: PipelineStage[]
  composite_definition: string
  excluded_note: string
}

export interface ToolDefinition {
  key: string
  tool: string
  measures: string
  higher_is_better: boolean
  group: ScoreGroup
  semantics: ScoreSemantics
  threshold: number | null
  threshold_source: string | null
  threshold_note: string | null
  coverage_note: string | null
  is_veto_gate: boolean
}

export interface ScaffoldCategoryView {
  id: string
  label: string
  scaffold_ids: string[]
}

export interface MaterialFormOption {
  id: MaterialForm
  label: string
}

export interface EvidenceLevelOption {
  id: EvidenceLevel
  label: string
  description: string
}

export interface ReferenceData {
  directions: FunctionDirection[]
  routes: DeliveryRoute[]
  tools: ToolDefinition[]
  evidence_levels: EvidenceLevelOption[]
  material_forms: MaterialFormOption[]
  categories: ScaffoldCategoryView[]
}

// ── Scaffolds ───────────────────────────────────────────────────────────────

export interface ScaffoldSequence {
  sequence_id: string
  fasta_filename: string | null
  length: number
  sequence: string
  sha256: string | null
  product_use: string | null
  regulatory_status: string | null
  evidence_level: EvidenceLevel | null
}

export interface ScaffoldExperiment {
  group: string | null
  level: string | null
  specific_experiments: string | null
  principal_result: string | null
  result_location: string | null
  evidence_limitations: string | null
}

export interface ScaffoldSummary {
  id: string
  name: string
  short_name: string
  category: string | null
  applicant: string
  patent: string | null
  length: number | null
  species: string | null
  sequence_count: number
  application_tags: string[]
  route_ids: string[]
  material_forms: MaterialForm[]
  max_evidence: EvidenceLevel | null
  has_sequence: boolean
}

export interface ScaffoldDetail extends ScaffoldSummary {
  description: string
  registrations: string[]
  registration_note: string | null
  product_use: string | null
  potential_uses: string | null
  evidence_limits: string | null
  patent_source_url: string | null
  regulatory_evidence_url: string | null
  sequences: ScaffoldSequence[]
  experiments: ScaffoldExperiment[]
  /** Declared by the interface but absent from the source dataset. Listed by
   *  `unavailable_fields`, so the page can say so instead of rendering an empty card. */
  lab: string | null
  common_name: string | null
  accession: string | null
  reference: string | null
  characteristics: string[] | null
  properties: { label: string; value: string }[] | null
  expression_notes: string | null
  unavailable_fields: string[]
}

// ── Linkers ─────────────────────────────────────────────────────────────────

export interface LinkerUnit {
  unit: string
  count: number
  label: string
}

export interface LinkerView {
  id: string
  name: string
  sequence: string
  length: number
  rigidity: "Flexible" | "Mostly Flexible" | "Balanced" | "Mostly Rigid" | "Rigid"
  source_table: string
  unit_composition: LinkerUnit[]
  description: string | null
  reference: string | null
}

export interface LinkerDetail extends LinkerView {
  flexible_count: number | null
  rigid_count: number | null
  rigidity_index: number | null
  priority_reason: string | null
}

// ── Analysis and chat ───────────────────────────────────────────────────────

export interface AnalysisBlock {
  id: string
  type:
    | "safety"
    | "peptide_origin"
    | "linker_rationale"
    | "expression_strategy"
    | "comparison"
    | "risk"
  title: string
  icon: string
  content: string
  collapsed: boolean
  /** Field paths the prose derives from, so every number in the text is traceable. */
  citations: string[]
}

export interface AnalysisResponse {
  construct_id: string
  provider: string
  route_id: string | null
  blocks: AnalysisBlock[]
}

export interface ChatAction {
  label: string
  action: string
  variant: string
}

export interface ChatMessage {
  id: string
  role: "user" | "assistant"
  content: string
  timestamp: string
  actions: ChatAction[]
}

export interface ChatResponse {
  provider: string
  construct_id: string
  message: ChatMessage
  suggested_questions: string[]
  llm_configured: boolean
}

// ── Health ──────────────────────────────────────────────────────────────────

export interface HealthResponse {
  ok: boolean
  database: {
    /**
     * Which source answered: `postgres`, `sqlite` or `auto`. `sqlite` means the service is
     * serving the bundled fixture, which is hand-made sample data rather than pipeline output.
     */
    backend: string
    host: string
    database: string
    server?: string
    now?: string
    /** Why the fallback took over. Present only when it did. */
    fallback_reason?: string
    /** The service's own statement of what the fixture is. Present only when it is in use. */
    note?: string
  }
  analysis_provider: string
  error?: string
  detail?: string
}
