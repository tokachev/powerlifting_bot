import { useUsers } from '@/hooks/useUsers'
import {
  MOVEMENT_PATTERNS,
  MOVEMENT_PATTERN_LABELS,
  MUSCLE_GROUPS,
  MUSCLE_GROUP_LABELS,
} from '@/api/types'
import type { DashboardQuery } from '@/api/types'

interface Props {
  value: DashboardQuery
  onChange: (next: DashboardQuery) => void
}

function toggle<T>(arr: T[], v: T): T[] {
  return arr.includes(v) ? arr.filter((x) => x !== v) : [...arr, v]
}

export function Sidebar({ value, onChange }: Props) {
  const { data: users, isLoading: usersLoading } = useUsers()

  return (
    <aside className="w-64 shrink-0 border-r border-neutral-800 bg-neutral-900 p-4 space-y-6 overflow-y-auto">
      <div>
        <h2 className="text-xs uppercase tracking-wider text-neutral-400 mb-2">User</h2>
        <select
          className="w-full bg-neutral-800 border border-neutral-700 rounded px-2 py-1 text-sm"
          value={value.user_id || ''}
          onChange={(e) => onChange({ ...value, user_id: Number(e.target.value) })}
          disabled={usersLoading}
        >
          <option value="">— select user —</option>
          {users?.map((u) => (
            <option key={u.id} value={u.id}>
              {u.display_name ?? `tg:${u.telegram_id}`} (#{u.id})
            </option>
          ))}
        </select>
      </div>

      <div>
        <h2 className="text-xs uppercase tracking-wider text-neutral-400 mb-2">Period</h2>
        <label className="block text-xs text-neutral-400 mb-1">Since</label>
        <input
          type="date"
          className="w-full bg-neutral-800 border border-neutral-700 rounded px-2 py-1 text-sm mb-2"
          value={value.since}
          onChange={(e) => onChange({ ...value, since: e.target.value })}
        />
        <label className="block text-xs text-neutral-400 mb-1">Until</label>
        <input
          type="date"
          className="w-full bg-neutral-800 border border-neutral-700 rounded px-2 py-1 text-sm"
          value={value.until}
          onChange={(e) => onChange({ ...value, until: e.target.value })}
        />
      </div>

      <div>
        <label className="flex items-center gap-2 text-sm cursor-pointer">
          <input
            type="checkbox"
            checked={value.target_only}
            onChange={(e) => onChange({ ...value, target_only: e.target.checked })}
            className="w-4 h-4"
          />
          <span>Только SBD (присед/жим/становая)</span>
        </label>
      </div>

      <div>
        <h2 className="text-xs uppercase tracking-wider text-neutral-400 mb-2">Мышечные группы</h2>
        <div className="space-y-1">
          {MUSCLE_GROUPS.map((m) => (
            <label key={m} className="flex items-center gap-2 text-sm cursor-pointer">
              <input
                type="checkbox"
                checked={value.muscle_groups.includes(m)}
                onChange={() => onChange({ ...value, muscle_groups: toggle(value.muscle_groups, m) })}
                className="w-4 h-4"
              />
              <span>{MUSCLE_GROUP_LABELS[m] ?? m}</span>
            </label>
          ))}
        </div>
      </div>

      <div>
        <h2 className="text-xs uppercase tracking-wider text-neutral-400 mb-2">Movement pattern</h2>
        <div className="space-y-1">
          {MOVEMENT_PATTERNS.map((p) => (
            <label key={p} className="flex items-center gap-2 text-sm cursor-pointer">
              <input
                type="checkbox"
                checked={value.movement_patterns.includes(p)}
                onChange={() =>
                  onChange({
                    ...value,
                    movement_patterns: toggle(value.movement_patterns, p),
                  })
                }
                className="w-4 h-4"
              />
              <span>{MOVEMENT_PATTERN_LABELS[p] ?? p}</span>
            </label>
          ))}
        </div>
      </div>
    </aside>
  )
}
