import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { ThemeProvider } from './theme/ThemeProvider'
import { AppShell } from './components/layout/AppShell'
import PlDashboardPage from './pages/PlDashboard'
import PlLiftDetailPage from './pages/PlLiftDetail'
import PlHistoryPage from './pages/PlHistory'
import LegacyDashboard from './pages/Dashboard'
import './i18n'

export default function App() {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/legacy" element={<LegacyDashboard />} />
          <Route element={<AppShell />}>
            <Route path="/" element={<PlDashboardPage />} />
            <Route path="/lifts/:lift" element={<PlLiftDetailPage />} />
            <Route path="/history" element={<PlHistoryPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ThemeProvider>
  )
}
