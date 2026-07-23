import { useCallback, useEffect, useState } from 'react'

import { checkApiHealth } from '@/services/api'

/**
 * Polls the backend readiness probe.
 * Returns the standard {data, error, loading, refetch} shape used by every hook
 * in this codebase so components handle async state consistently.
 */
export function useApiHealth({ pollMs = 0 } = {}) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  const refetch = useCallback(async () => {
    setLoading(true)
    try {
      const result = await checkApiHealth()
      setData(result)
      setError(null)
    } catch (err) {
      setData(null)
      setError(err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    const run = async () => {
      if (!cancelled) await refetch()
    }
    run()

    if (!pollMs) return () => { cancelled = true }

    const id = setInterval(run, pollMs)
    return () => {
      cancelled = true
      clearInterval(id)
    }
  }, [refetch, pollMs])

  return { data, error, loading, refetch }
}
