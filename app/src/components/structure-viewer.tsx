import { useEffect, useRef, useState } from "react"
import { Box, Download, Loader2, RotateCcw, TriangleAlert } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { findStructure, structureEnabled, structureFileUrl } from "@/api/structure"
import type { StructureMeta } from "@/api/structure"
import { cn } from "@/lib/utils"

/**
 * The predicted structure of one construct.
 *
 * What is on screen is a monomer prediction of the assembled fusion, produced by OmegaFold
 * with no multiple-sequence alignment and no partner chain. Four of the seven scaffolds are
 * collagen, whose real fold is a three-chain triple helix, and two are silk proteins, whose
 * fibre is a chain-to-chain beta stack. A single chain cannot show any of that. The rendering
 * is therefore of the peptide and the linker's own geometry, and the confidence figures are
 * shown beside it rather than left for the reader to infer from the picture.
 *
 * The colour is pLDDT - the predictor's per-residue confidence, which the coordinate file
 * carries in its B-factor column - on the scale AlphaFold uses: deep blue for confident
 * residues, yellow for uncertain ones, orange for disordered ones.
 */

type LoadState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "missing" }
  | { kind: "error"; message: string }
  | { kind: "ready"; meta: StructureMeta; url: string }

interface ThreeDmol {
  createViewer(element: HTMLElement, options: Record<string, unknown>): ThreeDmolViewer
}

interface ThreeDmolViewer {
  addModel(url: string, format: string, options?: Record<string, unknown>): unknown
  setStyle(selector: Record<string, unknown>, style: Record<string, unknown>): void
  zoomTo(selector?: Record<string, unknown>): void
  setBackgroundColor(color: string): void
  clear(): void
  render(): void
  resize(): void
}

declare global {
  interface Window {
    $3Dmol?: ThreeDmol
  }
}

let loaderPromise: Promise<boolean> | null = null

/** Load the viewer library once, on demand. */
function loadThreeDmol(): Promise<boolean> {
  if (typeof window === "undefined") return Promise.resolve(false)
  if (window.$3Dmol) return Promise.resolve(true)
  if (!loaderPromise) {
    loaderPromise = new Promise<boolean>((resolve) => {
      const script = document.createElement("script")
      script.src = `${import.meta.env.BASE_URL}vendor/3Dmol-min.js`
      script.async = true
      script.onload = () => resolve(Boolean(window.$3Dmol))
      script.onerror = () => resolve(false)
      document.head.appendChild(script)
    })
  }
  return loaderPromise
}

/** The colour ramp, from disordered to confident. */
const PLDDT_SCHEME = {
  prop: "b",
  gradient: "linear",
  min: 30,
  max: 100,
  colors: ["#e8622c", "#f5b921", "#8ecfd4", "#1f4fd8"],
} as const

const PEPTIDE_COLOR = "#c026d3"

function confidenceLabel(value: number | null): string {
  if (value === null || value === undefined) return "-"
  return `${(value * 100).toFixed(0)}%`
}

function confidenceTone(value: number | null): string {
  if (value === null || value === undefined) return "text-gray-400"
  if (value >= 0.7) return "text-emerald-600"
  if (value >= 0.5) return "text-amber-600"
  return "text-orange-600"
}

