import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it } from 'vitest'
import { clearWorkflowForTests } from './workflow/WorkflowContext'
import App from './App'

describe('App routing', () => {
  beforeEach(() => clearWorkflowForTests())
  it.each([
    ['/planning', '/planning'], ['/work-items', '/work-items'], ['/employees', '/employees'],
    ['/scenarios', '/scenarios'], ['/plan', '/plan'], ['/cash-flow', '/cash-flow'],
    ['/comparison', '/comparison'], ['/explanations', '/explanations'],
  ])('renders the %s workspace route', (path, href) => {
    render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>)
    expect(screen.getByRole('img', { name: 'NexaWorks Decision Support' })).toBeInTheDocument()
    expect(document.querySelector(`a[href="${href}"]`)).toBeInTheDocument()
  })

  it('redirects unknown routes to the dashboard route', async () => {
    render(<MemoryRouter initialEntries={['/does-not-exist']}><App /></MemoryRouter>)
    expect(await screen.findByRole('heading', { name: 'Build your operating plan' })).toBeInTheDocument()
  })
})
