import { useEffect, useState } from 'react'
import { Link, Navigate } from 'react-router'
import { api, ApiError, errorMessage, type CatalogPlugin } from '../api.ts'
import { usePlugins } from '../app/plugins.tsx'
import { useMe } from '../app/session.tsx'
import { Icon, isIconName } from '../components/Icon.tsx'
import './plugin-catalog.css'

export function PluginCatalogPage() {
  const { user } = useMe()
  return user.is_admin ? <PluginCatalog /> : <Navigate to="/profile" replace />
}

function PluginCatalog() {
  const { plugins, reload } = usePlugins()
  const [catalog, setCatalog] = useState<CatalogPlugin[] | null>(null)
  const [error, setError] = useState('')
  const [pending, setPending] = useState<string | null>(null)
  const [revision, setRevision] = useState(0)
  const [notice, setNotice] = useState('')

  useEffect(() => {
    let active = true
    api.pluginCatalog().then(
      (entries) => { if (active) setCatalog(entries) },
      (cause) => { if (active) setError(errorMessage(cause)) },
    )
    return () => { active = false }
  }, [revision])

  async function install(plugin: CatalogPlugin) {
    setPending(plugin.id)
    setError('')
    setNotice('')
    try {
      const installed = await api.installPlugin(plugin.id)
      setCatalog((entries) => entries?.map((entry) => entry.id === installed.id
        ? { ...entry, installed_version: installed.version }
        : entry) ?? null)
      setNotice(`«${plugin.name}» установлен.`)
      reload()
    } catch (cause) {
      setError(errorMessage(cause))
      if (cause instanceof ApiError && cause.status === 409) {
        setRevision((value) => value + 1)
        reload()
      }
    } finally {
      setPending(null)
    }
  }

  return (
    <section className="plugin-catalog" aria-labelledby="plugin-catalog-title">
      <h1 id="plugin-catalog-title">Плагины</h1>
      {error && <div role="alert" className="catalog-error">
        <p>{error}</p>
        {!catalog && <button className="button" type="button" onClick={() => {
          setError('')
          setRevision((value) => value + 1)
        }}>Повторить</button>}
      </div>}
      {notice && <p role="status" className="catalog-notice">{notice}</p>}
      {!catalog && !error && <p role="status">Загружаем каталог…</p>}
      {catalog && <ul className="catalog-grid">
        {catalog.map((plugin) => {
          const page = plugins.find((entry) => entry.id === plugin.id)?.frontend.pages[0]
          return <li className="catalog-card" key={plugin.id}>
            <div className="catalog-icon"><Icon name={isIconName(plugin.icon) ? plugin.icon : 'plugin'} /></div>
            <h2>{plugin.name}</h2>
            <p>{plugin.description}</p>
            <div className="catalog-card-footer">
              <small>{plugin.installed_version ? `Установлен · v${plugin.installed_version}` : `GitHub · v${plugin.version}`}</small>
              {plugin.installed_version
                ? page && <Link className="button" to={page.path}>Открыть</Link>
                : <button className="button" type="button" disabled={pending !== null}
                    onClick={() => void install(plugin)}>
                  {pending === plugin.id ? 'Устанавливаем…' : 'Установить'}
                </button>}
            </div>
          </li>
        })}
      </ul>}
    </section>
  )
}
