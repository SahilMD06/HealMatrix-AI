import { describe, expect, it, vi, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'

import { renderPage } from '@/test/testUtils'
import InventoryDashboard from './InventoryDashboard'
import api, { checkApiHealth } from '@/services/api'

// Mocks the whole services/api module: `default` covers this page's own
// useApi('/analytics/medicine') call, `checkApiHealth` covers the Header
// (rendered by PageContainer) polling readiness independently via raw axios.
vi.mock('@/services/api', () => ({
  default: { get: vi.fn() },
  checkApiHealth: vi.fn(),
}))

describe('InventoryDashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    checkApiHealth.mockResolvedValue({ status: 'ready' })
  })

  it('renders headline KPIs from /analytics/medicine', async () => {
    api.get.mockResolvedValueOnce({
      data: {
        expiring_count: 3,
        expiring: [],
        low_stock_count: 2,
        low_stock: [],
        value_at_risk_paise: 500000,
      },
    })

    renderPage(<InventoryDashboard />)

    // StatCard mounts at value=0 before the fetch resolves, then eases to the
    // real value over ~700ms (useAnimatedCounter) once data arrives — that's a
    // genuine animation, not test flakiness, so give waitFor enough headroom
    // to observe it land rather than tightening the race against the default
    // 1000ms timeout.
    await waitFor(() => expect(screen.getByText('3')).toBeInTheDocument(), { timeout: 2000 })
    expect(screen.getByText('2')).toBeInTheDocument()
    expect(api.get).toHaveBeenCalledWith('/analytics/medicine', { params: undefined })
  })

  it('shows empty states when nothing is at risk', async () => {
    api.get.mockResolvedValueOnce({
      data: { expiring_count: 0, expiring: [], low_stock_count: 0, low_stock: [], value_at_risk_paise: 0 },
    })

    renderPage(<InventoryDashboard />)

    await waitFor(() => expect(screen.getByText('Nothing expiring soon')).toBeInTheDocument())
    expect(screen.getByText('Stock levels look healthy')).toBeInTheDocument()
  })

  it('flags a critical SKU in the low-stock list', async () => {
    api.get.mockResolvedValueOnce({
      data: {
        expiring_count: 0, expiring: [], value_at_risk_paise: 0,
        low_stock_count: 1,
        low_stock: [
          { id: '1', sku: 'MED-1', medicine_name: 'Insulin', quantity: 2, reorder_point: 10, is_critical: true },
        ],
      },
    })

    renderPage(<InventoryDashboard />)

    await waitFor(() => expect(screen.getByText('Insulin')).toBeInTheDocument())
    expect(screen.getByText('critical')).toBeInTheDocument()
  })

  it('surfaces an error state and offers a retry', async () => {
    api.get.mockRejectedValueOnce({ code: 'network_error', message: 'The request could not be completed.' })

    renderPage(<InventoryDashboard />)

    await waitFor(() => expect(screen.getByText('Something went wrong')).toBeInTheDocument())
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument()
  })
})
