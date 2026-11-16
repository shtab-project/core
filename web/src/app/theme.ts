import { useSyncExternalStore } from 'react'

type Theme = 'light' | 'dark'
const STORAGE_KEY = 'shtab.theme'
const listeners = new Set<() => void>()

function readTheme(): Theme {
  try {
    return localStorage.getItem(STORAGE_KEY) === 'light' ? 'light' : 'dark'
  } catch {
    return 'dark'
  }
}

let theme = readTheme()

function applyTheme(value: Theme) {
  theme = value
  document.documentElement.dataset.theme = value
  listeners.forEach((listener) => listener())
}

export function initializeTheme() {
  applyTheme(theme)
}

function setTheme(value: Theme) {
  applyTheme(value)
  try {
    localStorage.setItem(STORAGE_KEY, value)
  } catch {
    // При недоступном хранилище выбор действует до обновления страницы.
  }
}

window.addEventListener('storage', (event) => {
  if (event.key === STORAGE_KEY || event.key === null) applyTheme(readTheme())
})

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => { listeners.delete(listener) }
}

export function useTheme() {
  return [useSyncExternalStore(subscribe, () => theme), setTheme] as const
}
