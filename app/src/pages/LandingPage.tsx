import { useCallback, useEffect, useRef, type ReactNode } from "react"
import { Link } from "react-router-dom"
import { ArrowRight, Beaker, Database, FlaskConical, Info, Shield, TrendingUp } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { ErrorState } from "@/components/ui/error-state"
import { LoadingBlock } from "@/components/ui/loading-state"
import { fetchLinkers, fetchPipeline, fetchReference, fetchScaffolds } from "@/api"
import type { LinkerView, PipelineView, ReferenceData, ScaffoldSummary } from "@/api/types"
import { distinctForms, formLabel, formatCount, groupScaffoldsByRoute, materialFormLabels } from "@/lib/derive"
import { DIRECTION_STATUS_LABEL, iconFor } from "@/lib/display"
import { useAsync } from "@/lib/useAsync"
import "./homepage.css"

// Display typography only. API fields, identifiers and scientific calculations stay unchanged.
function prose(text: string) {
  let seen = false
  return text.replace(/[\u2014\u2013]/g, () => {
    if (seen) { seen = false; return ":" }
    seen = true
    return "-"
  })
}

export default function LandingPage() {
  const load = useCallback(async () => {
    const [reference, pipeline, scaffolds, linkers] = await Promise.all([
      fetchReference(), fetchPipeline(), fetchScaffolds(), fetchLinkers(),
    ])
    return { reference, pipeline, scaffolds, linkers }
  }, [])
  const { data, loading, error, reload } = useAsync(load, [])

  return (
    <div className="homepage">
      <ScrollScene className="home-hero gradient-hero" id="overview">
        <div className="hero-art" aria-hidden="true">
          <div className="hero-protein hero-protein-left"><ProteinImage /></div>
          <div className="hero-protein hero-protein-right"><ProteinImage /></div>
        </div>
        <div className="home-container hero-content">
          <Badge variant="accent" className="mb-6 px-4 py-1.5 text-sm">DKU iGEM 2026</Badge>
          <h1>PeptiCraft: From peptide screening to<br /><span className="gradient-accent-text">traceable protein candidates</span></h1>
          <p className="hero-description">PeptiCraft brings peptide screening, scaffold selection and linker choice into one workflow for skin-care and biomaterial fusion-protein design, with expression-system guidance.</p>
          <div className="home-actions">
            <Link to="/builder?new=1"><Button variant="gradient" size="lg"><FlaskConical />Explore the Builder<ArrowRight /></Button></Link>
            <Link to="/library?tab=peptides"><Button variant="outline" size="lg"><Database />Browse Library</Button></Link>
          </div>
          <p className="hero-protein-caption">Our iGEM Top 1 candidate · con_0317 · Predicted structure</p>
          <div className="home-highlights">
            {loading && <LoadingBlock label="Reading the library" />}
            {error && <ErrorState error={error} onRetry={reload} compact />}
            {data && <HighlightBar {...data} />}
          </div>
        </div>
      </ScrollScene>

      <ScrollScene className="home-modules" id="modules">
        <div className="home-container">
          <SectionHeading number="1" eyebrow="Platform" title="Three Core Modules" description="Browse the library, build a construct and explore the supporting research." />
          <ThreeModules />
          <div className="source-notes">
            <details><summary>Where do the peptide sequences come from?</summary><p>The project records 20.2 million short-peptide entries from metagenomic datasets, UniProt, UniRef90, PDB and archived snapshots. Source identifiers and versions accompany the records.</p><a href="https://github.com/EarthTan/PeptiCraft/blob/main/docs/PeptiCraft-Documentation/02-Data-Assets-and-Data-Forms.md" target="_blank" rel="noreferrer">Read the data-source documentation <ArrowRight size={15} /></a></details>
            <details><summary>What is recorded for each scaffold?</summary><p>Eight scaffold clusters are curated from public patents and supporting literature, with sequence records, E1-E5 evidence grades, available expression-system details and application recommendations. Evidence is tied to its reported sequence and use.</p><Link to="/library?tab=scaffold">Explore the scaffold evidence <ArrowRight size={15} /></Link></details>
          </div>
        </div>
      </ScrollScene>

      <ScrollScene className="home-applications" id="scenarios">
        <div className="home-container">
          <SectionHeading number="2" eyebrow="scenario-driven" title="5 Application Scenarios" description="Choose an application scenario to explore suitable scaffolds and its screening profile." />
          {loading && <LoadingBlock label="Loading application scenarios" />}
          {data && <ApplicationRoutes reference={data.reference} scaffolds={data.scaffolds} />}
        </div>
      </ScrollScene>

      <section className="home-section home-functions" id="functions">
        <div className="home-container">
          <SectionHeading number="3" eyebrow="Functions" title="Four Function Directions" description="Antioxidant, antibacterial, anti-inflammatory and anti-melanin deposition. Combine directions in the Builder." />
          <div className="home-function-grid">
            {(data?.reference.directions ?? []).map(direction => {
              const Icon = iconFor(direction.icon)
              const description = prose(direction.description.replace(" rather than measuring anti-inflammatory activity", ""))
              return <article className="home-card" key={direction.id}>
                <div className="home-icon" style={{ backgroundColor: `${direction.color}15`, color: direction.color }}><Icon size={24} /></div>
                <h3>{direction.name}</h3>
                <Badge variant={direction.status === "ready" ? "accent" : "warning"}>{DIRECTION_STATUS_LABEL[direction.status] ?? direction.status}</Badge>
                <p>{description}</p>
                <div className="home-small">{direction.construct_count} constructs · {formatCount(direction.precursor_count)} peptide records</div>
                {direction.status === "wip" && <p className="home-wip">Screening in progress</p>}
              </article>
            })}
          </div>
        </div>
      </section>

      <section className="home-section home-principles" id="principles">
        <div className="home-container">
          <SectionHeading number="4" eyebrow="Core Design" title="Three Core Principles" description="Function and application fit do matter, but safety comes first." />
          <div className="home-three-grid">
            {[
              { icon: Shield, title: "Safety-First · Single Veto", text: "Toxicity, haemolysis or immunogenicity: any assessed metric that fails its safety gate removes the candidate. Unassessed metrics are labelled." },
              { icon: Beaker, title: "Each Metric Used Once", text: "Functional scores select the candidate pool. The next stage compares candidates using their developability signals." },
              { icon: TrendingUp, title: "Data-Driven Weights", text: "Weights are derived from the Winsorized standard deviation of each component in the candidate pool, then applied under the selected scenario's profile." },
            ].map(item => <article className="home-card" key={item.title}><div className="home-icon"><item.icon size={24} /></div><h3>{item.title}</h3><p>{item.text}</p></article>)}
          </div>
        </div>
      </section>

      <section className="home-section home-boundaries" aria-labelledby="boundaries-title">
        <div className="home-container">
          <div className="boundaries-heading"><span className="home-eyebrow">Scope & next steps</span><h2 id="boundaries-title">What PeptiCraft Can and Cannot Tell You</h2><p>PeptiCraft combines prediction tools into a screening pipeline. Its results identify promising candidates for experimental testing.</p></div>
          <div className="home-three-grid">
            {[
              { title: "Ranking is not probability", text: "Scores compare candidates within the screening workflow. They indicate relative priority for testing." },
              { title: "Some parts are still in progress", text: "Anti-inflammatory and anti-melanin screening remain in progress. Model coverage and supporting evidence vary across candidates." },
              { title: "Fusion protein construction must be validated with wet-lab results", text: "Expression, folding, activity and safety need to be tested using the final fusion construct." },
            ].map(item => <article className="boundary-card" key={item.title}><h3>{item.title}</h3><p>{item.text}</p></article>)}
          </div>
        </div>
      </section>

      <section className="home-section home-pipeline" id="pipeline">
        <div className="home-container">
          <SectionHeading number="5" eyebrow="Methods & tools" title="Four-Round Screening Pipeline" description="From functional screening to candidate assembly, with the tools used at each step." />
          {loading && <LoadingBlock label="Loading pipeline" />}
          <div className="pipeline-stages">{(data?.pipeline.included ?? []).map(stage => <article className="pipeline-arrow" key={stage.round}>
            <svg className="pipeline-arrow-shape" viewBox="0 0 1000 320" preserveAspectRatio="none" aria-hidden="true">
              <path d="M20 1 H980 Q999 1 999 20 V219 Q999 229 984 232 L512 317 Q500 320 488 317 L16 232 Q1 229 1 219 V20 Q1 1 20 1 Z" vectorEffect="non-scaling-stroke" />
            </svg>
            <div className="pipeline-round">R{stage.round}</div>
            <div className="pipeline-body"><div className="pipeline-stage-heading"><h3>{stage.name}</h3><span className="home-small">{stage.duration}</span></div>
              <p>{[
                "Rank peptides by functional direction: AnOxPePred for antioxidant activity, iMFP-LG for antimicrobial and anti-inflammatory signals, and TIPred for tyrosinase inhibition.",
                "Screen toxicity with ToxinPred3, haemolysis with HemoPI2 and MHC-I presentation with MHCflurry. Assessed scores must satisfy the applicable gates.",
                "Compare BepiPred-3.0, TemStaPro, SoDoPE and pLM4CPPs signals using the scenario-specific composite ranking.",
                "Combine selected peptides, scaffolds and linkers into construct sequences for review in the Builder.",
              ][stage.round - 1] ?? prose(stage.description)}</p>
              <div className="pipeline-flow">{prose(stage.input)} <ArrowRight size={16} /> {prose(stage.output)}</div>
              <div className="pipeline-tools">{stage.tools.map(tool => <span key={tool}>{prose(tool)}</span>)}</div>
              <details className="pipeline-details"><summary>Method details</summary><p>{prose(stage.description)}</p></details>
            </div>
          </article>)}</div>
          {data?.pipeline && <div className="pipeline-footnotes"><details><summary>How is the composite calculated?</summary><p>{prose(data.pipeline.composite_definition)}</p></details><details><summary>Structure prediction: Rounds 5-8</summary><p>{prose(data.pipeline.excluded_note)}</p></details></div>}
        </div>
      </section>

      <section className="home-section home-cta"><div className="home-container"><h2>Your fusion protein design<br /><span className="gradient-accent-text">starts right now</span></h2><p>Choose a scenario and function, then build your candidate.</p><div className="home-actions"><Link to="/builder?new=1"><Button variant="gradient" size="lg">Build a Candidate<ArrowRight /></Button></Link><Link to="/library?tab=peptides"><Button variant="outline" size="lg">Explore the Library</Button></Link></div></div></section>
      <Sponsors />
    </div>
  )
}

