import { cn } from '@/lib/utils'

/**
 * Surface primitive. Three looks share one component:
 *  - premium (default): solid card with top sheen, lifts + glows on hover
 *  - glass: translucent blurred panel for overlays
 *  - plain: static bordered card
 */
export function Card({ className, variant = 'premium', ...props }) {
  const base =
    variant === 'glass'
      ? 'glass rounded-lg text-card-foreground'
      : variant === 'plain'
        ? 'rounded-lg border border-border bg-card text-card-foreground'
        : 'premium-card text-card-foreground'
  return <div className={cn(base, className)} {...props} />
}

export function CardHeader({ className, ...props }) {
  return <div className={cn('flex flex-col gap-1 p-5 pb-3', className)} {...props} />
}

export function CardTitle({ className, ...props }) {
  return (
    <h3 className={cn('text-sm font-semibold leading-none tracking-tight', className)} {...props} />
  )
}

export function CardDescription({ className, ...props }) {
  return <p className={cn('text-sm text-muted-foreground', className)} {...props} />
}

export function CardContent({ className, ...props }) {
  return <div className={cn('p-5 pt-0', className)} {...props} />
}
