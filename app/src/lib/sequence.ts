/**
 * Sequence features derived from a peptide string.
 *
 * These are computed, not stored. Molecular weight, net charge and residue composition follow
 * from the sequence itself, so they need no service call and cannot drift from the database.
 * The residue masses are averages net of the water lost on peptide-bond formation; one water
 * is added back to account for the free termini.
 */

/** Average residue mass in Da, already net of the water lost on bond formation. */
const RESIDUE_MASS: Record<string, number> = {
  A: 71.08, R: 156.19, N: 114.1, D: 115.09, C: 103.14, E: 129.12,
  Q: 128.13, G: 57.05, H: 137.14, I: 113.16, L: 113.16, K: 128.17,
  M: 131.19, F: 147.18, P: 97.12, S: 87.08, T: 101.1, W: 186.2,
  Y: 163.18, V: 99.13,
}

const POSITIVE = new Set(["K", "R"])
const NEGATIVE = new Set(["D", "E"])
const AROMATIC = new Set(["F", "W", "Y"])
const HYDROPHOBIC = new Set(["A", "V", "L", "I", "M", "F", "W"])

export interface SequenceFeatures {
  length: number
  molecularWeight: number
  netCharge: number
  cysCount: number
  aromaticPct: number
  hydrophobicPct: number
  glycinePct: number
  prolinePct: number
}

export function analyseSequence(sequence: string): SequenceFeatures {
  const clean = sequence.replace(/[^A-Za-z]/g, "").toUpperCase()
  const n = clean.length || 1

  let mass = 0
  let charge = 0
  let cys = 0
  let aromatic = 0
  let hydrophobic = 0
  let glycine = 0
  let proline = 0

  for (const residue of clean) {
    mass += RESIDUE_MASS[residue] ?? 110
    if (POSITIVE.has(residue)) charge += 1
    if (NEGATIVE.has(residue)) charge -= 1
    if (residue === "C") cys += 1
    if (AROMATIC.has(residue)) aromatic += 1
    if (HYDROPHOBIC.has(residue)) hydrophobic += 1
    if (residue === "G") glycine += 1
    if (residue === "P") proline += 1
  }

  // One water molecule for the two free termini.
  mass += 18.02

  const pct = (count: number) => Math.round((count / n) * 1000) / 10

  return {
    length: clean.length,
    molecularWeight: Math.round(mass * 10) / 10,
    netCharge: charge,
    cysCount: cys,
    aromaticPct: pct(aromatic),
    hydrophobicPct: pct(hydrophobic),
    glycinePct: pct(glycine),
    prolinePct: pct(proline),
  }
}
