import { useTranslation } from 'react-i18next'
import { useUserId } from '@/components/layout/AppShell'
import { useOverview } from '@/hooks/usePl'
import { KpiStrip } from '@/components/pl/dashboard/KpiStrip'
import { Big3Hero } from '@/components/pl/dashboard/Big3Hero'
import { TonnageByLift } from '@/components/pl/dashboard/TonnageByLift'
import { IntensityChart } from '@/components/pl/dashboard/IntensityChart'
import { TrainingCalendar } from '@/components/pl/dashboard/TrainingCalendar'
import { ReadinessWidget } from '@/components/pl/dashboard/ReadinessWidget'
import { RecentSessions } from '@/components/pl/dashboard/RecentSessions'
import { NextMeetCard } from '@/components/pl/dashboard/NextMeetCard'
import { AccessoriesBars } from '@/components/pl/dashboard/AccessoriesBars'
import { NigglesWidget } from '@/components/pl/dashboard/NigglesWidget'
import { BodyweightTrend } from '@/components/pl/dashboard/BodyweightTrend'

export default function PlDashboard() {
  const userId = useUserId()
  const { t } = useTranslation()
  const { data, isLoading, isError, error } = useOverview(userId, 14)

  if (isLoading) return <div className="card">Loading…</div>
  if (isError) return <div className="card">Error: {(error as Error)?.message}</div>
  if (!data) return null

  const phaseWeeks = data.tonnage_by_lift.squat.map((p) => p.phase)

  return (
    <>
      <KpiStrip kpi={data.kpi} nextMeet={data.next_meet} />
      <Big3Hero big3={data.big3} byLift={data.tonnage_by_lift} />

      <div className="row cols-2">
        <TonnageByLift data={data.tonnage_by_lift} phases={phaseWeeks} />
        <ReadinessWidget data={data.readiness} />
      </div>

      <div className="row cols-4">
        <IntensityChart data={data.intensity_by_lift} />
        <TrainingCalendar cells={data.calendar} />
      </div>

      <div className="row cols-2">
        <RecentSessions sessions={data.recent_sessions} />
        <NextMeetCard nextMeet={data.next_meet} />
      </div>

      <div className="row cols-2">
        <AccessoriesBars items={data.accessories} />
        <div className="row" style={{ gridTemplateRows: 'auto auto', gap: 'var(--gap)' }}>
          <NigglesWidget items={data.niggles} />
          <BodyweightTrend points={data.bodyweight_trend} />
        </div>
      </div>
      <div className="hr" />
      <div className="mono" style={{ color: 'var(--fg-3)', fontSize: 10 }}>
        {t('today')} · {new Date().toLocaleDateString()}
      </div>
    </>
  )
}
