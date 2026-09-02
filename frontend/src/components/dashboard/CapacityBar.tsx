interface CapacityBarProps {
  pct: number  // 0–100
  /** Rendered inside an accessible container — provide a title via the parent */
  'aria-label'?: string
}

function barClass(pct: number): string {
  if (pct >= 90) return 'capacity-bar__fill capacity-bar__fill--danger'
  if (pct >= 75) return 'capacity-bar__fill capacity-bar__fill--warning'
  return 'capacity-bar__fill'
}

export function CapacityBar({ pct, 'aria-label': ariaLabel }: CapacityBarProps) {
  const clamped = Math.min(100, Math.max(0, pct))
  return (
    <div className="capacity-bar" role="meter" aria-valuenow={clamped} aria-valuemin={0} aria-valuemax={100} aria-label={ariaLabel}>
      <div className={barClass(clamped)} style={{ width: `${clamped}%` }} />
    </div>
  )
}
