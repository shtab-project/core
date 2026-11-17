import { useEffect, useRef, useState } from 'react'
import { NavLink } from 'react-router'
import { api } from '../api.ts'
import { useMe } from '../app/session.tsx'
import { usePlugins } from '../app/plugins.tsx'
import { displayName, initials, roleLabel } from '../format.ts'
import { Icon, isIconName, type IconName } from './Icon.tsx'
import { ThemeToggle } from './ThemeToggle.tsx'
import { Brand } from './Brand.tsx'

const COLLAPSED_KEY = 'shtab.sidebar-collapsed'

function readCollapsed() {
  try {
    return localStorage.getItem(COLLAPSED_KEY) === '1'
  } catch {
    return false
  }
}

type Props = {
  open: boolean
  onClose: () => void
}

/** Боковое меню: сворачивается до иконок, на телефоне выезжает поверх контента. */
export function Sidebar({ open, onClose }: Props) {
  const { user, organization } = useMe()
  const [collapsed, setCollapsed] = useState(readCollapsed)
  const accountMenu = useRef<HTMLDetailsElement>(null)

  function closeMenu() {
    if (accountMenu.current) accountMenu.current.open = false
    onClose()
  }

  useEffect(() => {
    try {
      localStorage.setItem(COLLAPSED_KEY, collapsed ? '1' : '0')
    } catch {
      // Хранилище недоступно (приватный режим) — просто не запоминаем
    }
  }, [collapsed])

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return
      const menu = accountMenu.current
      if (menu?.open) {
        menu.open = false
        menu.querySelector('summary')?.focus()
      } else {
        onClose()
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  async function logout() {
    const { logout_url } = await api.logout()
    // Завершаем сессию и в Authentik, иначе следующий «Войти» пропустит ввод пароля
    window.location.href = logout_url ?? '/'
  }

  const className = ['sidebar', collapsed && 'collapsed', open && 'open'].filter(Boolean).join(' ')

  return (
    <aside className={className} aria-label="Основная навигация">
      <div className="sidebar-top">
        <Brand name={organization?.name} />
        <button
          className="icon-button collapse-toggle"
          type="button"
          aria-label={collapsed ? 'Развернуть меню' : 'Свернуть меню'}
          title={collapsed ? 'Развернуть меню' : 'Свернуть меню'}
          onClick={() => setCollapsed((value) => !value)}
        >
          <Icon name={collapsed ? 'expand' : 'collapse'} />
        </button>
      </div>
      <nav>
        <PluginLinks slot="sidebar.main" onClose={closeMenu} />
      </nav>

      <div className="sidebar-bottom">
        <PluginLinks slot="sidebar.bottom" onClose={closeMenu} />
        <details className="sidebar-account" ref={accountMenu}>
          <summary className="user-chip" aria-label={`Аккаунт: ${displayName(user)}`} title={`${displayName(user)} · ${roleLabel(user)}`}>
            <span className="avatar" aria-hidden="true">{initials(user)}</span>
            <span className="user-chip-name">{displayName(user)}</span>
            <Icon name="chevron-down" />
          </summary>
          <div className="sidebar-account-links">
            <SidebarLink to="/profile" icon="profile" label="Профиль" onClick={closeMenu} />
            {user.is_admin && <>
              <SidebarLink to="/users" icon="users" label="Пользователи" onClick={closeMenu} />
              <SidebarLink to="/plugins" end icon="plugin" label="Плагины" onClick={closeMenu} />
            </>}
            <ThemeToggle />
            <button className="nav-link danger" type="button" title="Выйти" onClick={() => void logout()}>
              <Icon name="logout" />
              <span>Выйти</span>
            </button>
          </div>
        </details>
      </div>
    </aside>
  )
}

const pluginIcons: Readonly<Partial<Record<string, IconName>>> = {
  todo: 'todo',
  notes: 'note',
  'direct-ai-control': 'sparkles',
}

function PluginLinks({ slot, onClose }: { slot: string; onClose: () => void }) {
  const { plugins, error, reload } = usePlugins()
  const items = plugins.flatMap((plugin) => plugin.frontend.menu_items
    .filter((item) => item.slot === slot)
    .map((item) => ({ ...item, pluginId: plugin.id })))
    .sort((left, right) => left.order - right.order || left.title.localeCompare(right.title, 'ru'))

  return <>
    {items.map((item) => <SidebarLink key={`${item.pluginId}:${item.path}`} to={item.path}
      icon={pluginIcons[item.pluginId] ?? (isIconName(item.icon) ? item.icon : 'plugin')} label={item.title} onClick={onClose} />)}
    {slot === 'sidebar.main' && error && <button className="nav-link" type="button"
      title="Не удалось загрузить плагины. Повторить" onClick={reload}>
      <Icon name="plugin" /><span>Повторить загрузку</span>
    </button>}
  </>
}

function SidebarLink(props: { to: string; end?: boolean; icon: IconName; label: string; onClick: () => void }) {
  return (
    <NavLink className="nav-link" to={props.to} end={props.end} title={props.label} onClick={props.onClick}>
      <Icon name={props.icon} />
      <span>{props.label}</span>
    </NavLink>
  )
}
