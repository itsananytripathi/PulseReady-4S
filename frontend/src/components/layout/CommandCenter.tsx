import type { ReactNode } from 'react'
import { Activity, Database, FileUp, LayoutDashboard, Network, ShieldCheck, Wifi } from 'lucide-react'
import { NavLink, Outlet } from 'react-router-dom'
import { useHealth } from '../../hooks/useApiQueries'
import { apiBaseUrl } from '../../lib/api/endpoints'
import { safeErrorMessage } from '../../lib/api/errors'

const links = [
  { to: '/', label: 'Command Center', icon: LayoutDashboard },
  { to: '/simulation', label: 'Sim Sandbox', icon: Activity },
  { to: '/ingestion', label: 'Pipeline Hub', icon: FileUp },
  { to: '/audit', label: 'Audit Ledger', icon: ShieldCheck },
  { to: '/integrations', label: 'AI Ecosystem', icon: Network },
]

export function Panel({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <section className={`border border-line bg-panel shadow-panel ${className}`}>{children}</section>
}

export function Eyebrow({ children }: { children: ReactNode }) {
  return <p className="mono text-[10px] uppercase tracking-[0.18em] text-muted">{children}</p>
}

export function Badge({ children, tone = 'neutral' }: { children: ReactNode; tone?: 'healthy' | 'warning' | 'critical' | 'neutral' }) {
  const tones = { healthy: 'border-teal/40 bg-teal/10 text-teal', warning: 'border-amber/40 bg-amber/10 text-amber', critical: 'border-danger/40 bg-danger/10 text-danger', neutral: 'border-line bg-raised text-muted' }
  return <span className={`inline-flex items-center border px-2 py-1 mono text-[10px] uppercase tracking-wider ${tones[tone]}`}>{children}</span>
}

export function MetricCard({ label, value, detail, tone = 'cyan' }: { label: string; value: string; detail?: string; tone?: 'cyan' | 'healthy' | 'warning' | 'critical' }) {
  const colors = { cyan: 'text-cyan', healthy: 'text-teal', warning: 'text-amber', critical: 'text-danger' }
  return <div className="min-h-[92px] border border-line bg-panel p-3"><Eyebrow>{label}</Eyebrow><p className={`mono mt-3 text-2xl font-semibold ${colors[tone]}`}>{value}</p>{detail && <p className="mt-1 text-[11px] text-muted">{detail}</p>}</div>
}

export function Bar({ value, tone = 'healthy' }: { value: number; tone?: 'healthy' | 'warning' | 'critical' }) {
  const colors = { healthy: 'bg-teal', warning: 'bg-amber', critical: 'bg-danger' }
  return <div className="h-2 bg-raised"><div className={`h-full ${colors[tone]}`} style={{ width: `${Math.min(100, Math.max(0, value))}%` }} /></div>
}

export function Unavailable({ label = 'Not provided by API' }: { label?: string }) {
  return <span className="mono text-[10px] uppercase tracking-wider text-muted">{label}</span>
}

export function CommandCenter() {
  const health = useHealth()
  const connected = health.isSuccess && health.data.status === 'ok'
  return <div className="min-h-screen bg-ink text-slate-100">
    <header className="sticky top-0 z-10 border-b border-line bg-nav/95 backdrop-blur">
      <div className="mx-auto flex max-w-[1600px] items-center gap-5 px-4 py-3 lg:px-6">
        <div className="flex min-w-max items-center gap-2"><div className="grid h-7 w-7 place-items-center border border-cyan/50 text-cyan"><span className="mono text-xs font-bold">4S</span></div><div><p className="mono text-xs font-semibold tracking-[0.18em]">PULSEREADY <span className="text-cyan">4S</span></p><p className="hidden text-[10px] text-muted sm:block">OPERATIONS COMMAND CENTER</p></div></div>
        <nav aria-label="Primary navigation" className="flex flex-1 gap-1 overflow-x-auto">{links.map(({ to, label, icon: Icon }, index) => <NavLink key={to} to={to} end={to === '/'} className={({ isActive }) => `flex min-w-max items-center gap-2 border px-3 py-2 mono text-[10px] uppercase tracking-wider ${isActive ? 'border-cyan/60 bg-cyan/10 text-cyan' : 'border-transparent text-muted hover:border-line hover:bg-raised hover:text-slate-100'}`}><span className="text-[9px] text-muted">0{index + 1}</span><Icon size={14} aria-hidden="true" />{label}</NavLink>)}</nav>
        <div className="hidden items-center gap-2 border-l border-line pl-4 text-right sm:flex"><Wifi size={13} className={connected ? 'text-teal' : 'text-amber'} aria-hidden="true" /><div><p className={`mono text-[10px] uppercase ${connected ? 'text-teal' : 'text-amber'}`}>{connected ? 'Service online' : health.isLoading ? 'Checking service' : 'Service offline'}</p><p className="max-w-40 truncate text-[10px] text-muted" title={health.isError ? safeErrorMessage(health.error) : apiBaseUrl()}>{apiBaseUrl()}</p></div></div>
      </div>
    </header>
    <main className="mx-auto max-w-[1600px] px-4 py-5 lg:px-6"><Outlet /></main>
    <footer className="mx-auto max-w-[1600px] px-4 pb-5 lg:px-6"><p className="mono text-[10px] uppercase tracking-wider text-muted">Synthetic demo data · Backend remains authoritative · No clinical decision automation</p></footer>
  </div>
}
