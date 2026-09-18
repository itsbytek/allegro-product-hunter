import { useEffect, useState } from 'react'
import { BarChart3, FileWarning, LayoutDashboard, ScrollText, Settings, Zap } from 'lucide-react'
import Dashboard from './components/Dashboard'
import LogsPage from './components/LogsPage'
import SettingsPage from './components/SettingsPage'
import VerificationPage from './components/VerificationPage'

type Page = 'dashboard' | 'verification' | 'logs' | 'settings'

const navigation: Array<{ id: Page; label: string; icon: typeof LayoutDashboard }> = [
  { id: 'dashboard', label: 'Research', icon: LayoutDashboard },
  { id: 'verification', label: 'Weryfikacja', icon: FileWarning },
  { id: 'logs', label: 'System Logs', icon: ScrollText },
  { id: 'settings', label: 'Ustawienia', icon: Settings },
]

export default function App() {
  const [page, setPage] = useState<Page>('dashboard')
  const [online, setOnline] = useState(true)

  useEffect(() => {
    const update = () => setOnline(navigator.onLine)
    window.addEventListener('online', update)
    window.addEventListener('offline', update)
    return () => {
      window.removeEventListener('online', update)
      window.removeEventListener('offline', update)
    }
  }, [])

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark"><Zap size={18} /></span>
          <div><strong>Product Hunter</strong><small>ALLEGRO RESEARCH</small></div>
        </div>
        <nav>
          {navigation.map((item) => {
            const Icon = item.icon
            return <button className={page === item.id ? 'active' : ''} key={item.id} onClick={() => setPage(item.id)}><Icon size={17} />{item.label}</button>
          })}
        </nav>
        <div className="sidebar-spacer" />
        <div className="system-state"><span className={`dot ${online ? 'ok' : 'bad'}`} /><div><strong>{online ? 'System online' : 'Brak internetu'}</strong><small>Local-first · SQLite</small></div></div>
        <div className="version"><BarChart3 size={14} /> v0.1.0 · AI OFF</div>
      </aside>
      <main className="main-area">
        {page === 'dashboard' && <Dashboard />}
        {page === 'verification' && <VerificationPage />}
        {page === 'logs' && <LogsPage />}
        {page === 'settings' && <SettingsPage />}
      </main>
    </div>
  )
}

