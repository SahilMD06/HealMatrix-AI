import * as TabsPrimitive from '@radix-ui/react-tabs'

import { cn } from '@/lib/utils'

/** Thin styled wrapper around Radix Tabs so every tabbed page shares one look. */
export const Tabs = TabsPrimitive.Root

export function TabsList({ className, ...props }) {
  return (
    <TabsPrimitive.List
      className={cn(
        'inline-flex items-center gap-1 rounded-lg border border-border bg-card p-1',
        className
      )}
      {...props}
    />
  )
}

export function TabsTrigger({ className, ...props }) {
  return (
    <TabsPrimitive.Trigger
      className={cn(
        'focus-ring relative rounded-md px-3.5 py-1.5 text-sm font-medium text-muted-foreground transition-all',
        'data-[state=active]:bg-brand-gradient data-[state=active]:text-white data-[state=active]:shadow-glow',
        'hover:text-foreground data-[state=active]:hover:text-white',
        className
      )}
      {...props}
    />
  )
}

export function TabsContent({ className, ...props }) {
  return (
    <TabsPrimitive.Content
      className={cn('mt-6 focus-visible:outline-none', className)}
      {...props}
    />
  )
}
