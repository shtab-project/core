import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { ApiError, api, errorMessage, type Me, type SetupStatus } from '../api.ts'

export type Session =
  | { kind: 'loading' }
  | { kind: 'error'; message: string }
  | { kind: 'guest'; setup: SetupStatus }
  | { kind: 'user'; setup: SetupStatus; me: Me }

type SessionContextValue = {
  session: Session
  reload: () => Promise<void>
}

const SessionContext = createContext<SessionContextValue | null>(null)

/** Кто вошёл и настроена ли организация — общее для всех страниц. */
export function SessionProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session>({ kind: 'loading' })

  const reload = useCallback(async () => {
    try {
      const setup = await api.setupStatus()
      try {
        setSession({ kind: 'user', setup, me: await api.me() })
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) setSession({ kind: 'guest', setup })
        else throw error
      }
    } catch (error) {
      setSession({ kind: 'error', message: errorMessage(error) })
    }
  }, [])

  useEffect(() => {
    void reload()
  }, [reload])

  return <SessionContext value={{ session, reload }}>{children}</SessionContext>
}

export function useSession() {
  const value = useContext(SessionContext)
  if (!value) throw new Error('useSession вне SessionProvider')
  return value
}

/** Данные вошедшего пользователя — только внутри страниц приложения. */
export function useMe() {
  const { session } = useSession()
  if (session.kind !== 'user') throw new Error('useMe без входа')
  return session.me
}
