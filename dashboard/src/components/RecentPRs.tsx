import type { PRsResponse } from '@/api/types'
import { E1RM_EXERCISE_LABELS } from '@/api/types'

interface Props {
  data: PRsResponse
}

function fmtWeight(kg: number): string {
  return kg === Math.floor(kg) ? String(kg) : kg.toFixed(1)
}

export function RecentPRs({ data }: Props) {
  if (data.records.length === 0) {
    return (
      <div className="glass-card">
        <h3 className="chart-title">Рекорды</h3>
        <div className="text-neutral-500 text-sm py-8 text-center">Нет рекордов</div>
      </div>
    )
  }

  return (
    <div className="glass-card">
      <h3 className="chart-title">Рекорды</h3>
      <div className="overflow-x-auto">
        <table className="w-full text-sm text-left">
          <thead>
            <tr className="text-neutral-500 border-b border-white/[0.06]">
              <th className="py-2 font-medium">Дата</th>
              <th className="py-2 font-medium">Упражнение</th>
              <th className="py-2 font-medium">Подход</th>
              <th className="py-2 font-medium">e1RM</th>
              <th className="py-2 font-medium">Дельта</th>
            </tr>
          </thead>
          <tbody>
            {data.records.map((r, i) => {
              const name = E1RM_EXERCISE_LABELS[r.canonical_name] ?? r.canonical_name
              const delta = r.previous_1rm_kg != null
                ? `+${fmtWeight(r.estimated_1rm_kg - r.previous_1rm_kg)}`
                : 'первый'
              return (
                <tr key={i} className="border-b border-white/[0.04]">
                  <td className="py-1.5 text-neutral-400">{r.date}</td>
                  <td className="py-1.5">{name}</td>
                  <td className="py-1.5">{fmtWeight(r.weight_kg)} x {r.reps}</td>
                  <td className="py-1.5 text-accent-light">{fmtWeight(r.estimated_1rm_kg)} кг</td>
                  <td className="py-1.5 text-green-400">{delta}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
