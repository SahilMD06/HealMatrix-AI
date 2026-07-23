import { formatNumber } from '@/lib/utils'
import { TriageBadge } from '@/components/ui/TriageBadge'
import { EmptyState, ErrorState, Skeleton } from '@/components/ui/States'
import { Stethoscope } from 'lucide-react'

/**
 * Live triage queue, ordered by acuity then wait time (the API already sorts it).
 * A row past its target response window pulses to draw attention.
 */
export function TriageQueue({ data, loading, error, onRetry, onSelect }) {
  if (loading && !data) {
    return (
      <div className="space-y-2">
        {[...Array(4)].map((_, i) => (
          <Skeleton key={i} className="h-14 w-full" />
        ))}
      </div>
    )
  }
  if (error) return <ErrorState error={error} onRetry={onRetry} />
  if (!data?.length) {
    return (
      <EmptyState
        icon={Stethoscope}
        title="Queue is clear"
        description="No patients are currently awaiting review."
      />
    )
  }

  return (
    <div className="space-y-2">
      {data.map((entry) => {
        const esi = entry.triage?.esi_level
        const target = entry.triage?.target_response_minutes ?? 999
        const overdue = entry.waiting_minutes != null && entry.waiting_minutes > target
        return (
          <button
            key={entry.id}
            onClick={() => onSelect?.(entry)}
            className="focus-ring flex w-full items-center gap-3 rounded-md border border-border bg-card px-3 py-2.5 text-left transition-colors hover:bg-secondary"
          >
            <TriageBadge level={esi} showLabel={false} />
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium">
                {entry.patient_name || 'Unknown'}{' '}
                <span className="text-muted-foreground">· {entry.patient_age ?? '—'}y</span>
              </p>
              <p className="truncate text-xs text-muted-foreground">{entry.chief_complaint}</p>
            </div>
            <div className="text-right">
              <p className="font-mono text-xs font-medium">{entry.department_id ? '' : ''}</p>
              <p className={overdue ? 'text-xs font-semibold text-destructive' : 'text-xs text-muted-foreground'}>
                {formatNumber(entry.waiting_minutes)} min
              </p>
            </div>
          </button>
        )
      })}
    </div>
  )
}
