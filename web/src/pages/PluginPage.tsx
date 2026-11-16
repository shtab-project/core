import { createElement, useEffect, useState } from 'react'
import { Navigate, useLocation } from 'react-router'
import { errorMessage, type PluginUI } from '../api.ts'
import { loadPluginModule, usePlugins } from '../app/plugins.tsx'

export function PluginPage() {
  const { pathname } = useLocation()
  const { plugins, loading, error, reload } = usePlugins()
  const plugin = plugins.find((item) => item.frontend.pages.some((page) => page.path === pathname))
  const page = plugin?.frontend.pages.find((item) => item.path === pathname)

  if (loading) return <PluginLoading>Загружаем плагины…</PluginLoading>
  if (error) return <section role="alert">
    <h1 className="page-title">Не удалось загрузить плагины</h1>
    <p>{error}</p>
    <button className="button" onClick={reload}>Повторить</button>
  </section>
  if (!plugin || !page) return <Navigate to="/profile" replace />
  return <PluginElement key={`${plugin.id}:${plugin.version}:${page.element}`}
    plugin={plugin} element={page.element} />
}

function PluginElement({ plugin, element }: { plugin: PluginUI; element: string }) {
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading')
  const [message, setMessage] = useState('')
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let active = true
    setState('loading')
    loadPluginModule(plugin, element).then(() => {
      if (active) setState('ready')
    }).catch((cause: unknown) => {
      if (active) {
        setMessage(errorMessage(cause))
        setState('error')
      }
    })
    return () => { active = false }
  }, [plugin, element, attempt])

  if (state === 'loading') return <PluginLoading>{`Загружаем «${plugin.name}»…`}</PluginLoading>
  if (state === 'error') return <section role="alert">
    <h1 className="page-title">Не удалось открыть «{plugin.name}»</h1>
    <p>{message}</p>
    <button className="button" onClick={() => setAttempt((value) => value + 1)}>Повторить</button>
  </section>
  return createElement(element)
}

function PluginLoading({ children }: { children: string }) {
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const timer = window.setTimeout(() => setVisible(true), 300)
    return () => window.clearTimeout(timer)
  }, [])

  return visible ? <p role="status">{children}</p> : null
}
