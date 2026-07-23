import { cn } from '@/lib/utils'
import { TRIAGE_META } from '@/lib/utils'

/**
 * Acuity chip. Status is never colour-only: the ESI numeral and label are always
 * present, which is both an accessibility requirement and a clinical safety one.
 */
export function TriageBadge({ level, showLabel = true, className }) {
  const meta = TRIAGE_META[level] || { label: 'Unknown', className: 'bg-muted' }
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-xs font-semibold text-white',
        meta.className,
        className
      )}
    >
      <span className="tabular-nums">ESI {level}</span>
      {showLabel && <span className="font-normal opacity-90">· {meta.label}</span>}
    </span>
  )
}
