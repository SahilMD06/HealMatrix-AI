import { describe, expect, it, vi, beforeEach } from 'vitest'
import { renderHook, waitFor, act } from '@testing-library/react'

import { useApi } from './useApi'
import api from '@/services/api'

vi.mock('@/services/api', () => ({
  default: { get: vi.fn() },
}))

describe('useApi', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('starts loading and resolves with data on success', async () => {
    api.get.mockResolvedValueOnce({ data: { census: 12 } })

    const { result } = renderHook(() => useApi('/analytics/overview'))
    expect(result.current.loading).toBe(true)

    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.data).toEqual({ census: 12 })
    expect(result.current.error).toBeNull()
    expect(api.get).toHaveBeenCalledWith('/analytics/overview', { params: undefined })
  })

  it('surfaces the normalised error shape and clears loading', async () => {
    const error = { code: 'network_error', message: 'boom', status: 0 }
    api.get.mockRejectedValueOnce(error)

    const { result } = renderHook(() => useApi('/analytics/overview'))
    await waitFor(() => expect(result.current.loading).toBe(false))

    expect(result.current.error).toEqual(error)
    expect(result.current.data).toBeNull()
  })

  it('does not fetch at all when enabled is false', () => {
    const { result } = renderHook(() => useApi('/analytics/overview', { enabled: false }))
    expect(result.current.loading).toBe(false)
    expect(api.get).not.toHaveBeenCalled()
  })

  it('passes query params through to the request', async () => {
    api.get.mockResolvedValueOnce({ data: [] })
    renderHook(() => useApi('/analytics/patients', { params: { days: 7 } }))

    await waitFor(() =>
      expect(api.get).toHaveBeenCalledWith('/analytics/patients', { params: { days: 7 } })
    )
  })

  it('refetch triggers another request', async () => {
    api.get.mockResolvedValue({ data: { a: 1 } })
    const { result } = renderHook(() => useApi('/x'))

    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(api.get).toHaveBeenCalledTimes(1)

    await act(async () => {
      await result.current.refetch()
    })
    expect(api.get).toHaveBeenCalledTimes(2)
  })
})
