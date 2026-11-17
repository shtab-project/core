export function Brand({ name = 'Shtab' }: { name?: string }) {
  return (
    <span className="brand">
      <svg className="brand-mark" viewBox="0 0 30 32" fill="none" aria-hidden="true">
        <path d="M3 27V5h7v22M12 27V11h7v16M21 27V5h7v22"
          stroke="currentColor" strokeWidth="3" strokeLinejoin="round" />
      </svg>
      <span className="brand-name" title={name}>{name}</span>
    </span>
  )
}
