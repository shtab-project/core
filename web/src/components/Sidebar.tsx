import { useEffect, useState } from 'react'
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

  useEffect(() => {
    try {
      localStorage.setItem(COLLAPSED_KEY, collapsed ? '1' : '0')
    } catch {
      // Хранилище недоступно (приватный режим) — просто не запоминаем
    }
  }, [collapsed])

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => event.key === 'Escape' && onClose()
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
        <Brand />
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
      {organization && <p className="sidebar-org">{organization.name}</p>}

      <nav>
        <div className="sidebar-group workspace-links">
          <p className="sidebar-group-label">Рабочее пространство</p>
          <PluginLinks slot="sidebar.main" onClose={onClose} />
        </div>
        <div className="sidebar-group">
          <p className="sidebar-group-label">Аккаунт</p>
          <SidebarLink to="/profile" icon="profile" label="Профиль" onClick={onClose} />
        </div>
        {user.is_admin && (
          <div className="sidebar-group admin-links">
            <p className="sidebar-group-label">Управление</p>
            <SidebarLink to="/users" icon="users" label="Пользователи" onClick={onClose} />
            <SidebarLink to="/plugins" end icon="plugin" label="Плагины" onClick={onClose} />
          </div>
        )}
      </nav>

      <div className="sidebar-bottom">
        <PluginLinks slot="sidebar.bottom" onClose={onClose} />
        <ThemeToggle />
        <div className="user-chip" title={displayName(user)}>
          <div className="avatar">{initials(user)}</div>
          <span>
            <b>{displayName(user)}</b>
            <small>{roleLabel(user)}</small>
          </span>
        </div>
        <button className="nav-link danger" type="button" title="Выйти" onClick={() => void logout()}>
          <Icon name="logout" />
          <span>Выйти</span>
        </button>
      </div>
    </aside>
  )
}

function PluginLinks({ slot, onClose }: { slot: string; onClose: () => void }) {
  const { plugins, error, reload } = usePlugins()
  const items = plugins.flatMap((plugin) => plugin.frontend.menu_items
    .filter((item) => item.slot === slot)
    .map((item) => ({ ...item, pluginId: plugin.id })))
    .sort((left, right) => left.order - right.order || left.title.localeCompare(right.title, 'ru'))

  return <>
    {items.map((item) => <SidebarLink key={`${item.pluginId}:${item.path}`} to={item.path}
      icon={item.pluginId === 'todo' ? 'todo' : item.pluginId === 'notes' ? 'note' : isIconName(item.icon) ? item.icon : 'plugin'} label={item.title} onClick={onClose} />)}
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
