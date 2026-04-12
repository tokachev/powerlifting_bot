import { useMemo } from 'react'
import { format, startOfWeek, addDays, differenceInWeeks, parseISO } from 'date-fns'
import type { CalendarResponse } from '@/api/types'

interface Props {
  data: CalendarResponse
  since: string
  until: string
}

const DAY_NAMES = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
const CELL = 14
const GAP = 2
const STEP = CELL + GAP

function intensityColor(tonnage: number, max: number): string {
  if (tonnage === 0) return 'rgba(255,255,255,0.04)'
  const t = Math.min(tonnage / (max || 1), 1)
  // from dim blue to bright blue
  const alpha = 0.15 + t * 0.85
  return `rgba(59, 130, 246, ${alpha.toFixed(2)})`
}

export function CalendarHeatmap({ data, since, until }: Props) {
  const { cells, weeks, maxTonnage } = useMemo(() => {
    const byDate = new Map<string, { tonnage: number; sets: number }>()
    let maxTonnage = 0
    for (const d of data.days) {
      byDate.set(d.date, { tonnage: d.total_tonnage_kg, sets: d.total_sets })
      if (d.total_tonnage_kg > maxTonnage) maxTonnage = d.total_tonnage_kg
    }

    const sinceDate = parseISO(since)
    const untilDate = parseISO(until)
    const weekStart = startOfWeek(sinceDate, { weekStartsOn: 1 })
    const totalWeeks = differenceInWeeks(untilDate, weekStart) + 2

    const cells: Array<{
      x: number; y: number; date: string
      tonnage: number; sets: number
    }> = []

    for (let w = 0; w < totalWeeks; w++) {
      for (let d = 0; d < 7; d++) {
        const day = addDays(weekStart, w * 7 + d)
        if (day < sinceDate || day > untilDate) continue
        const key = format(day, 'yyyy-MM-dd')
        const val = byDate.get(key)
        cells.push({
          x: w * STEP,
          y: d * STEP,
          date: key,
          tonnage: val?.tonnage ?? 0,
          sets: val?.sets ?? 0,
        })
      }
    }

    return { cells, weeks: totalWeeks, maxTonnage }
  }, [data, since, until])

  if (data.days.length === 0) {
    return (
      <div className="glass-card">
        <h3 className="chart-title">Активность</h3>
        <div className="text-neutral-500 text-sm py-8 text-center">Нет данных</div>
      </div>
    )
  }

  const svgWidth = weeks * STEP + 30
  const svgHeight = 7 * STEP + 8

  return (
    <div className="glass-card">
      <h3 className="chart-title">Активность</h3>
      <div className="overflow-x-auto">
        <svg width={svgWidth} height={svgHeight} className="mx-auto">
          {DAY_NAMES.map((name, i) => (
            i % 2 === 0 ? (
              <text
                key={name}
                x={0}
                y={i * STEP + CELL}
                fontSize={9}
                fill="rgba(255,255,255,0.3)"
              >
                {name}
              </text>
            ) : null
          ))}
          {cells.map((c) => (
            <rect
              key={c.date}
              x={c.x + 24}
              y={c.y}
              width={CELL}
              height={CELL}
              rx={3}
              fill={intensityColor(c.tonnage, maxTonnage)}
            >
              <title>{`${c.date}: ${Math.round(c.tonnage)} кг, ${c.sets} сетов`}</title>
            </rect>
          ))}
        </svg>
      </div>
    </div>
  )
}
