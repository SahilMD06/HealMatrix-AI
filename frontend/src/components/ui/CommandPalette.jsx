import { useEffect, useMemo, useState } from 'react'
import { createPortal } from 'react-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { useLocation, useNavigate } from 'react-router-dom'
import { CornerDownLeft, Search } from 'lucide-react'

import { cn } from '@/lib/utils'

/**
 * ⌘K / Ctrl-K command palette. Built with a portal + framer-motion, no extra
 * dependency. Actions are supplied by the shell and filtered as you type.
 */
export function CommandPalette({ open, onOpenChange, actions }) {
  const navigate = useNavigate()
  const location = useLocation()
  const [query, setQuery] = useState('')
  const [active, setActive] = useState(0)

  // Safety net: whatever triggered the navigation (a palette click, browser
  // back/forward, anything), once the route has actually changed the palette
  // has done its job and must not still be sitting on top of the new page.
  // This does not depend on `run()`'s own onOpenChange(false) call succeeding.
  useEffect(() => {
    onOpenChange(false)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname])

  const results = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return actions
    return actions.filter(
      (a) =>
        a.label.toLowerCase().includes(q) ||
        a.group?.toLowerCase().includes(q) ||
        a.keywords?.some((k) => k.includes(q))
    )
  }, [query, actions])

  useEffect(() => {
    setActive(0)
  }, [query, open])

  useEffect(() => {
    if (!open) setQuery('')
  }, [open])

  function run(action) {
    if (action.to) navigate(action.to)
    action.onSelect?.()
    // Deferred rather than called first: react-router's navigate() and this
    // close both update state in the same tick, and batching them together
    // was the actual bug — after 2-3 rapid open/select cycles the palette's
    // own `open` update was getting dropped while framer-motion's
    // AnimatePresence was still unwinding the previous exit animation.
    // Pushing the close into its own macrotask lets that settle first.
    setTimeout(() => onOpenChange(false), 0)
  }

  function onKeyDown(e) {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActive((i) => Math.min(i + 1, results.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActive((i) => Math.max(i - 1, 0))
    } else if (e.key === 'Enter' && results[active]) {
      e.preventDefault()
      run(results[active])
    }
  }

  return createPortal(
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-50 flex items-start justify-center p-4 pt-[12vh]"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        >
          <div
            className="absolute inset-0 bg-background/70 backdrop-blur-sm"
            onClick={() => onOpenChange(false)}
          />
          <motion.div
            initial={{ opacity: 0, scale: 0.97, y: -8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.97, y: -8 }}
            transition={{ duration: 0.16 }}
            className="glass relative w-full max-w-lg overflow-hidden rounded-xl shadow-elevated"
            onKeyDown={onKeyDown}
          >
            <div className="flex items-center gap-2 border-b border-border px-4">
              <Search className="h-4 w-4 text-muted-foreground" />
              <input
                autoFocus
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search dashboards, agents, actions…"
                className="h-12 flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
              />
              <kbd className="rounded border border-border px-1.5 py-0.5 text-[10px] text-muted-foreground">
                ESC
              </kbd>
            </div>
            <div className="max-h-80 overflow-y-auto scrollbar-slim p-2">
              {results.length === 0 ? (
                <p className="px-3 py-6 text-center text-sm text-muted-foreground">No results</p>
              ) : (
                results.map((action, i) => (
                  <button
                    key={action.label}
                    onMouseEnter={() => setActive(i)}
                    onClick={() => run(action)}
                    className={cn(
                      'flex w-full items-center gap-3 rounded-md px-3 py-2 text-left text-sm transition-colors',
                      i === active ? 'bg-primary/10 text-primary' : 'text-foreground hover:bg-secondary'
                    )}
                  >
                    {action.icon && <action.icon className="h-4 w-4 shrink-0" />}
                    <span className="flex-1">{action.label}</span>
                    {action.group && (
                      <span className="text-xs text-muted-foreground">{action.group}</span>
                    )}
                    {i === active && <CornerDownLeft className="h-3.5 w-3.5 text-muted-foreground" />}
                  </button>
                ))
              )}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body
  )
}

/** Registers the ⌘K / Ctrl-K shortcut and Escape-to-close. */
export function useCommandPalette() {
  const [open, setOpen] = useState(false)
  useEffect(() => {
    function onKey(e) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setOpen((v) => !v)
      } else if (e.key === 'Escape') {
        setOpen(false)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])
  return { open, setOpen }
}
