import { AlertTriangle, AudioLines, CheckCircle2, CircleSlash2, Network, RefreshCw, ShieldCheck, Sparkles } from 'lucide-react'
import { useEffect, useState } from 'react'
import { ErrorState, EmptyState, LoadingState } from '../../components/feedback/States'
import { Badge, Eyebrow, Panel, Unavailable } from '../../components/layout/CommandCenter'
import { useBriefingAudio, useIntegrationStatuses, useOverview, useSummaryReview } from '../../hooks/useApiQueries'
import type { IntegrationStatus, IntegrationStatusOut } from '../../lib/api/contracts'
import { safeErrorMessage } from '../../lib/api/errors'

function statusTone(status: IntegrationStatus): 'healthy' | 'warning' | 'critical' | 'neutral' {
  if (status === 'live_ready' || status === 'live_verified') return 'healthy'
  if (status === 'mock_active') return 'warning'
  if (status === 'unsupported_contract') return 'neutral'
  if (status === 'missing_credential' || status === 'configuration_error') return 'warning'
  return 'critical'
}

function statusLabel(status: IntegrationStatus) {
  return status.replaceAll('_', ' ')
}

function IntegrationStatusCard({ item }: { item: IntegrationStatusOut }) {
  return <article className="border border-line bg-panel p-4">
    <div className="flex items-start justify-between gap-3"><div className="flex items-center gap-2"><Network size={15} className="text-cyan" aria-hidden="true" /><h2 className="font-semibold text-slate-100">{item.capability.replaceAll('_', ' ')}</h2></div><Badge tone={statusTone(item.status)}>{statusLabel(item.status)}</Badge></div>
    <p className="mt-3 text-xs leading-5 text-muted">{item.message}</p><dl className="mt-4 grid grid-cols-2 gap-3 border-t border-line pt-3 text-xs"><div><dt className="text-muted">Enabled</dt><dd className="mt-1 mono uppercase text-slate-100">{item.enabled ? 'yes' : 'no'}</dd></div><div><dt className="text-muted">Contract</dt><dd className="mt-1 mono uppercase text-slate-100">{item.contract_verified ? 'verified' : 'not verified'}</dd></div><div><dt className="text-muted">Credential</dt><dd className="mt-1 mono uppercase text-slate-100">{item.credential_configured ? 'present' : 'missing'}</dd></div><div><dt className="text-muted">Endpoint</dt><dd className="mt-1 mono uppercase text-slate-100">{item.endpoint_configured ? 'present' : 'missing'}</dd></div></dl>
  </article>
}

function AudioResult({ audio }: { audio: Blob }) {
  const [url, setUrl] = useState<string>()
  useEffect(() => { const next = URL.createObjectURL(audio); setUrl(next); return () => URL.revokeObjectURL(next) }, [audio])
  return url ? <audio className="w-full" controls src={url} aria-label="Synthetic local briefing audio" /> : null
}