/** Sticky hold uses native scrolling, including trackpads, touch and keyboard navigation.
 * Tall scenarios stick only after their last row has entered the viewport. */
function ScrollScene({ children, className, id }: { children: ReactNode; className: string; id: string }) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const content = ref.current
    if (!content) return
    const resize = () => content.style.setProperty("--scene-top", `${Math.min(64, window.innerHeight - content.offsetHeight)}px`)
    const observer = new ResizeObserver(resize)
    observer.observe(content)
    window.addEventListener("resize", resize)
    resize()
    let lastY = window.scrollY
    let downward = false
    const onScroll = () => { downward = window.scrollY > lastY; lastY = window.scrollY }
    const onScrollEnd = () => {
      if (!downward || window.innerWidth < 768 || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return
      const scene = content.parentElement
      if (!scene) return
      const start = scene.getBoundingClientRect().top + window.scrollY
      const holdStart = start + content.offsetHeight - window.innerHeight
      const holdEnd = start + scene.offsetHeight - window.innerHeight
      const progress = (window.scrollY - holdStart) / Math.max(1, holdEnd - holdStart)
      if (progress > .55 && progress < 1) window.scrollTo({ top: start + scene.offsetHeight - 64, behavior: "smooth" })
    }
    window.addEventListener("scroll", onScroll, { passive: true })
    window.addEventListener("scrollend", onScrollEnd)
    return () => {
      observer.disconnect()
      window.removeEventListener("resize", resize)
      window.removeEventListener("scroll", onScroll)
      window.removeEventListener("scrollend", onScrollEnd)
    }
  }, [])
  return <section className="intro-scene" id={id}><div ref={ref} className={`scene-content ${className}`}>{children}</div></section>
}

