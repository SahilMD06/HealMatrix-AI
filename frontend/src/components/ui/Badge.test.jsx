import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'

import { Badge } from './Badge'

describe('Badge', () => {
  it('renders its children', () => {
    render(<Badge>Active</Badge>)
    expect(screen.getByText('Active')).toBeInTheDocument()
  })

  it('defaults to the neutral variant', () => {
    render(<Badge>Plain</Badge>)
    expect(screen.getByText('Plain')).toHaveClass('bg-secondary', 'text-secondary-foreground')
  })

  it('applies the danger variant for critical states', () => {
    render(<Badge variant="danger">Critical</Badge>)
    expect(screen.getByText('Critical')).toHaveClass('text-triage-1')
  })

  it('applies the success variant', () => {
    render(<Badge variant="success">Healthy</Badge>)
    expect(screen.getByText('Healthy')).toHaveClass('text-brand-emerald')
  })

  it('merges a caller-supplied className rather than replacing the base styles', () => {
    render(<Badge className="ml-2">Tagged</Badge>)
    const badge = screen.getByText('Tagged')
    expect(badge).toHaveClass('ml-2')
    expect(badge).toHaveClass('rounded-full') // base style survives the merge
  })
})
