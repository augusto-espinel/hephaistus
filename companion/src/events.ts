/**
 * Simple event bus for cross-component communication.
 * Used to signal Context Inspector to refresh after a prompt is sent.
 */

type Listener = () => void

const listeners: Map<string, Set<Listener>> = new Map()

export function emit(event: string) {
  const set = listeners.get(event)
  if (set) {
    set.forEach(fn => fn())
  }
}

export function on(event: string, listener: Listener) {
  if (!listeners.has(event)) {
    listeners.set(event, new Set())
  }
  listeners.get(event)!.add(listener)
  return () => {
    listeners.get(event)?.delete(listener)
  }
}

// Event names
export const Events = {
  PROMPT_SENT: 'prompt-sent',
  SCHEMATIC_LOADED: 'schematic-loaded',
  SIMULATION_IMPORTED: 'simulation-imported',
} as const
