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
    <aside className="w-64 shrink-0 border-r border-white/[0.06] bg-surface-1 p-5 space-y-6 overflow-y-auto relative">
      <div className="absolute inset-x-0 top-0 h-32 bg-gradient-to-b from-accent/[0.06] to-transparent pointer-events-none" />

      <div className="relative flex items-center gap-2 pb-4 mb-2 border-b border-white/[0.06]">
        <div className="w-8 h-8 rounded-lg bg-accent/20 flex items-center justify-center">
          <span className="text-accent-light font-bold text-sm">P</span>
        </div>
        <div>
          <div className="text-sm font-semibold">pwrbot</div>
          <div className="text-[10px] text-neutral-500">training analytics</div>
        </div>
      </div>

      <div className="relative">
        <h2 className="sidebar-label">User</h2>
        <select
          className="sidebar-input appearance-none cursor-pointer"
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

      <div className="relative border-t border-white/[0.04] pt-5">
        <h2 className="sidebar-label">Period</h2>
        <label className="block text-xs text-neutral-500 mb-1.5 font-medium">Since</label>
        <input
          type="date"
          className="sidebar-input mb-2"
          value={value.since}
          onChange={(e) => onChange({ ...value, since: e.target.value })}
        />
        <label className="block text-xs text-neutral-500 mb-1.5 font-medium">Until</label>
        <input
          type="date"
          className="sidebar-input"
          value={value.until}
          onChange={(e) => onChange({ ...value, until: e.target.value })}
        />
      </div>

      <div className="relative border-t border-white/[0.04] pt-5">
        <label className="flex items-center gap-2 text-sm cursor-pointer text-neutral-300 hover:text-neutral-100 transition-colors">
          <input
            type="checkbox"
            checked={value.target_only}
            onChange={(e) => onChange({ ...value, target_only: e.target.checked })}
            className="w-4 h-4 accent-indigo-500"
          />
          <span>Только SBD (присед/жим/становая)</span>
        </label>
      </div>

      <div className="relative border-t border-white/[0.04] pt-5">
        <h2 className="sidebar-label">Мышечные группы</h2>
        <div className="space-y-1.5">
          {MUSCLE_GROUPS.map((m) => (
            <label key={m} className="flex items-center gap-2 text-sm cursor-pointer text-neutral-300 hover:text-neutral-100 transition-colors">
              <input
                type="checkbox"
                checked={value.muscle_groups.includes(m)}
                onChange={() => onChange({ ...value, muscle_groups: toggle(value.muscle_groups, m) })}
                className="w-4 h-4 accent-indigo-500"
              />
              <span>{MUSCLE_GROUP_LABELS[m] ?? m}</span>
            </label>
          ))}
        </div>
      </div>

      <div className="relative border-t border-white/[0.04] pt-5">
        <h2 className="sidebar-label">Movement pattern</h2>
        <div className="space-y-1.5">
          {MOVEMENT_PATTERNS.map((p) => (
            <label key={p} className="flex items-center gap-2 text-sm cursor-pointer text-neutral-300 hover:text-neutral-100 transition-colors">
              <input
                type="checkbox"
                checked={value.movement_patterns.includes(p)}
                onChange={() =>
                  onChange({
                    ...value,
                    movement_patterns: toggle(value.movement_patterns, p),
                  })
                }
                className="w-4 h-4 accent-indigo-500"
              />
              <span>{MOVEMENT_PATTERN_LABELS[p] ?? p}</span>
            </label>
          ))}
        </div>
      </div>
    </aside>
  )
}
