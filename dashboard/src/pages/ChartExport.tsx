import type React from 'react'
import { useSearchParams, useParams } from 'react-router-dom'
import { useLiftDetail, useOverview } from '@/hooks/usePl'
import type { Lift } from '@/api/pl_types'
import { TonnageByLift } from '@/components/pl/dashboard/TonnageByLift'
import { IntensityChart } from '@/components/pl/dashboard/IntensityChart'
import { BodyweightTrend } from '@/components/pl/dashboard/BodyweightTrend'
import {
  E1RMProgressionChart,
  LiftIntensityChart,
  LiftTonnageChart,
} from '@/components/pl/lift/LiftCharts'

const VALID_LIFTS: Lift[] = ['squat', 'bench', 'deadlift']
const OVERVIEW_CHARTS = new Set(['overview-tonnage', 'overview-intensity', 'bodyweight-trend'])
const LIFT_CHARTS = new Set(['lift-e1rm', 'lift-tonnage', 'lift-intensity'])

function asPositiveInt(value: string | null, fallback: number) {
  const parsed = Number(value)
  return Number.isInteger(parsed) && parsed > 0 ? parsed : fallback
}

function asWeeks(value: string | null) {
  const parsed = asPositiveInt(value, 14)
  return Math.max(4, Math.min(52, parsed))
}

function asLift(value: string | null): Lift {
  return VALID_LIFTS.includes(value as Lift) ? (value as Lift) : 'squat'
}

export default function ChartExportPage() {
  const { chartId = '' } = useParams<{ chartId: string }>()
  const [params] = useSearchParams()
  const userId = asPositiveInt(params.get('user_id'), 0)
  const weeks = asWeeks(params.get('weeks'))
  const lift = asLift(params.get('lift'))

  if (!OVERVIEW_CHARTS.has(chartId) && !LIFT_CHARTS.has(chartId)) {
    return <ExportFrame status="error">Unknown chart: {chartId}</ExportFrame>
  }
  if (userId <= 0) {
    return <ExportFrame status="error">Missing user_id</ExportFrame>
  }
  if (OVERVIEW_CHARTS.has(chartId)) {
    return <OverviewChartExport chartId={chartId} userId={userId} weeks={weeks} />
  }
  return <LiftChartExport chartId={chartId} userId={userId} weeks={weeks} lift={lift} />
}

function ExportFrame({
  children,
  status,
}: {
  children: React.ReactNode
  status: 'ready' | 'loading' | 'error'
}) {
  return (
    <div
      data-chart-export={status}
      style={{
        width: 1040,
        padding: 24,
        background: 'var(--bg)',
        color: 'var(--fg)',
      }}
    >
      <div data-chart-export-content style={{ width: '100%' }}>
        {children}
      </div>
    </div>
  )
}

function OverviewChartExport({
  chartId,
  userId,
  weeks,
}: {
  chartId: string
  userId: number
  weeks: number
}) {
  const { data, isLoading, isError, error } = useOverview(userId, weeks)
  if (isLoading) return <ExportFrame status="loading">Loading…</ExportFrame>
  if (isError) return <ExportFrame status="error">Error: {(error as Error)?.message}</ExportFrame>
  if (!data) return <ExportFrame status="error">No data</ExportFrame>

  const phaseWeeks = data.tonnage_by_lift.squat.map((p) => p.phase)
  return (
    <ExportFrame status="ready">
      {chartId === 'overview-tonnage' && (
        <TonnageByLift data={data.tonnage_by_lift} phases={phaseWeeks} />
      )}
      {chartId === 'overview-intensity' && <IntensityChart data={data.intensity_by_lift} />}
      {chartId === 'bodyweight-trend' && <BodyweightTrend points={data.bodyweight_trend} />}
    </ExportFrame>
  )
}

function LiftChartExport({
  chartId,
  userId,
  weeks,
  lift,
}: {
  chartId: string
  userId: number
  weeks: number
  lift: Lift
}) {
  const { data, isLoading, isError, error } = useLiftDetail(userId, lift, weeks)
  if (isLoading) return <ExportFrame status="loading">Loading…</ExportFrame>
  if (isError) return <ExportFrame status="error">Error: {(error as Error)?.message}</ExportFrame>
  if (!data) return <ExportFrame status="error">No data</ExportFrame>

  return (
    <ExportFrame status="ready">
      {chartId === 'lift-e1rm' && (
        <E1RMProgressionChart weekly={data.weekly} target={data.target_kg} lift={data.lift} />
      )}
      {chartId === 'lift-tonnage' && <LiftTonnageChart weekly={data.weekly} lift={data.lift} />}
      {chartId === 'lift-intensity' && <LiftIntensityChart weekly={data.weekly} lift={data.lift} />}
    </ExportFrame>
  )
}
