import { useLocation } from 'react-router'
import { login, type Organization } from '../api.ts'

export function LoginPage({ organization }: { organization: Organization | null }) {
  const location = useLocation()

  return (
    <section>
      <p className="eyebrow">{organization ? organization.name : 'Shtab'}</p>
      <h1>Вся команда в одном месте</h1>
      <p className="lead">
        Пользователи, роли и проекты организации — под единым входом через Authentik.
      </p>

      <article className="learning-card">
        <h2>Вход</h2>
        <p>Используйте аккаунт организации. После входа вы вернётесь сюда.</p>
        <button type="button" onClick={() => login(location.pathname)}>
          Войти через Authentik
        </button>
      </article>
    </section>
  )
}
