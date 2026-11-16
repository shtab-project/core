import { useEffect, useRef, useState } from 'react'
import { Navigate } from 'react-router'
import { api, errorMessage, type User } from '../api.ts'
import { useMe } from '../app/session.tsx'
import { Icon } from '../components/Icon.tsx'
import { displayName, formatDate, initials } from '../format.ts'
import './account.css'

type Role = 'is_admin' | 'is_trusted'

/** Список пользователей и их роли — только для администратора. */
export function UsersPage() {
  const { user: me } = useMe()
  if (!me.is_admin) return <Navigate to="/profile" replace />
  return <UsersList currentUserId={me.id} />
}

function UsersList({ currentUserId }: { currentUserId: string }) {
  const [users, setUsers] = useState<User[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [revision, setRevision] = useState(0)
  const [pendingUser, setPendingUser] = useState<string | null>(null)
  const updating = useRef(false)

  useEffect(() => {
    let active = true
    api.users().then(
      (list) => { if (active) setUsers(list) },
      (cause) => { if (active) setError(errorMessage(cause)) },
    )
    return () => { active = false }
  }, [revision])

  async function toggle(user: User, role: Role) {
    if (updating.current) return
    updating.current = true
    setPendingUser(user.id)
    setError(null)
    try {
      const updated = await api.updateUser(user.id, { [role]: !user[role] })
      setUsers((list) => list?.map((item) => (item.id === updated.id ? updated : item)) ?? null)
    } catch (error) {
      setError(errorMessage(error))
    } finally {
      updating.current = false
      setPendingUser(null)
    }
  }

  const search = query.trim().toLocaleLowerCase('ru')
  const visible = users?.filter((user) =>
    [displayName(user), user.username, `@${user.username}`, user.email ?? '']
      .some((value) => value.toLocaleLowerCase('ru').includes(search)),
  )

  return (
    <section className="account-page">
      <h1 className="account-heading">Пользователи</h1>
      <div className="account-panel directory-panel">
        <div className="directory-tools">
          <label className="directory-search">
            <Icon name="search" />
            <input type="search" aria-label="Найти пользователя" placeholder="Имя, логин или почта"
              value={query} onChange={(event) => setQuery(event.target.value)} />
          </label>
          {visible && <span className="directory-count" role="status">Показано {visible.length} из {users?.length}</span>}
        </div>
        {error && <p className="directory-error" role="alert">{error}</p>}
        {!users ? (
          error ? <div className="directory-empty">
            <button className="button" type="button" onClick={() => {
              setError(null)
              setRevision((value) => value + 1)
            }}>Повторить</button>
          </div> : <p className="directory-empty" role="status">Загружаем пользователей…</p>
        ) : !visible?.length ? (
          <p className="directory-empty">{search ? 'Пользователи не найдены' : 'Пока нет пользователей'}</p>
        ) : (
          <div className="directory-table">
            <table>
              <thead>
                <tr>
                  <th>Пользователь</th>
                  <th>Админ</th>
                  <th>Доверенный</th>
                  <th>Последний вход</th>
                </tr>
              </thead>
              <tbody>
                {visible.map((user) => (
                  <tr key={user.id} aria-busy={pendingUser === user.id}>
                    <td className="directory-person">
                      <div className="directory-identity">
                        <span className="avatar" aria-hidden="true">{initials(user)}</span>
                        <div>
                          <strong>{displayName(user)}</strong>
                          {user.id === currentUserId && <span className="directory-self">Вы</span>}
                          <small>{user.email ?? `@${user.username}`}</small>
                        </div>
                      </div>
                    </td>
                    <td className="directory-role">
                      <span aria-hidden="true">Админ</span>
                      <Switch
                        checked={user.is_admin}
                        disabled={user.id === currentUserId || pendingUser !== null}
                        locked={user.id === currentUserId}
                        label={`Администратор: ${user.username}`}
                        onChange={() => void toggle(user, 'is_admin')}
                      />
                    </td>
                    <td className="directory-role">
                      <span aria-hidden="true">Доверенный</span>
                      <Switch
                        checked={user.is_trusted}
                        disabled={pendingUser !== null}
                        label={`Доверенный: ${user.username}`}
                        onChange={() => void toggle(user, 'is_trusted')}
                      />
                    </td>
                    <td className="directory-activity">
                      <span aria-hidden="true">Последний вход </span>{formatDate(user.last_login_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  )
}

function Switch(props: { checked: boolean; disabled?: boolean; locked?: boolean; label: string; onChange: () => void }) {
  return (
    <button
      className="switch"
      type="button"
      role="switch"
      aria-checked={props.checked}
      aria-label={props.label}
      disabled={props.disabled}
      title={props.locked ? 'Нельзя снять права с себя' : undefined}
      onClick={props.onChange}
    />
  )
}
