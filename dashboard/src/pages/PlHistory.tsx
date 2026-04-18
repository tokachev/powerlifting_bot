import { useUserId } from '@/components/layout/AppShell'
import { useHistory } from '@/hooks/usePl'
import { HistoryKpiStrip } from '@/components/pl/history/HistoryKpi'
import { TotalByMeetChart } from '@/components/pl/history/TotalByMeetChart'
import { MeetHistoryTable } from '@/components/pl/history/MeetHistoryTable'
import { WilksDotsChart } from '@/components/pl/history/WilksDotsChart'
import { RmGrowthCards } from '@/components/pl/history/RmGrowthCards'
import { PersonalRecordsCards } from '@/components/pl/history/PersonalRecordsCards'
import { BestTotalsRow } from '@/components/pl/history/BestTotalsRow'

export default function PlHistory() {
  const userId = useUserId()
  const { data, isLoading, isError, error } = useHistory(userId)
  if (isLoading) return <div className="card">Loading…</div>
  if (isError) return <div className="card">Error: {(error as Error)?.message}</div>
  if (!data) return null

  return (
    <>
      <HistoryKpiStrip kpi={data.kpi} />
      <TotalByMeetChart meets={data.meets} />
      <MeetHistoryTable meets={data.meets} bestTotal={data.best_total_kg} />
      <WilksDotsChart meets={data.meets} />
      <RmGrowthCards items={data.rm_growth} />
      <PersonalRecordsCards items={data.personal_records} />
      <BestTotalsRow bestTotalKg={data.best_total_kg} bestGymTotalKg={data.best_gym_total_kg} />
    </>
  )
}
