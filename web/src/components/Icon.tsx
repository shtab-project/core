// Контурные иконки 20×20 для сайдбара; цвет берут из текста (currentColor).

const paths = {
  search: 'M16 10a6 6 0 1 1-12 0 6 6 0 0 1 12 0Zm-1.75 4.25L20 20',
  note: 'M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9Zm0 0v6h6M8 13h8M8 17h5',
  sun: 'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8ZM12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4',
  moon: 'M20.5 13A8.7 8.7 0 0 1 11 3.5 8.8 8.8 0 1 0 20.5 13Z',
  plugin: 'M4 4h6v5h4V4h6v6h-5v4h5v6h-6v-5h-4v5H4v-6h5v-4H4Z',
  todo: 'M9 5H5v4h4ZM19 5h-4v4h4ZM9 15H5v4h4ZM19 15h-4v4h4Z',
  profile: 'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8ZM4.5 20c.6-4 3.4-6 7.5-6s6.9 2 7.5 6',
  users:
    'M9 11a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7ZM2.5 20c.5-3.8 2.7-5.8 6.5-5.8s6 2 6.5 5.8M16 4.5a3.5 3.5 0 0 1 0 6.5M18 14.5c2 .6 3.2 2.4 3.5 5.5',
  logout: 'M10 4H6a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h4M15 8l4 4-4 4M19 12H9',
  collapse: 'M15 6l-6 6 6 6',
  expand: 'M9 6l6 6-6 6',
  menu: 'M4 7h16M4 12h16M4 17h16',
} as const

export type IconName = keyof typeof paths

export function isIconName(value: unknown): value is IconName {
  return typeof value === 'string' && Object.hasOwn(paths, value)
}

export function Icon({ name }: { name: IconName }) {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d={paths[name]}
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}
