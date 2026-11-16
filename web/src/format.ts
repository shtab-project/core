import type { User } from './api.ts'

export function displayName(user: User) {
  return user.name || user.username
}

export function initials(user: User) {
  const parts = displayName(user).trim().split(/\s+/)
  const letters = parts.length > 1 ? parts[0][0] + parts[1][0] : parts[0].slice(0, 2)
  return letters.toUpperCase()
}

export function roleLabel(user: User) {
  if (user.is_admin) return 'Администратор'
  if (user.is_trusted) return 'Доверенный'
  return 'Пользователь'
}

export function formatDate(value: string | null) {
  return value
    ? new Date(value).toLocaleString('ru-RU', { dateStyle: 'medium', timeStyle: 'short' })
    : '—'
}
