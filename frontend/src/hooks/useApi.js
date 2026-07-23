import { useCallback, useEffect, useState } from 'react'

import api from '@/services/api'

/**
 * Data-fetching hook returning the {data, error, loading, refetch} shape used by
 * every page, so async states are handled consistently. Optional polling keeps
 * live views (triage queue, occupancy) fresh.
 */
export function useApi(path, { params, pollMs = 0, enabled = true } = {}) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(enabled)

  const key = JSON.stringify({ path, params })

  const refetch = useCallback(async () => {
    if (!enabled) return
    setLoading(true)
    try {
      const response = await api.get(path, { params })
      setData(response.data)
      setError(null)
    } catch (err) {
      setError(err)
    } finally {
      setLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, enabled])

  useEffect(() => {
    let cancelled = false
    const run = async () => {
      if (!cancelled) await refetch()
    }
    run()

    if (!pollMs || !enabled) return () => { cancelled = true }
    const id = setInterval(run, pollMs)
    return () => {
      cancelled = true
      clearInterval(id)
    }
  }, [refetch, pollMs, enabled])

  return { data, error, loading, refetch }
}