function SectionHeading({ number, eyebrow, title, description }: { number: string; eyebrow: string; title: string; description: string }) {
  return <header className="home-section-heading"><span className="section-number gradient-accent-text" aria-hidden="true">{number}</span><span className="home-eyebrow">{eyebrow}</span><div className="numbered-title"><h2><span>{title}</span></h2></div><p><span className="heading-description">{description}</span></p></header>
}

function ProteinImage() {
  // ViewBox aligns the protein's alpha bounds without stretching or modifying the source PNG.
  return <svg viewBox="384 332 648 1100" role="presentation"><image href="/brand/con_0317.png" width="1388" height="1478" /></svg>
}

function StatTip({ label, children }: { label: string; children: ReactNode }) {
  return <span className="stat-tip"><span className="stat-tip-trigger" tabIndex={0} aria-label={label}>i</span><span className="home-tip-panel" role="tooltip">{children}</span></span>
}

function InfoTip({ label, children }: { label: string; children: ReactNode }) {
  return <details className="home-info-tip"><summary aria-label={label}><Info size={18} aria-hidden="true" /></summary><div className="home-tip-panel" role="note">{children}</div></details>
}

function RollingNumber({ value }: { value: string }) {
  return <span className="rolling-number" aria-label={value}><span aria-hidden="true">{Array.from(value).map((character, index) => /\d/.test(character) ? <span className="rolling-digit" key={index}><span className="digit-reel" style={{ animationDelay: `${index * 55}ms` }}>{Array.from({ length: 20 }, (_, i) => <span key={i}>{i % 10}</span>)}<span>{character}</span></span></span> : <span key={index}>{character}</span>)}</span></span>
}

