import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { api, errorMessage, type PluginUI } from '../api.ts'

type PluginState = {
  plugins: PluginUI[]
  loading: boolean
  error: string | null
  reload: () => void
}

const PluginContext = createContext<PluginState | null>(null)
const reserved = ['/profile', '/users', '/api']

// Плагины дополняют интерфейс, но не подменяют маршруты ядра.
function isPluginPath(path: string) {
  return path.startsWith('/') && !path.startsWith('//') && path !== '/'
    && !/[?#\\*:\s]/.test(path)
    && !path.split('/').some((part) => part === '.' || part === '..')
    && !reserved.some((base) => path === base || path.startsWith(`${base}/`))
}

function validatePlugins(plugins: PluginUI[]) {
  const routes = new Set<string>()
  return plugins.map((plugin) => {
    const pages = plugin.frontend.pages.filter((page) => {
      if (!isPluginPath(page.path) || !/^[a-z][a-z0-9]*(?:-[a-z0-9]+)+$/.test(page.element)
        || routes.has(page.path)) return false
      routes.add(page.path)
      return true
    })
    return {
      ...plugin,
      frontend: {
        ...plugin.frontend,
        pages,
        menu_items: plugin.frontend.menu_items.filter((item) =>
          pages.some((page) => page.path === item.path)),
      },
    }
  })
}

export function PluginsProvider({ children }: { children: ReactNode }) {
  const [plugins, setPlugins] = useState<PluginUI[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [revision, setRevision] = useState(0)
  const reload = useCallback(() => setRevision((value) => value + 1), [])

  useEffect(() => {
    let active = true
    setLoading(true)
    setError(null)
    api.pluginUI().then((result) => {
      if (active) setPlugins(validatePlugins(result))
    }).catch((cause: unknown) => {
      if (active) setError(errorMessage(cause))
    }).finally(() => {
      if (active) setLoading(false)
    })
    return () => { active = false }
  }, [revision])

  return <PluginContext.Provider value={{ plugins, loading, error, reload }}>
    {children}
  </PluginContext.Provider>
}

export function usePlugins() {
  const context = useContext(PluginContext)
  if (!context) throw new Error('PluginsProvider не подключён')
  return context
}

const modules = new Map<string, Promise<unknown>>()
const retries = new Map<string, number>()

export async function loadPluginModule(plugin: PluginUI, element: string) {
  const url = new URL(plugin.frontend.entry, window.location.origin)
  if (url.origin !== window.location.origin || !url.pathname.startsWith('/api/plugin-assets/')) {
    throw new Error('Недопустимый адрес интерфейса плагина')
  }
  url.searchParams.set('v', plugin.version)
  const key = url.href
  let pending = modules.get(key)
  if (!pending) {
    const attempt = retries.get(key) ?? 0
    if (attempt) url.searchParams.set('retry', String(attempt))
    pending = import(/* @vite-ignore */ url.href).catch((error: unknown) => {
      modules.delete(key)
      retries.set(key, attempt + 1)
      throw error
    })
    modules.set(key, pending)
  }
  await pending
  if (!customElements.get(element)) {
    throw new Error(`Плагин не зарегистрировал компонент «${element}»`)
  }
}
