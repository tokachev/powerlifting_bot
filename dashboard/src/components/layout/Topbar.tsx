import { useLocation } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Download, Plus, Settings2 } from 'lucide-react'
import { useState } from 'react'
import { TweaksPanel } from './TweaksPanel'
import type { NextMeetEcho } from '@/api/pl_types'

interface Props {
  nextMeet?: NextMeetEcho | null
}

export function PlTopbar({ nextMeet }: Props) {
  const { pathname } = useLocation()
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)

  const crumb = pathname.startsWith('/lifts')
    ? t('lifts')
    : pathname.startsWith('/history')
      ? t('history')
      : t('dashboard')

  return (
    <>
      <header className="topbar">
        <nav className="crumbs">
          <span>pwrbot</span>
          <span className="sep">/</span>
          <span className="cur">{crumb}</span>
        </nav>
        <div className="top-right">
          {nextMeet && (
            <span className="pill">
              <span className="dot" />
              {nextMeet.name} · {nextMeet.days_left} {t('daysOutShort')}
            </span>
          )}
          <button className="btn ghost" onClick={() => setOpen((v) => !v)} aria-label="tweaks">
            <Settings2 size={14} /> {t('tweaks')}
          </button>
          <button className="btn ghost">
            <Download size={14} /> {t('export')}
          </button>
          <button className="btn primary">
            <Plus size={14} /> {t('logSession')}
          </button>
        </div>
      </header>
      <TweaksPanel open={open} onClose={() => setOpen(false)} />
    </>
  )
}
