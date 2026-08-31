import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import App from './App'

describe('App routing', () => {
  it.each([
    ['/scenarios', 'Scenarios'], ['/plan', 'Plan'], ['/cash-flow', 'Cash flow'],
    ['/comparison', 'Comparison'], ['/explanations', 'Explanations'],
  ])('renders the %s workspace route', (path, heading) => {
    render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>)
    expect(screen.getByRole('heading', { level: 1, name: heading })).toBeInTheDocument()
    expect(screen.getByText('NexaWorks')).toBeInTheDocument()
  })

  it('redirects unknown routes to the dashboard route', async () => {
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(new Promise(() => undefined)))
    render(<MemoryRouter initialEntries={['/does-not-exist']}><App /></MemoryRouter>)
    expect(await screen.findByText('Loading baseline data…')).toBeInTheDocument()
  })
})
