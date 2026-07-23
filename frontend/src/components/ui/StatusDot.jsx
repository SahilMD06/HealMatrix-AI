import { cn } from '@/lib/utils'

const TONES = {
  online: 'bg-brand-emerald',
  warning: 'bg-amber-400',
  offline: 'bg-triage-1',
  idle: 'bg-muted-foreground',
}

/** Pulsing status indicator. The halo animation reads as "live". */
export function StatusDot({ tone = 'online', pulse = true, className }) {
  return (
    <span className={cn('relative inline-flex', className)}>
      <span className={cn('h-2 w-2 rounded-full', TONES[tone] || TONES.idle)} />
      {pulse && (
        <span
          className={cn('absolute inset-0 rounded-full opacity-70', TONES[tone] || TONES.idle)}
          style={{ animation: 'pulse-ring 1.8s cubic-bezier(0.24,0,0.38,1) infinite' }}
        />
      )}
    </span>
  )
}
