import { useState, type FormEvent } from 'react'
import { api, errorMessage } from '../api.ts'
import { useSession } from '../app/session.tsx'

/** Мастер первого запуска: тот, кто его прошёл, становится администратором. */
export function SetupPage() {
  const { reload } = useSession()
  const [name, setName] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function submit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await api.setup(name.trim())
      await reload()
    } catch (error) {
      setError(errorMessage(error))
      setBusy(false)
    }
  }

  return (
    <section>
      <p className="eyebrow">Первый запуск</p>
      <h1>Создадим вашу организацию</h1>
      <p className="lead">Вы станете её администратором и сможете выдавать роли остальным.</p>

      <form className="learning-card" onSubmit={submit}>
        <h2>Организация</h2>
        <label className="field">
          Название
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            maxLength={200}
            placeholder="ООО «Ромашка»"
            autoFocus
          />
        </label>
        {error && <p className="error">{error}</p>}
        <button type="submit" disabled={busy || !name.trim()}>
          Создать
        </button>
      </form>
    </section>
  )
}
