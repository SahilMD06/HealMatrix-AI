import { clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

/**
 * Merge conditional class names, resolving Tailwind conflicts.
 * Used by every UI primitive so consumers can override styles predictably.
 */
export function cn(...inputs) {
  return twMerge(clsx(inputs))
}

/** Format a number as Indian-style compact currency from paise. */
export function formatCurrency(paise, { compact = true } = {}) {
  const rupees = (paise ?? 0) / 100
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    notation: compact ? 'compact' : 'standard',
    maximumFractionDigits: compact ? 1 : 2,
  }).format(rupees)
}

/** Format a raw number with locale separators and optional unit suffix. */
export function formatNumber(value, { unit = '', decimals = 0 } = {}) {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  const formatted = new Intl.NumberFormat('en-IN', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value)
  return unit ? `${formatted} ${unit}` : formatted
}

/** Percentage helper that guards against divide-by-zero. */
export function percentage(part, whole, decimals = 1) {
  if (!whole) return 0
  return Number(((part / whole) * 100).toFixed(decimals))
}

/** Map an ESI triage level to its palette token and label. */
export const TRIAGE_META = {
  1: { label: 'Resuscitation', className: 'bg-triage-1', targetMinutes: 0 },
  2: { label: 'Emergent', className: 'bg-triage-2', targetMinutes: 10 },
  3: { label: 'Urgent', className: 'bg-triage-3', targetMinutes: 30 },
  4: { label: 'Less Urgent', className: 'bg-triage-4', targetMinutes: 60 },
  5: { label: 'Non-Urgent', className: 'bg-triage-5', targetMinutes: 120 },
}

/** Map a 0-100 sustainability score to a grade and palette token. */
export function sustainabilityGrade(score) {
  if (score >= 85) return { grade: 'A+', className: 'text-sustain-excellent' }
  if (score >= 75) return { grade: 'A', className: 'text-sustain-excellent' }
  if (score >= 65) return { grade: 'B', className: 'text-sustain-good' }
  if (score >= 55) return { grade: 'C', className: 'text-sustain-fair' }
  if (score >= 45) return { grade: 'D', className: 'text-sustain-fair' }
  return { grade: 'E', className: 'text-sustain-poor' }
}

/** Debounce helper for search inputs and map interactions. */
export function debounce(fn, delay = 300) {
  let timer
  return (...args) => {
    clearTimeout(timer)
    timer = setTimeout(() => fn(...args), delay)
  }
}