export function StructureViewer({
  constructId,
  scaffoldId,
  linkerId,
}: {
  constructId: string
  scaffoldId: string | null
  linkerId: string | null
}) {
  const [state, setState] = useState<LoadState>({ kind: "idle" })
  const [attempt, setAttempt] = useState(0)
  const [highlightPeptide, setHighlightPeptide] = useState(false)
  const containerRef = useRef<HTMLDivElement | null>(null)
  const viewerRef = useRef<ThreeDmolViewer | null>(null)

  // Locate the structure. Runs once per construct: the identifier is what changes.
  useEffect(() => {
    if (!structureEnabled()) return
    let cancelled = false
    setState({ kind: "loading" })
    findStructure(constructId, scaffoldId, linkerId)
      .then((meta) => {
        if (cancelled) return
        if (!meta) {
          setState({ kind: "missing" })
          return
        }
        const url = structureFileUrl(meta.structure_id)
        if (!url) {
          setState({ kind: "missing" })
          return
        }
        setState({ kind: "ready", meta, url })
      })
      .catch((error: unknown) => {
        if (cancelled) return
        setState({
          kind: "error",
          message: error instanceof Error ? error.message : "structure unavailable",
        })
      })
    return () => {
      cancelled = true
    }
  }, [constructId, scaffoldId, linkerId, attempt])

  // The ready state, pulled apart so the effects below can depend on plain values.
  const ready = state.kind === "ready" ? state : null
  const readyUrl = ready?.url ?? null
  const readyMeta = ready?.meta ?? null

  // Draw it.
  useEffect(() => {
    if (!readyUrl) return
    let cancelled = false
    let viewer: ThreeDmolViewer | null = null

    void loadThreeDmol().then(async (loaded) => {
      if (cancelled || !loaded || !containerRef.current || !window.$3Dmol) {
        if (!cancelled) {
          setState((previous) =>
            previous.kind === "ready"
              ? { kind: "error", message: "the structure viewer could not be loaded" }
              : previous,
          )
        }
        return
      }
      let coordinates: string
      try {
        const response = await fetch(readyUrl)
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        coordinates = await response.text()
      } catch (error) {
        if (!cancelled) {
          setState((previous) =>
            previous.kind === "ready"
              ? {
                  kind: "error",
                  message:
                    error instanceof Error ? error.message : "the coordinate file is unreachable",
                }
              : previous,
          )
        }
        return
      }
      if (cancelled) return
      viewer = window.$3Dmol.createViewer(containerRef.current, {
        backgroundColor: "white",
        antialias: true,
      })
      viewer.addModel(coordinates, "pdb", { keepH: false })
      viewer.setStyle({}, { cartoon: { colorscheme: PLDDT_SCHEME } })
      viewer.zoomTo()
      viewer.render()
      viewerRef.current = viewer
    })

    return () => {
      cancelled = true
      viewerRef.current = null
      if (viewer) {
        viewer.clear()
        viewer.render()
      }
    }
  }, [readyUrl])

  // Repaint on a colour-scheme change, and on a window resize.
  useEffect(() => {
    if (!readyMeta) return
    const viewer = viewerRef.current
    if (!viewer) return
    const total = readyMeta.aa_length
    const start = Math.max(0, total - readyMeta.peptide_length)
    viewer.setStyle({}, { cartoon: { colorscheme: PLDDT_SCHEME } })
    if (highlightPeptide) {
      viewer.setStyle({ resi: [start, total - 1] }, { cartoon: { color: PEPTIDE_COLOR } })
    }
    viewer.render()
  }, [highlightPeptide, readyMeta])

  useEffect(() => {
    const onResize = () => {
      viewerRef.current?.resize()
      viewerRef.current?.render()
    }
    window.addEventListener("resize", onResize)
    return () => window.removeEventListener("resize", onResize)
  }, [])

  if (!structureEnabled()) return null

  if (state.kind === "loading" || state.kind === "idle") {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Box className="w-4 h-4 text-primary-500" />
            Predicted structure
          </CardTitle>
        </CardHeader>
        <CardContent className="flex items-center gap-2 text-sm text-gray-500">
          <Loader2 className="w-4 h-4 animate-spin" />
          Looking for a predicted structure of this construct…
        </CardContent>
      </Card>
    )
  }

  if (state.kind === "missing") {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Box className="w-4 h-4 text-gray-400" />
            Predicted structure
          </CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-gray-500">
          No published model matches this exact construct, scaffold and linker combination yet.
          Other combinations may already have models.
        </CardContent>
      </Card>
    )
  }

  if (state.kind === "error") {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <TriangleAlert className="w-4 h-4 text-amber-500" />
            Predicted structure
          </CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-gray-500"><p>Unable to load the structure data: {state.message}</p><Button variant="outline" size="sm" className="mt-3" onClick={() => setAttempt(value => value + 1)}>Retry</Button></CardContent>
      </Card>
    )
  }

  const { meta, url } = state

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle className="flex items-center gap-2 text-base">
              <Box className="w-4 h-4 text-primary-500" />
              Predicted structure
            </CardTitle>
            <CardDescription>
              OmegaFold, single chain, no alignment. {meta.aa_length} residues.
            </CardDescription>
          </div>
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="icon"
              title="Highlight the functional peptide"
              onClick={() => setHighlightPeptide((value) => !value)}
              className={cn("text-gray-400 hover:text-primary-600", highlightPeptide && "text-fuchsia-600")}
            >
              <span className="text-xs font-semibold">Pep</span>
            </Button>
            <Button
              variant="ghost"
              size="icon"
              title="Reset the view"
              onClick={() => {
                viewerRef.current?.zoomTo()
                viewerRef.current?.render()
              }}
              className="text-gray-400 hover:text-primary-600"
            >
              <RotateCcw className="w-4 h-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              title="Download the coordinate file"
              onClick={() => window.open(url, "_blank")}
              className="text-gray-400 hover:text-primary-600"
            >
              <Download className="w-4 h-4" />
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <div
          ref={containerRef}
          className="relative w-full h-[420px] rounded-lg border border-gray-200 bg-white overflow-hidden"
        />

        <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-xs">
          <div className="flex items-center gap-2">
            <span className="text-gray-500">Whole chain pLDDT</span>
            <span className={cn("font-semibold", confidenceTone(meta.confidence))}>
              {confidenceLabel(meta.confidence)}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-gray-500">Peptide only</span>
            <span className={cn("font-semibold", confidenceTone(meta.peptide_confidence))}>
              {confidenceLabel(meta.peptide_confidence)}
            </span>
          </div>
          <div className="flex items-center gap-2 text-gray-400">
            <span>Colour</span>
            {[
              ["#e8622c", "disordered"],
              ["#f5b921", "uncertain"],
              ["#8ecfd4", "confident"],
              ["#1f4fd8", "very confident"],
            ].map(([color, label]) => (
              <span key={label} className="flex items-center gap-1">
                <span
                  className="w-3 h-3 rounded-sm inline-block"
                  style={{ backgroundColor: color }}
                />
                {label}
              </span>
            ))}
          </div>
        </div>

        <p className="text-xs text-gray-400 leading-relaxed">
          A prediction of the assembled chain on its own. It says nothing about the oligomeric
          state: four of the seven scaffolds are collagen and two are silk protein, and both
          fold into structures that no single chain can show.
        </p>
      </CardContent>
    </Card>
  )
}
