import { useMe } from '../app/session.tsx'
import { displayName, formatDate, initials } from '../format.ts'
import './account.css'

export function ProfilePage() {
  const { user, organization } = useMe()

  return (
    <section className="account-page">
      <h1 className="account-heading">Профиль</h1>
      <div className="account-panel profile-panel">
        <header className="profile-identity">
          <span className="avatar profile-avatar" aria-hidden="true">{initials(user)}</span>
          <div>
            <h2>{displayName(user)}</h2>
            <p>@{user.username}</p>
            <div className="profile-roles" aria-label="Роли">
              {user.is_admin && <span className="account-chip">Администратор</span>}
              {user.is_trusted && <span className="account-chip">Доверенный</span>}
              {!user.is_admin && !user.is_trusted && <span className="account-chip">Участник</span>}
            </div>
          </div>
        </header>

        <div className="profile-sections">
          <section aria-labelledby="profile-account">
            <h3 id="profile-account">Аккаунт</h3>
            <dl className="profile-fields">
              <div><dt>Почта</dt><dd>{user.email ?? 'Не указана'}</dd></div>
              <div><dt>Организация</dt><dd>{organization?.name ?? 'Не указана'}</dd></div>
            </dl>
          </section>
          <section aria-labelledby="profile-activity">
            <h3 id="profile-activity">Активность</h3>
            <dl className="profile-fields">
              <div><dt>В Shtab с</dt><dd>{formatDate(user.created_at)}</dd></div>
              <div><dt>Последний вход</dt><dd>{formatDate(user.last_login_at)}</dd></div>
            </dl>
          </section>
        </div>
      </div>
    </section>
  )
}
