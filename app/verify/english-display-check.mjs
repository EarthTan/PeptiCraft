import assert from 'node:assert/strict'
import { readdir, readFile } from 'node:fs/promises'
import { englishDisplay } from '../src/lib/english-display.ts'

let files = 0
let fields = 0
let translated = 0
function compare(raw, shown, path) {
  if (typeof raw === 'string') {
    fields++
    assert(!/[\u4e00-\u9fff\u2013\u2014]/u.test(shown), `Untranslated text at ${path}: ${shown}`)
    if (shown !== raw) translated++
    // Identifiers, sequences, hashes and ASCII source URLs must be preserved exactly.
    if (/^[\x20-\x7e]*$/.test(raw)) assert.equal(shown, raw, `ASCII field changed at ${path}`)
  } else if (Array.isArray(raw)) {
    assert.equal(shown.length, raw.length)
    raw.forEach((value, index) => compare(value, shown[index], `${path}[${index}]`))
  } else if (raw && typeof raw === 'object') {
    assert.deepEqual(Object.keys(shown), Object.keys(raw))
    Object.entries(raw).forEach(([key, value]) => compare(value, shown[key], `${path}.${key}`))
  } else assert.equal(shown, raw, `Value changed at ${path}`)
}
async function visit(directory) {
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const path = `${directory}/${entry.name}`
    if (entry.isDirectory()) await visit(path)
    else if (entry.name.endsWith('.json')) {
      const raw = JSON.parse(await readFile(path, 'utf8'))
      compare(raw, englishDisplay(raw), path)
      files++
    }
  }
}
await visit(new URL('../public/data', import.meta.url).pathname)
console.log(`English display passed: ${files} files, ${fields} text fields, ${translated} translated/normalised fields; ASCII identifiers, sequences and numeric values preserved.`)