function BriefingPanel() {
  const overview = useOverview()
  const summary = useSummaryReview()
  const audio = useBriefingAudio()
  const alerts = overview.data?.active_alerts ?? []
  const [selectedId, setSelectedId] = useState('')
  const selected = alerts.find((alert) => alert.id === selectedId) ?? alerts[0]
  const alertId = selected?.id ?? ''
  return <Panel className="p-4"><div className="flex flex-wrap items-start justify-between gap-3 border-b border-line pb-3"><div><Eyebrow>BRIEFING WORKFLOWS</Eyebrow><h2 className="mt-1 font-semibold text-slate-100">Human-supervised briefing rehearsal</h2></div><Badge tone="warning">MOCK-SAFE</Badge></div>{overview.isLoading && <LoadingState label="Loading authorized alert context…" />}{overview.isError && <ErrorState error={overview.error} retry={() => void overview.refetch()} />}{overview.data && alerts.length === 0 && <EmptyState title="No active alerts" detail="Summary review requires an alert returned by the authenticated overview contract." />}{selected && <div className="space-y-4 pt-4"><label className="block text-xs text-muted">Authorized alert<select aria-label="Briefing alert" className="mt-1 w-full border border-line bg-raised px-3 py-2 text-sm text-slate-100" value={alertId} onChange={(event) => setSelectedId(event.target.value)}>{alerts.map((alert) => <option key={alert.id} value={alert.id}>{alert.title} · {alert.id.slice(0, 8)}</option>)}</select></label><div className="border border-line bg-raised p-3"><p className="font-medium text-slate-100">{selected.title}</p><p className="mt-1 text-sm leading-5 text-muted">{selected.explanation}</p><p className="mt-2 mono text-[10px] uppercase text-muted">Server state: {selected.status} · {selected.facility_code}</p></div><div className="flex flex-wrap gap-2"><button type="button" className="inline-flex items-center gap-2 border border-cyan/50 bg-cyan/10 px-3 py-2 mono text-[10px] uppercase tracking-wider text-cyan disabled:cursor-not-allowed disabled:opacity-40" disabled={summary.isPending} onClick={() => summary.mutate(alertId)}><Sparkles size={14} aria-hidden="true" />{summary.isPending ? 'Reviewing…' : 'Run mock summary review'}</button><button type="button" className="inline-flex items-center gap-2 border border-line bg-raised px-3 py-2 mono text-[10px] uppercase tracking-wider text-slate-100 disabled:cursor-not-allowed disabled:opacity-40" disabled={audio.isPending} onClick={() => audio.mutate(alertId)}><AudioLines size={14} aria-hidden="true" />{audio.isPending ? 'Preparing…' : 'Request approved audio'}</button></div>{summary.isError && <p className="text-sm text-danger" role="alert">{safeErrorMessage(summary.error)}</p>}{summary.data && <div className="border border-amber/40 bg-amber/10 p-3 text-sm"><p className="flex items-center gap-2 font-medium text-amber"><AlertTriangle size={15} aria-hidden="true" />Simulated result — not an Adaption approval</p><p className="mt-1 text-muted">Review status: <span className="mono text-slate-100">{summary.data.review_status}</span>; approved: <span className="mono text-slate-100">{String(summary.data.approved)}</span></p><ul className="mt-2 list-disc pl-5 text-xs text-muted">{summary.data.issues.map((issue) => <li key={issue}>{issue}</li>)}</ul></div>}{audio.isError && <p className="text-sm text-danger" role="alert">{safeErrorMessage(audio.error)}</p>}{audio.data && <div className="space-y-2 border border-line bg-raised p-3"><p className="flex items-center gap-2 text-xs text-teal"><CheckCircle2 size={15} aria-hidden="true" />Local mock audio returned by the backend</p><AudioResult audio={audio.data} /></div>}<p className="border-t border-line pt-3 text-xs leading-5 text-muted">Audio requires a persisted acknowledged review. The current overview route returns open alerts only, so an approved alert may need to be selected after completing review in Audit Ledger.</p></div>}</Panel>
}

export function IntegrationsPage() {
  const query = useIntegrationStatuses()
  return <div className="space-y-5"><div className="flex flex-wrap items-end justify-between gap-3"><div><Eyebrow>05 · EXTERNAL BOUNDARY</Eyebrow><h1 className="mt-1 text-2xl font-semibold tracking-tight text-slate-100 sm:text-3xl">AI Ecosystem &amp; Integrations</h1><p className="mt-2 max-w-3xl text-sm leading-6 text-muted">Server-reported capability status for the eight configured integration slots. Credentials stay server-side; this page never calls a provider directly.</p></div><Badge tone="warning">NO LIVE SPEND</Badge></div><Panel className="flex items-start gap-3 p-4"><ShieldCheck size={18} className="mt-0.5 text-teal" aria-hidden="true" /><div><p className="font-medium text-slate-100">Credit-safe rehearsal mode</p><p className="mt-1 text-sm text-muted">Mock status means outbound provider calls are blocked. A credential being present does not make a capability live.</p></div></Panel>{query.isLoading && <LoadingState label="Loading server integration diagnostics…" />}{query.isError && <ErrorState error={query.error} retry={() => void query.refetch()} />}{query.data && (query.data.length ? <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{query.data.map((item) => <IntegrationStatusCard item={item} key={item.capability} />)}</div> : <EmptyState title="No integration diagnostics returned" detail="The backend returned an empty capability status set." />)}<BriefingPanel /><p className="flex items-start gap-2 border-t border-line pt-3 text-xs leading-5 text-muted"><CircleSlash2 size={14} className="mt-0.5 shrink-0" aria-hidden="true" />Unsupported provider contracts remain visibly unavailable. This page does not claim live Agent37, Render, Nodus, ElevenLabs or FlutterFlow execution.</p><div className="flex items-center gap-2 text-xs text-muted"><RefreshCw size={13} aria-hidden="true" />Status refreshes on demand and is not an automatic credit-consuming action.</div></div>
}
