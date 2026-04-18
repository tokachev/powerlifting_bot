import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

export function Card({
  title,
  meta,
  children,
  dense = false,
  brackets = false,
}: {
  title?: string
  meta?: ReactNode
  children: ReactNode
  dense?: boolean
  brackets?: boolean
}) {
  return (
    <div className={`card${dense ? ' dense' : ''}${brackets ? ' brackets' : ''}`}>
      {(title || meta) && (
        <div className="card-title">
          {title && <h3>{title}</h3>}
          {meta && <div className="meta">{meta}</div>}
        </div>
      )}
      {children}
    </div>
  )
}

export function Chip({
  kind,
  children,
}: {
  kind?: 'good' | 'warn' | 'crit'
  children: ReactNode
}) {
  return <span className={`chip${kind ? ' ' + kind : ''}`}>{children}</span>
}

export function LiftDot({ lift }: { lift: 'squat' | 'bench' | 'deadlift' }) {
  const color =
    lift === 'squat'
      ? 'var(--squat)'
      : lift === 'bench'
        ? 'var(--bench)'
        : 'var(--dead)'
  return (
    <span
      className="legend-dot"
      style={{ background: color, width: 10, height: 10 }}
    />
  )
}

export function EmptyState({ text }: { text: string }) {
  return <div className="mono" style={{ color: 'var(--fg-3)', padding: 16 }}>{text}</div>
}

export function Meter({ value, max = 100 }: { value: number; max?: number }) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100))
  return (
    <div className="meter">
      <span style={{ width: `${pct}%` }} />
    </div>
  )
}

export function PhaseStrip({ weeks }: { weeks: string[] }) {
  const color = (ph: string) => {
    switch (ph) {
      case 'hypertrophy': return 'var(--dead)'
      case 'strength': return 'var(--accent)'
      case 'peaking': return 'var(--bench)'
      case 'deload': return 'var(--fg-3)'
      default: return 'var(--line-2)'
    }
  }
  return (
    <div className="phases-strip">
      {weeks.map((ph, i) => (
        <span key={i} style={{ flex: 1, background: color(ph) }} />
      ))}
    </div>
  )
}

export function UseT() {
  const { t } = useTranslation()
  return { t }
}
