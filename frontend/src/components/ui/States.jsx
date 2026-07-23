import { AlertTriangle, Inbox, RefreshCw } from 'lucide-react'

import { cn } from '@/lib/utils'
import { Button } from './Button'

/** Loading skeleton that matches the shape of the content it stands in for. */
export function Skeleton({ className }) {
  return <div className={cn('skeleton h-4 w-full', className)} />
}

export function SkeletonCard() {
  return (
    <div className="glass-card space-y-3">
      <Skeleton className="h-3 w-1/3" />
      <Skeleton className="h-8 w-1/2" />
      <Skeleton className="h-3 w-2/3" />
    </div>
  )
}

/** Empty state: explains the absence and offers the action that resolves it. */
export function EmptyState({ icon: Icon = Inbox, title, description, action }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-12 text-center">
      <div className="rounded-full bg-secondary p-3">
        <Icon className="h-6 w-6 text-muted-foreground" aria-hidden="true" />
      </div>
      <div>
        <p className="font-medium">{title}</p>
        {description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}
      </div>
      {action}
    </div>
  )
}

/** Error state: code, plain-language message, correlation ID, and a retry. */
export function ErrorState({ error, onRetry }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-12 text-center">
      <div className="rounded-full bg-destructive/10 p-3">
        <AlertTriangle className="h-6 w-6 text-destructive" aria-hidden="true" />
      </div>
      <div>
        <p className="font-medium">Something went wrong</p>
        <p className="mt-1 text-sm text-muted-foreground">
          {error?.message || 'The request could not be completed.'}
        </p>
        {error?.correlationId && (
          <p className="mt-1 font-mono text-xs text-muted-foreground/70">
            ref: {error.correlationId}
          </p>
        )}
      </div>
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry}>
          <RefreshCw className="h-3.5 w-3.5" /> Retry
        </Button>
      )}
    </div>
  )
}
