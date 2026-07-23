import { useEffect, useRef, useState } from 'react'

/**
 * Eases a number from its previous value to the target when it changes, giving
 * KPI tiles a "live counter" feel. Respects prefers-reduced-motion by snapping.
 */
export function useAnimatedCounter(target, { duration = 700, decimals = 0 } = {}) {
  const [value, setValue] = useState(target ?? 0)
  const fromRef = useRef(target ?? 0)
  const frameRef = useRef()

  useEffect(() => {
    const to = Number(target) || 0
    const from = fromRef.current
    const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

    if (reduce || from === to) {
      setValue(to)
      fromRef.current = to
      return undefined
    }

    const start = performance.now()
    const tick = (now) => {
      const progress = Math.min((now - start) / duration, 1)
      // easeOutCubic
      const eased = 1 - Math.pow(1 - progress, 3)
      const current = from + (to - from) * eased
      setValue(current)
      if (progress < 1) {
        frameRef.current = requestAnimationFrame(tick)
      } else {
        fromRef.current = to
      }
    }
    frameRef.current = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frameRef.current)
  }, [target, duration])

  const display = Number(value).toLocaleString('en-IN', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })
  return display
}
