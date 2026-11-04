import type { SequenceSegment } from "@/api/types"

export function sequenceColor(segment: SequenceSegment): string {
  if (!segment.available) return "#9ca3af"
  if (segment.type === "linker") return "#a16207"
  if (segment.type === "peptide") return "#7e22ce"
  return segment.color
}

export function sequenceWeight(segment: SequenceSegment): number {
  return segment.type === "peptide" ? 700 : segment.type === "linker" ? 600 : 400
}
