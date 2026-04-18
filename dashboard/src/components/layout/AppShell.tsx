import { Outlet, useOutletContext } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { useUsers } from '@/hooks/useUsers'
import { PlSidebar } from './Sidebar'
import { PlTopbar } from './Topbar'
import { useOverview } from '@/hooks/usePl'

export type ShellCtx = { userId: number }

export function useUserId(): number {
  return useOutletContext<ShellCtx>().userId
}

export function AppShell() {
  const { data: users } = useUsers()
  const [userId, setUserId] = useState(0)

  useEffect(() => {
    if (userId === 0 && users && users.length > 0) setUserId(users[0].id)
  }, [users, userId])

  const { data: overview } = useOverview(userId, 14)

  return (
    <div className="app">
      <PlSidebar />
      <PlTopbar nextMeet={overview?.next_meet} />
      <main className="main">
        {userId === 0 ? (
          <div className="card">Loading user…</div>
        ) : (
          <Outlet context={{ userId }} />
        )}
      </main>
    </div>
  )
}
