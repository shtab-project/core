import { useTheme } from '../app/theme.ts'
import { Icon } from './Icon.tsx'

export function ThemeToggle() {
  const [theme, setTheme] = useTheme()
  const next = theme === 'dark' ? 'light' : 'dark'
  const label = next === 'light' ? 'Включить светлую тему' : 'Включить тёмную тему'

  return (
    <button className="nav-link theme-toggle" type="button" aria-label={label}
      title={label} onClick={() => setTheme(next)}>
      <Icon name={next === 'light' ? 'sun' : 'moon'} />
      <span>{next === 'light' ? 'Светлая тема' : 'Тёмная тема'}</span>
    </button>
  )
}
