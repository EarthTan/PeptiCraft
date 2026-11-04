import { Check } from "lucide-react"
import "./builder-journey.css"

const LABELS = ["Route", "Function", "Scaffold", "Linker", "Results"]

export function BuilderJourney({ step, route, functions, scaffold, linker, onBack }: {
  step: number
  route?: string
  functions: string[]
  scaffold?: string
  linker?: string
  onBack: (step: number) => void
}) {
  const peptide = functions.join(" + ")
  // Assembly defaults are only introduced when the corresponding selection step is reached.
  const shownScaffold = step >= 3 ? scaffold : undefined
  const shownLinker = step >= 4 ? linker : undefined
  return <section className="builder-journey" aria-label="Build progress and assembly">
    <div className="builder-journey-inner">
      <nav aria-label="Construct builder progress">
        <p className="sr-only" aria-live="polite">Step {step} of 5: {LABELS[step - 1]}</p>
        <ol className="journey-steps">{LABELS.map((label, offset) => {
          const index = offset + 1
          const completed = index < step
          const current = index === step
          return <li key={label} className={`journey-step ${completed ? "is-complete" : current ? "is-current" : "is-pending"}`}>
            <span className="journey-track">{completed ? <button type="button" className="journey-dot cursor-pointer" aria-label={`Return to step ${index}: ${label}`} onClick={() => onBack(index)}><Check size={14} strokeWidth={2.5} aria-hidden="true" /></button> : <span className="journey-dot" aria-current={current ? "step" : undefined}>{index}</span>}</span>
            {completed ? <button type="button" className="journey-label" onClick={() => onBack(index)} aria-label={`Go back to ${label}`}><strong>{label}</strong></button> : <div className="journey-label" aria-current={current ? "step" : undefined}><strong>{label}</strong></div>}
          </li>
        })}</ol>
      </nav>
      <div className="assembly-preview" aria-label="Current fusion protein assembly" aria-live="polite" aria-atomic="true">
        <p className={`assembly-route ${route ? "is-filled" : ""}`}>{route ?? "Application route"}</p>
        <div className="assembly-parts">
          <div className={`assembly-part assembly-scaffold ${shownScaffold ? "is-filled" : ""}`}><span>Scaffold</span>{shownScaffold && <strong>{shownScaffold}</strong>}</div>
          <div className={`assembly-linker ${shownLinker ? "is-filled" : ""}`}><span className="assembly-linker-line" aria-hidden="true" /><span>Linker</span>{shownLinker && <strong>{shownLinker}</strong>}</div>
          <div className={`assembly-part assembly-peptide ${peptide ? "is-filled" : ""}`}><span>Peptide</span>{peptide && <strong>{peptide}</strong>}</div>
        </div>
      </div>
    </div>
  </section>
}
