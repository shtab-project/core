import { useCallback, useState, type ReactNode } from 'react'
import { Outlet, useMatch } from 'react-router'
import { useSession } from './app/session.tsx'
import { PluginsProvider } from './app/plugins.tsx'
import { Icon } from './components/Icon.tsx'
import { Sidebar } from './components/Sidebar.tsx'
import { ThemeToggle } from './components/ThemeToggle.tsx'
import { Brand } from './components/Brand.tsx'
import { LoginPage } from './pages/LoginPage.tsx'
import { SetupPage } from './pages/SetupPage.tsx'
import './App.css'

function App() {
  const { session, reload } = useSession()

  switch (session.kind) {
    case 'loading':
      return null
    case 'error':
      return (
        <PublicShell>
          <p className="eyebrow">Сервер недоступен</p>
          <h1>Не удалось связаться с Shtab</h1>
          <p className="lead">{session.message}</p>
          <button className="button" type="button" onClick={() => void reload()}>
            Повторить
          </button>
        </PublicShell>
      )
    case 'guest':
      return (
        <PublicShell>
          <LoginPage organization={session.setup.organization} />
        </PublicShell>
      )
    case 'user':
      if (!session.setup.initialized) {
        return (
          <PublicShell>
            <SetupPage />
          </PublicShell>
        )
      }
      return <PluginsProvider><AppShell /></PluginsProvider>
  }
}

/** Экраны до входа: шапка и контент по центру, как в gonets. */
function PublicShell({ children }: { children: ReactNode }) {
  return (
    <div className="app-shell">
      <header className="app-header">
        <Brand />
        <ThemeToggle />
      </header>
      <main>{children}</main>
    </div>
  )
}

/** Приложение после входа: сайдбар слева, страница справа. */
function AppShell() {
  const [menuOpen, setMenuOpen] = useState(false)
  const closeMenu = useCallback(() => setMenuOpen(false), [])
  const notesPage = useMatch('/plugins/notes')

  return (
    <div className={`app-shell with-sidebar${notesPage ? ' full-workspace' : ''}`}>
      <header className="app-header mobile-header">
        <Brand />
        <button
          className="icon-button"
          type="button"
          aria-label="Открыть меню"
          onClick={() => setMenuOpen(true)}
        >
          <Icon name="menu" />
        </button>
      </header>

      <Sidebar open={menuOpen} onClose={closeMenu} />
      <div className={menuOpen ? 'sidebar-backdrop open' : 'sidebar-backdrop'} onClick={closeMenu} />

      <div className="content">
        <main>
          <Outlet />
        </main>
      </div>
    </div>
  )
}

export default App
