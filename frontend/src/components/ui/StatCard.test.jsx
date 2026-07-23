import { Activity } from 'lucide-react'
import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'

import { StatCard } from './StatCard'

describe('StatCard', () => {
  it('renders the label and icon', () => {
    render(<StatCard icon={Activity} label="Active census" value={42} animate={false} />)
    expect(screen.getByText('Active census')).toBeInTheDocument()
  })

  it('renders a non-animated numeric value verbatim', () => {
    render(<StatCard label="Active census" value={42} animate={false} />)
    expect(screen.getByText('42')).toBeInTheDocument()
  })

  it('renders a unit suffix alongside the value', () => {
    render(<StatCard label="Occupancy" value={87.5} unit="%" animate={false} />)
    expect(screen.getByText('87.5')).toBeInTheDocument()
    expect(screen.getByText('%')).toBeInTheDocument()
  })

  it('falls back to an em dash for a non-numeric value', () => {
    render(<StatCard label="Grade" value={null} animate={false} />)
    expect(screen.getByText('—')).toBeInTheDocument()
  })

  it('shows a positive trend with an up arrow and its label', () => {
    render(<StatCard label="ICU occupancy" value={92} animate={false} trend={2} trendLabel="over threshold" />)
    expect(screen.getByText(/▲/)).toBeInTheDocument()
    expect(screen.getByText(/over threshold/)).toBeInTheDocument()
  })

  it('shows a negative trend with a down arrow', () => {
    render(<StatCard label="Emissions" value={10} animate={false} trend={-5} />)
    expect(screen.getByText(/▼/)).toBeInTheDocument()
  })

  it('omits the trend line entirely when no trend is given', () => {
    render(<StatCard label="Beds" value={10} animate={false} />)
    expect(screen.queryByText(/▲|▼|•/)).not.toBeInTheDocument()
  })
})
