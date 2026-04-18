import { useTranslation } from 'react-i18next'
import type { Acwr } from '@/api/pl_types'
import { Card } from '../shared'

export function LoadIndex({ acwr }: { acwr: Acwr }) {
  const { t } = useTranslation()
  const pct = Math.round(acwr.ratio * 100)
  const clamped = Math.min(pct, 150)
  const zoneColor =
    acwr.risk_zone === 'sweet'
      ? 'var(--good)'
      : acwr.risk_zone === 'high'
        ? 'var(--warn)'
        : acwr.risk_zone === 'danger'
          ? 'var(--crit)'
          : 'var(--fg-3)'
  const r = 46
  const C = 2 * Math.PI * r
  const offset = C * (1 - clamped / 150)

  return (
    <Card title={t('loadIndex')}>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '120px 1fr',
          gap: 14,
          alignItems: 'center',
        }}
      >
        <svg viewBox="0 0 120 120" width={120} height={120}>
          <circle cx="60" cy="60" r={r} stroke="var(--bg-3)" strokeWidth="10" fill="none" />
          <circle
            cx="60"
            cy="60"
            r={r}
            stroke={zoneColor}
            strokeWidth="10"
            fill="none"
            strokeLinecap="round"
            strokeDasharray={C}
            strokeDashoffset={offset}
            transform="rotate(-90 60 60)"
          />
          <text
            x="60"
            y="65"
            textAnchor="middle"
            fill="var(--fg)"
            fontSize="22"
            fontFamily="var(--f-disp)"
            fontWeight="700"
          >
            {pct}%
          </text>
        </svg>
        <table className="tbl" style={{ fontSize: 11 }}>
          <tbody>
            <tr>
              <td className="muted">{t('acute')}</td>
              <td className="num">{acwr.acute_7d_kg.toFixed(0)} {t('kg')}</td>
            </tr>
            <tr>
              <td className="muted">{t('chronic')}</td>
              <td className="num">{acwr.chronic_28d_avg_kg.toFixed(0)} {t('kg')}</td>
            </tr>
            <tr>
              <td className="muted">{t('ratio')}</td>
              <td className="num">{acwr.ratio.toFixed(2)}</td>
            </tr>
            <tr>
              <td className="muted">{t('riskZone')}</td>
              <td style={{ color: zoneColor, textTransform: 'uppercase' }} className="mono">
                {t(acwr.risk_zone)}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </Card>
  )
}
