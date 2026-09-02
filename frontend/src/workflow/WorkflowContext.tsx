import { createContext, useCallback, useContext, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { planningApi } from './api'
import type { WorkflowSnapshot } from './types'

const STORAGE_KEY = 'nexaworks.active-planning-workflow.v1'
const emptySnapshot: WorkflowSnapshot = {
  status: 'NO_DATA',
  source: null,
  catalog: null,
  dataset: null,
  analysis: null,
  generation: null,
  generatedAt: null,
}

function restore(): WorkflowSnapshot {
  try {
    const value = sessionStorage.getItem(STORAGE_KEY)
    return value ? { ...emptySnapshot, ...JSON.parse(value) } : emptySnapshot
  } catch {
    return emptySnapshot
  }
}

interface WorkflowContextValue extends WorkflowSnapshot {
  busy: boolean
  error: string | null
  loadSample: () => Promise<void>
  loadDataset: (dataset: Record<string, unknown>) => Promise<void>
  analyze: () => Promise<void>
  generate: () => Promise<void>
  reset: () => void
}

const WorkflowContext = createContext<WorkflowContextValue | null>(null)

export function WorkflowProvider({ children }: { children: ReactNode }) {
  const [snapshot, setSnapshot] = useState<WorkflowSnapshot>(restore)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const commit = useCallback((next: WorkflowSnapshot) => {
    setSnapshot(next)
    try { sessionStorage.setItem(STORAGE_KEY, JSON.stringify(next)) } catch { /* memory state remains usable */ }
  }, [])

  const perform = useCallback(async (action: () => Promise<void>) => {
    setBusy(true)
    setError(null)
    try { await action() } catch (value) {
      setError(value instanceof Error ? value.message : 'PLANNING_WORKFLOW_FAILED')
      throw value
    } finally { setBusy(false) }
  }, [])

  const loadSample = useCallback(() => perform(async () => {
    const catalog = await planningApi.sample()
    commit({ ...emptySnapshot, status: 'DATA_LOADED', source: 'sample', catalog })
  }), [commit, perform])

  const loadDataset = useCallback((dataset: Record<string, unknown>) => perform(async () => {
    const catalog = await planningApi.review(dataset)
    commit({ ...emptySnapshot, status: 'DATA_LOADED', source: 'uploaded', catalog, dataset })
  }), [commit, perform])

  const analyze = useCallback(() => perform(async () => {
    if (!snapshot.catalog) throw new Error('PLANNING_DATA_REQUIRED')
    const analysis = await planningApi.analyze(snapshot.dataset)
    commit({ ...snapshot, status: 'ANALYZED', analysis, generation: null, generatedAt: null })
  }), [commit, perform, snapshot])

  const generate = useCallback(() => perform(async () => {
    if (!snapshot.catalog || !snapshot.analysis) throw new Error('PORTFOLIO_ANALYSIS_REQUIRED')
    const generation = await planningApi.generate(snapshot.dataset)
    commit({
      ...snapshot,
      status: 'PLAN_GENERATED',
      analysis: {
        feasibility: generation.feasibility,
        portfolio: generation.portfolio,
        commercial: generation.commercial,
        scoring: generation.scoring,
      },
      generation,
      generatedAt: new Date().toISOString(),
    })
  }), [commit, perform, snapshot])

  const reset = useCallback(() => {
    sessionStorage.removeItem(STORAGE_KEY)
    setError(null)
    setSnapshot(emptySnapshot)
  }, [])

  const value = useMemo(() => ({
    ...snapshot, busy, error, loadSample, loadDataset, analyze, generate, reset,
  }), [snapshot, busy, error, loadSample, loadDataset, analyze, generate, reset])
  return <WorkflowContext.Provider value={value}>{children}</WorkflowContext.Provider>
}

export function useWorkflow(): WorkflowContextValue {
  const value = useContext(WorkflowContext)
  if (!value) throw new Error('useWorkflow must be used inside WorkflowProvider')
  return value
}

export function seedWorkflowForTests(snapshot: Partial<WorkflowSnapshot>) {
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ ...emptySnapshot, ...snapshot }))
}

export function clearWorkflowForTests() {
  sessionStorage.removeItem(STORAGE_KEY)
}
