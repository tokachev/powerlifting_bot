import { NavLink } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { BarChart3, CalendarClock, History, Settings, Weight } from 'lucide-react'

export function PlSidebar() {
  const { t } = useTranslation()
  const items: { to: string; icon: JSX.Element; label: string; disabled?: boolean }[] = [
    { to: '/', icon: <BarChart3 className="icon" />, label: t('dashboard') },
    { to: '/lifts/squat', icon: <Weight className="icon" />, label: t('lifts') },
    { to: '/history', icon: <History className="icon" />, label: t('history') },
    { to: '/planner', icon: <CalendarClock className="icon" />, label: t('planner'), disabled: true },
    { to: '/settings', icon: <Settings className="icon" />, label: t('settings'), disabled: true },
  ]
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark">P</div>
        <div>
          <div className="brand-name">{t('brand')}</div>
          <div className="brand-sub">{t('brandSub')}</div>
        </div>
      </div>
      <div className="nav-section">{t('dashboard')}</div>
      {items.map((it) =>
        it.disabled ? (
          <div key={it.to} className="nav-item" style={{ opacity: 0.4, cursor: 'not-allowed' }}>
            {it.icon}
            <span>{it.label}</span>
          </div>
        ) : (
          <NavLink
            key={it.to}
            to={it.to}
            end={it.to === '/'}
            className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
          >
            {it.icon}
            <span>{it.label}</span>
          </NavLink>
        ),
      )}
      <div className="nav-foot">pwrbot · local<br />v0.2</div>
    </aside>
  )
}
