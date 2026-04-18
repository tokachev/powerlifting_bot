import { useTranslation } from 'react-i18next'
import type { NextMeetEcho } from '@/api/pl_types'
import { Card, EmptyState } from '../shared'

export function NextMeetCard({ nextMeet }: { nextMeet: NextMeetEcho | null }) {
  const { t } = useTranslation()
  if (!nextMeet) {
    return (
      <Card title={t('nextMeet')}>
        <EmptyState text={t('noData')} />
      </Card>
    )
  }
  const lifts: Array<'squat' | 'bench' | 'deadlift'> = ['squat', 'bench', 'deadlift']
  return (
    <Card
      title={t('attempts')}
      meta={`${nextMeet.days_left} ${t('daysOutShort')} · ${nextMeet.name}`}
    >
      {lifts.map((lift) => {
        const att = nextMeet.attempts_kg[lift] ?? []
        return (
          <div className="attempt-row" key={lift}>
            <span className="lift-label">{t(lift)}</span>
            {[0, 1, 2].map((i) => {
              const cls = i === 0 ? 'opener' : i === 1 ? 'second' : 'third'
              return (
                <div className={`attempt-box ${cls}`} key={i}>
                  <div className="a-n">{i + 1}</div>
                  <div className="a-v mono">
                    {att[i] !== undefined ? att[i].toFixed(1) : '—'}
                  </div>
                </div>
              )
            })}
          </div>
        )
      })}
    </Card>
  )
}