function HighlightBar({ reference, scaffolds, linkers, pipeline }: { reference: ReferenceData; scaffolds: ScaffoldSummary[]; linkers: LinkerView[]; pipeline: PipelineView }) {
  const searchSpace = Math.max(0, ...reference.directions.map(d => d.precursor_count))
  const tools = [...new Set(pipeline.included.filter(s => s.round < 4).flatMap(s => s.tools))]
  const highlights = [
    { value: formatCount(searchSpace), label: "Peptide records", href: "#modules", note: "Sequences from metagenomic datasets, UniProt, UniRef90, PDB and archived snapshots." },
    { value: String(reference.directions.reduce((sum, d) => sum + d.construct_count, 0)), label: "Scored constructs", href: "/library?tab=peptides", note: "Browse the screened construct records in the Library." },
    { value: String(scaffolds.length), label: "Scaffold clusters", href: "/library?tab=scaffold", note: scaffolds.map(s => s.short_name).join(" · ") },
    { value: String(reference.directions.length), label: "Function directions", href: "#functions", note: reference.directions.map(d => d.name).join(" · ") },
    { value: String(tools.length), label: "Prediction tools", href: "#pipeline", note: tools.join(" · ") },
    { value: String(linkers.length), label: "Linkers", href: "/library?tab=linker", note: linkers.map(l => l.name).join(" · ") },
  ]
  return <div className="highlight-grid">{highlights.map(item => <div className="highlight-item" key={item.label}>
    {item.href.startsWith("/") ? <Link to={item.href} className="highlight-link"><RollingNumber value={item.value} /><span>{item.label}</span></Link> : <a href={item.href} className="highlight-link"><RollingNumber value={item.value} /><span>{item.label}</span></a>}
    <StatTip label={`About ${item.label}`}><strong>{item.label}</strong><p>{item.note}</p></StatTip>
  </div>)}</div>
}

function ThreeModules() {
  const features = [
    { icon: Database, title: "Construct, Scaffold and Linker Library", description: "Browse screened constructs, scaffold sequences and linkers, with source references and supporting evidence.", href: "/library?tab=peptides", link: "Browse the Library" },
    { icon: FlaskConical, title: "Construct Builder", description: "Choose a peptide, scaffold and linker to obtain a complete construct sequence, with expression-system recommendations where supported by the available evidence.", href: "/builder?new=1", link: "Build a construct" },
    { icon: Shield, title: "Research-Based Explanations", description: "Explore the research behind each candidate, including prediction results, component choices and limitations.", href: "/library?tab=peptides", link: "Explore the evidence" },
  ]
  return <div className="home-three-grid">{features.map(feature => <article className="home-card module-card" key={feature.title}><div className="home-icon"><feature.icon size={24} /></div><h3>{feature.title}</h3><p>{feature.description}</p><Link className="home-text-link" to={feature.href}>{feature.link}<ArrowRight size={17} /></Link></article>)}</div>
}

