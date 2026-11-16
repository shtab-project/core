// Клиент API Shtab Core. Сессия — httpOnly cookie, поэтому достаточно same-origin запросов.

export type Organization = {
  name: string
  created_at: string
}

export type User = {
  id: string
  username: string
  name: string
  email: string | null
  is_admin: boolean
  is_trusted: boolean
  created_at: string
  last_login_at: string | null
}

export type Me = {
  user: User
  organization: Organization | null
}

export type SetupStatus = {
  initialized: boolean
  organization: Organization | null
}

export type PluginUI = {
  id: string
  name: string
  version: string
  frontend: {
    entry: string
    pages: { path: string; element: string }[]
    menu_items: { slot: string; title: string; path: string; order: number; icon?: string | null }[]
  }
}

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export type CatalogPlugin = {
  id: string
  name: string
  version: string
  description: string
  icon: string
  installed_version: string | null
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    const detail = typeof body?.detail === 'string' ? body.detail : response.statusText
    throw new ApiError(response.status, detail)
  }
  return response.json() as Promise<T>
}

export const api = {
  pluginUI: () => request<PluginUI[]>('/api/plugin-ui'),
  pluginCatalog: () => request<CatalogPlugin[]>('/api/plugins/catalog'),
  installPlugin: (id: string) =>
    request<{ id: string; version: string }>(`/api/plugins/catalog/${encodeURIComponent(id)}/install`, { method: 'POST' }),
  setupStatus: () => request<SetupStatus>('/api/setup'),
  setup: (organization_name: string) =>
    request<Organization>('/api/setup', {
      method: 'POST',
      body: JSON.stringify({ organization_name }),
    }),
  me: () => request<Me>('/api/me'),
  users: () => request<User[]>('/api/users'),
  updateUser: (id: string, roles: Partial<Pick<User, 'is_admin' | 'is_trusted'>>) =>
    request<User>(`/api/users/${id}`, { method: 'PATCH', body: JSON.stringify(roles) }),
  logout: () => request<{ logout_url: string | null }>('/api/auth/logout', { method: 'POST' }),
}

/** Вход — это переход браузера на страницу Authentik, а не fetch. */
export function login(next = '/') {
  window.location.href = `/api/auth/login?next=${encodeURIComponent(next)}`
}

export function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : String(error)
}
