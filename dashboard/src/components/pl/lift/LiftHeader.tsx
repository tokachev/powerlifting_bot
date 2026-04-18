import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import type { Lift, LiftDetailResponse } from '@/api/pl_types'
import { LiftDot } from '../shared'

export function LiftHeader({ data }: { data: LiftDetailResponse }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const lifts: Lift[] = ['squat', 'bench', 'deadlift']
  const color =
    data.lift === 'squat'
      ? 'var(--squat)'
      : data.lift === 'bench'
        ? 'var(--bench)'
        : 'var(--dead)'

  return (
    <div className="card" style={{ padding: 20, position: 'relative' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <div className="seg" style={{ marginBottom: 12 }}>
            {lifts.map((l) => (
              <button
                key={l}
                className={l === data.lift ? 'on' : ''}
                onClick={() => navigate(`/lifts/${l}`)}
              >
                {t(l)}
              </button>
            ))}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
            <LiftDot lift={data.lift} />
            <span className="upper mono" style={{ color: 'var(--fg-2)' }}>
              {t(data.lift)} · {t('e1rm')}
            </span>
          </div>
          <div
            className="mono"
            style={{
              fontFamily: 'var(--f-disp)',
              fontSize: 72,
              fontWeight: 700,
              letterSpacing: '-0.04em',
              lineHeight: 0.95,
              color,
            }}
          >
            {data.current_e1rm_kg.toFixed(1)}
            <span style={{ fontSize: 22, color: 'var(--fg-2)', marginLeft: 8, fontWeight: 400 }}>
              {t('kg')}
            </span>
          </div>
          <div
            className="mono"
            style={{ fontSize: 12, color: 'var(--fg-2)', marginTop: 8, display: 'flex', gap: 16 }}
          >
            <span style={{ color: data.delta_pct >= 0 ? 'var(--good)' : 'var(--crit)', fontWeight: 600 }}>
              {data.delta_pct >= 0 ? '+' : ''}
              {data.delta_pct}% {t('vsPrev')}
            </span>
            <span>
              {t('pr')}: <b>{data.pr_kg.toFixed(1)}</b>
            </span>
            {data.target_kg > 0 && (
              <span>
                {t('target')}: <b>{data.target_kg.toFixed(1)}</b>
              </span>
            )}
            {data.pct_of_bw !== null && <span>%BW: {data.pct_of_bw.toFixed(1)}%</span>}
          </div>
        </div>
      </div>
    </div>
  )
}
