import { AlertTriangle, LoaderCircle, RefreshCw } from 'lucide-react'
import { safeErrorMessage } from '../../lib/api/errors'

export function LoadingState({ label = 'Loading live data…' }: { label?: string }) {
  return <div className="flex items-center gap-3 border border-line bg-panel p-5 text-sm text-muted" role="status"><LoaderCircle className="animate-spin text-cyan" size={18} aria-hidden="true" />{label}</div>
}

export function ErrorState({ error, retry }: { error: unknown; retry?: () => void }) {
  return <div className="border border-danger/40 bg-danger/10 p-5 text-sm text-slate-100" role="alert"><div className="flex items-start gap-3"><AlertTriangle className="text-danger" size={19} aria-hidden="true" /><div className="flex-1"><p className="font-semibold">Unable to load live backend data</p><p className="mt-1 text-muted">{safeErrorMessage(error)}</p>{retry && <button className="mt-3 inline-flex items-center gap-2 border border-danger/40 bg-raised px-3 py-2 font-medium hover:bg-danger/10" onClick={retry}><RefreshCw size={15} aria-hidden="true" />Retry</button>}</div></div></div>
}

export function EmptyState({ title, detail }: { title: string; detail: string }) {
  return <div className="border border-dashed border-line bg-panel p-8 text-center"><p className="font-semibold text-slate-100">{title}</p><p className="mt-1 text-sm text-muted">{detail}</p></div>
}