function ApplicationRoutes({ reference, scaffolds }: { reference: ReferenceData; scaffolds: ScaffoldSummary[] }) {
  const labels = materialFormLabels(reference)
  const byRoute = groupScaffoldsByRoute(scaffolds)
  return <div className="scenario-list">{reference.routes.map(route => {
    const Icon = iconFor(route.icon)
    const admitted = byRoute.get(route.id) ?? []
    const forms = distinctForms(admitted)
    return <article className="scenario-row" key={route.id}>
      <div className="scenario-title"><div className="home-icon"><Icon size={32} strokeWidth={2} /></div><h3>{route.name}</h3><Badge variant="outline">{route.barrier_label}</Badge>{route.emerging && <Badge variant="warning">Evidence still building</Badge>}</div>
      <div className="scenario-content"><p>{prose(route.contact_interface)}</p><div className="scenario-tags"><span>{admitted.length} scaffold{admitted.length === 1 ? "" : "s"}</span><span>immuno ≤ {route.screening.immunogenicity_threshold.toFixed(2)}</span>{forms.map(form => <span key={form}>{formLabel(labels, form)}</span>)}</div>
        <details className="scenario-method"><summary>Screening profile & immuno parameter</summary><p><strong>MHCflurry 2.0:</strong> predicts MHC-I presentation. Higher presentation scores indicate stronger predicted presentation under the evaluated conditions.</p><p><strong>Project cutoff: ≤ {route.screening.immunogenicity_threshold.toFixed(2)}.</strong> {route.screening.immunogenicity_threshold <= 0.35 ? "A tighter project cutoff is used for exposed-tissue contact." : "The project cutoff follows the scenario-specific exposure profile."}</p><p>These scenario cutoffs are project screening choices. The MHCflurry paper describes the prediction model; it does not establish these cutoffs as safety limits.</p><a href="https://pubmed.ncbi.nlm.nih.gov/32711842/" target="_blank" rel="noreferrer">MHCflurry 2.0 paper</a><p><strong>Immune exposure:</strong> {prose(route.immune_exposure)}</p><p><strong>Profile:</strong> cell penetration {route.screening.cpp_weight}, solubility {route.screening.solubility_weight}, thermal stability {route.screening.thermal_stability_weight}.</p><p><strong>Additional checks:</strong> {route.screening.extra_gates.join(", ")}.</p>{route.emerging_note && <p>{prose(route.emerging_note)}</p>}</details>
      </div>
      <InfoTip label={`${route.name}: scaffold names`}><strong>Scaffolds for {route.name}</strong>{admitted.length ? <ul>{admitted.map(s => <li key={s.id}><Link to={`/library/scaffold/${encodeURIComponent(s.id)}`}>{s.short_name}</Link></li>)}</ul> : <p>No scaffold is currently assigned to this scenario.</p>}</InfoTip>
    </article>
  })}</div>
}

function Sponsors() {
  return <section className="home-sponsors"><div className="home-container"><h2>Our University & Sponsors</h2><div className="sponsor-grid">
    <div className="sponsor-tile sponsor-dark"><img src="/sponsors/dku.png" alt="Duke Kunshan University" loading="lazy" /><p>Wang Cai Biochemistry Lab</p></div>
    <div className="sponsor-tile"><img src="/sponsors/snapgene-igem.png" alt="SnapGene + iGEM" loading="lazy" /><p>Sponsor · SnapGene</p></div>
    <div className="sponsor-tile sponsor-dark"><img src="/sponsors/dku-ine.png" alt="DKU Innovation and Entrepreneurship" loading="lazy" /><p>DKU Innovation and Entrepreneurship</p></div>
    </div><p className="home-license">© 2026 DKU iGEM · PeptiCraft. Source code: <a href="https://github.com/EarthTan/PeptiCraft" target="_blank" rel="noreferrer">GitHub</a> · <a href="https://github.com/EarthTan/PeptiCraft/blob/main/LICENSE" target="_blank" rel="noreferrer">Apache-2.0</a>. Third-party logos belong to their respective owners.</p></div></section>
}
