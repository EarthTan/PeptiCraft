import type { ConstructDetail, ReferenceData } from "@/api/types"

/** Show measured scores for the requested functions; never impute missing values. */
export function functionalScoreTiles(detail: ConstructDetail, reference: ReferenceData, selectedFunctions: string[]) {
  const functionalValues: Record<string, { value: number | null; tool: string }> = {
    antioxidant: { value: detail.supplementary.anoxpepred_frs, tool: "AnOxPePred FRS" },
    antibacterial: { value: detail.supplementary.imfp_lg_amp ?? detail.supplementary.amp_esm, tool: detail.supplementary.imfp_lg_amp != null ? "iMFP-LG AMP" : "AMPlify" },
    anti_inflammatory: { value: detail.supplementary.imfp_lg_aip, tool: "iMFP-LG AIP" },
    antimelanin: { value: detail.supplementary.tipred, tool: "TIPred" },
  }
  return [...new Set(selectedFunctions)].flatMap(id => {
    const source = functionalValues[id]
    const value = id === detail.direction ? detail.functional_score ?? source?.value : source?.value
    if (value == null) return []
    return [{ id, value, label: reference.directions.find(direction => direction.id === id)?.name ?? id, tool: id === detail.direction ? detail.functional_score_label : source?.tool ?? "Prediction" }]
  })
}
