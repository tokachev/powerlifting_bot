import { useParams, Navigate } from 'react-router-dom'
import { useUserId } from '@/components/layout/AppShell'
import { useLiftDetail } from '@/hooks/usePl'
import type { Lift } from '@/api/pl_types'
import { LiftHeader } from '@/components/pl/lift/LiftHeader'
import {
  BarVelocityChart,
  E1RMProgressionChart,
  LiftIntensityChart,
  LiftTonnageChart,
} from '@/components/pl/lift/LiftCharts'
import { RepMaxTable } from '@/components/pl/lift/RepMaxTable'
import { SetRecommendations } from '@/components/pl/lift/SetRecommendations'
import { AllTimePRs } from '@/components/pl/lift/AllTimePRs'
import { TechniqueNotes } from '@/components/pl/lift/TechniqueNotes'
import { LoadIndex } from '@/components/pl/lift/LoadIndex'

const VALID_LIFTS: Lift[] = ['squat', 'bench', 'deadlift']

export default function PlLiftDetail() {
  const { lift } = useParams<{ lift: string }>()
  const userId = useUserId()
  if (!lift || !VALID_LIFTS.includes(lift as Lift)) {
    return <Navigate to="/lifts/squat" replace />
  }
  const { data, isLoading, isError, error } = useLiftDetail(userId, lift as Lift, 14)

  if (isLoading) return <div className="card">Loading…</div>
  if (isError) return <div className="card">Error: {(error as Error)?.message}</div>
  if (!data) return null

  return (
    <>
      <LiftHeader data={data} />
      <E1RMProgressionChart weekly={data.weekly} target={data.target_kg} lift={data.lift} />

      <div className="row cols-3">
        <LiftTonnageChart weekly={data.weekly} lift={data.lift} />
        <LiftIntensityChart weekly={data.weekly} lift={data.lift} />
        <BarVelocityChart weekly={data.weekly} lift={data.lift} />
      </div>

      <RepMaxTable entries={data.rep_max} />
      <SetRecommendations items={data.set_recommendations} />

      <div className="row cols-2">
        <AllTimePRs items={data.all_prs} />
        <div className="row" style={{ gridTemplateRows: 'auto auto', gap: 'var(--gap)' }}>
          <TechniqueNotes items={data.technique_notes} />
          <LoadIndex acwr={data.acwr} />
        </div>
      </div>
    </>
  )
}
