import { Activity, ClipboardCheck, FileUp, LayoutDashboard, Network, ShieldCheck, Siren } from 'lucide-react'
import { NavLink, Outlet } from 'react-router-dom'
import { useHealth } from '../../hooks/useApiQueries'
import { apiBaseUrl } from '../../lib/api/endpoints'
import { safeErrorMessage } from '../../lib/api/errors'

const links = [
  { to: '/', label: 'Operations overview', icon: LayoutDashboard },
  { to: '/alerts', label: 'Alerts & review', icon: Siren },
  { to: '/simulation', label: 'What-if simulation', icon: Activity },
  { to: '/ingestion', label: 'Signal ingestion', icon: FileUp },
  { to: '/audit', label: 'Audit integrity', icon: ShieldCheck },
  { to: '/integrations', label: 'AI ecosystem & integrations', icon: Network },
]

export function AppShell() {
  const health = useHealth()
  const connected = health.isSuccess && health.data.status === 'ok'
  return <div className="min-h-screen bg-paper text-slate-900">
    <header className="border-b border-slate-200 bg-ink text-white">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-4 sm:px-6 lg:px-8">
        <div className="flex items-center gap-3"><div className="rounded-lg bg-teal p-2"><ClipboardCheck size={21} aria-hidden="true" /></div><div><p className="text-sm font-semibold tracking-wide">PULSEREADY 4S</p><p className="text-xs text-slate-300">Synthetic operations command center</p></div></div>
        <div className="flex items-center gap-2 text-xs" title={health.isError ? safeErrorMessage(health.error) : `Backend: ${apiBaseUrl()}`}><span className={`h-2.5 w-2.5 rounded-full ${connected ? 'bg-emerald-400' : 'bg-amber-300'}`} />{connected ? 'Backend connected' : health.isLoading ? 'Checking backend…' : 'Backend unavailable'}</div>
      </div>
    </header>
    <div className="mx-auto flex max-w-7xl flex-col gap-6 px-4 py-6 sm:px-6 lg:flex-row lg:px-8">
      <aside className="lg:w-64 lg:shrink-0"><nav aria-label="Primary navigation" className="flex gap-2 overflow-x-auto lg:flex-col lg:overflow-visible">{links.map(({ to, label, icon: Icon }) => <NavLink key={to} to={to} end={to === '/'} className={({ isActive }) => `flex min-w-max items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition ${isActive ? 'bg-ink text-white shadow-panel' : 'text-slate-600 hover:bg-white hover:text-ink'}`}><Icon size={18} aria-hidden="true" />{label}</NavLink>)}</nav></aside>
      <main className="min-w-0 flex-1"><Outlet /></main>
    </div>
    <footer className="mx-auto max-w-7xl px-4 pb-6 text-xs text-slate-400 sm:px-6 lg:px-8">Decisions and readiness values come from the FastAPI backend. This interface displays synthetic demo data only.</footer>
  </div>
}
