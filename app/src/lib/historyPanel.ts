/**
 * Whether the build history is on screen.
 *
 * The panel is asked for from two places that share no page — the clock in the top bar,
 * which is part of the layout every page sits inside, and the results step, which is deep in
 * the Builder. Its open state therefore cannot belong to either of them, and mounting two
 * copies would give the application two panels to keep in step. This module is the little
 * piece of state both of them read and write; the panel itself is mounted once, in the
 * layout.
 */

let open = false
const listeners = new Set<() => void>()

function emit() {
  for (const listener of listeners) listener()
}

export function subscribeHistoryPanel(listener: () => void): () => void {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

/** The current state. Stable between changes, as `useSyncExternalStore` requires. */
export function historyPanelOpen(): boolean {
  return open
}

/** The server has no panel to open, and no state to read. */
export function historyPanelOpenOnServer(): boolean {
  return false
}

export function openHistoryPanel(): void {
  if (open) return
  open = true
  emit()
}

export function closeHistoryPanel(): void {
  if (!open) return
  open = false
  emit()
}
