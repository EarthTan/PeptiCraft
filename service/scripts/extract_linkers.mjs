/**
 * Extract the linker library from the frontend's linkers.ts and print it as JSON.
 *
 * The 15 curated linker entries — with their unit composition, rigidity band and per-entry
 * literature reference — were held as a TypeScript literal in `app/src/data/linkers.ts`.
 * Rather than transcribe them into Python (which would immediately create a second copy to
 * drift from), this read the module and emitted the data, and the importer consumed the JSON.
 *
 *   ⚠ That source file no longer exists. It went when the frontend's static mock data was
 *   removed, and with it the only copy of the 15 entries outside the database itself. The
 *   `linker_library` table still holds them, so the rows are not lost — but the curated
 *   source is, and this script cannot regenerate it.
 *
 * Until the source is restored this exits with an explanation rather than an ENOENT stack
 * trace, because "file not found" from a deep `readFileSync` says nothing about the fact that
 * a curated library needs recovering. Checked while writing this: the file is not in this
 * repository's history (it predates the repo, which starts from the first commit that
 * consolidated the project), and no copy was found elsewhere on this machine. So the two
 * routes back both need the actual data rather than a reconstruction of it:
 *
 *   1. Recover `app/src/data/linkers.ts` from wherever the frontend's pre-consolidation
 *      history lives, if it is still reachable.
 *   2. Or promote the database to the source: dump the 15 `linker_library` rows and treat
 *      the dump as the new curated source. The derivation below is idempotent, so exporting
 *      the rows through the same shape and re-running it is safe.
 *
 * Reconstructing the entries from the sequences alone is not possible: `unit_composition`,
 * `reference` and `priority_reason` are prose that exists only in the original source.
 *
 *   node service/scripts/extract_linkers.mjs > /tmp/linkers.json
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(here, "..", "..");
const sourcePath = path.join(repoRoot, "app", "src", "data", "linkers.ts");

if (!fs.existsSync(sourcePath)) {
  process.stderr.write(
    `The curated linker source is missing: ${path.relative(repoRoot, sourcePath)}\n\n` +
      `It was deleted along with the frontend's static mock data, so the 15 entries can no\n` +
      `longer be regenerated from source. The rows themselves are still in the linker_library\n` +
      `table; see the header of this file for the two routes back.\n`,
  );
  process.exit(2);
}

const raw = fs.readFileSync(sourcePath, "utf8");

// Everything below assumes a plain object literal with type annotations and helper
// functions, which is what that file was. The vm-based strip is kept so a restored file
// needs no changes here.
let js = raw
  // drop `import type { ... } from "@/types"` — types do not exist at runtime
  .replace(/^\s*import\s+type\s+[^\n]*\n/gm, "")
  // drop the `: Linker[]` / `: {...}` annotations on the declarations we evaluate
  .replace(/export const linkers\s*:\s*Linker\[\]\s*=/, "const linkers =")
  .replace(/export const linkerEnumerationStats\s*(:[^=]+)?=/, "const linkerEnumerationStats =");

// Everything from the first exported function onwards is helper code that closes over
// `linkers`; we do not need it and it carries type annotations.
js = js.replace(/export function[\s\S]*$/, "");

js += "\n;globalThis.__extracted = { linkers, linkerEnumerationStats };\n";

const vm = await import("node:vm");
const context = { globalThis: {} };
vm.createContext(context);
vm.runInContext(js, context);

const { linkers, linkerEnumerationStats } = context.globalThis.__extracted;

if (!Array.isArray(linkers) || linkers.length === 0) {
  throw new Error(`no linkers found in ${sourcePath}`);
}

// Unit counts are derived from the sequence rather than trusted from the prose, and the
// two families the library actually uses are named explicitly.
const UNIT_FAMILIES = { flexible: "GGGGS", rigid: "EAAAK" };

const countUnit = (sequence, unit) => {
  let count = 0;
  let index = sequence.indexOf(unit);
  while (index !== -1) {
    count += 1;
    index = sequence.indexOf(unit, index + unit.length);
  }
  return count;
};

// Five-band label to a coarse 0-1 index. The band is a presentation choice layered on top
// of the library's two-value convention (0.0 fully flexible, 1.0 fully rigid); the midpoint
// values are an interpolation, not a measurement.
const RIGIDITY_INDEX = {
  Flexible: 0.0,
  "Mostly Flexible": 0.25,
  Balanced: 0.5,
  "Mostly Rigid": 0.75,
  Rigid: 1.0,
};

const out = linkers.map((l) => ({
  id: l.id,
  name: l.name,
  sequence: l.sequence,
  length: l.length ?? l.sequence.length,
  rigidity: l.rigidity ?? null,
  rigidity_index: RIGIDITY_INDEX[l.rigidity] ?? null,
  flexible_count: countUnit(l.sequence, UNIT_FAMILIES.flexible),
  rigid_count: countUnit(l.sequence, UNIT_FAMILIES.rigid),
  unit_composition: l.unitComposition ?? [],
  description: l.description ?? null,
  reference: l.reference ?? null,
  priority_reason: l.priorityReason ?? null,
}));

// A length that disagrees with the sequence would silently corrupt every fused construct,
// so it is checked here rather than at render time.
for (const l of out) {
  if (l.length !== l.sequence.length) {
    throw new Error(`${l.id}: declared length ${l.length} != sequence length ${l.sequence.length}`);
  }
}

process.stdout.write(
  JSON.stringify(
    { source: path.relative(repoRoot, sourcePath), enumeration: linkerEnumerationStats, linkers: out },
    null,
    2,
  ) + "\n",
);
