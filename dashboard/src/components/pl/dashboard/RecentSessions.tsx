import { useTranslation } from 'react-i18next'
import type { RecentSessionItem } from '@/api/pl_types'
import { Card, EmptyState } from '../shared'

export function RecentSessions({ sessions }: { sessions: RecentSessionItem[] }) {
  const { t } = useTranslation()
  if (sessions.length === 0) {
    return (
      <Card title={t('recentSessions')}>
        <EmptyState text={t('noData')} />
      </Card>
    )
  }
  const tagClass = (focus: string) =>
    focus === 'squat' ? 'squat' : focus === 'bench' ? 'bench' : focus === 'deadlift' ? 'dead' : ''
  return (
    <Card title={t('recentSessions')} meta={`${sessions.length}`}>
      <table className="tbl">
        <thead>
          <tr>
            <th>{t('date')}</th>
            <th>{t('focus')}</th>
            <th>{t('topSet')}</th>
            <th>{t('volume')}</th>
            <th>{t('rpe')}</th>
          </tr>
        </thead>
        <tbody>
          {sessions.map((s, i) => (
            <tr key={i}>
              <td className="num">{s.date}</td>
              <td>
                <span className={`tag ${tagClass(s.focus)}`}>{t(s.focus) || s.focus}</span>
              </td>
              <td className="num">
                {s.top_set_kg.toFixed(1)}×{s.top_set_reps}
              </td>
              <td className="num">{s.total_volume_kg.toFixed(0)}</td>
              <td className="num">{s.avg_rpe?.toFixed(1) ?? '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  )
}
