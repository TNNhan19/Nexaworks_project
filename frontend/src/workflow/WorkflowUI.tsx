import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import type { WorkflowStatus } from './types'
import { workflowCopy } from './copy'

const steps: Array<{ key: 'data' | 'work' | 'analysis' | 'plan'; minimum: WorkflowStatus }> = [
  { key: 'data', minimum: 'DATA_LOADED' },
  { key: 'work', minimum: 'ANALYZED' },
  { key: 'analysis', minimum: 'ANALYZED' },
  { key: 'plan', minimum: 'PLAN_GENERATED' },
]
const rank: Record<WorkflowStatus, number> = { NO_DATA: 0, DATA_LOADED: 1, ANALYZED: 2, PLAN_GENERATED: 3 }

export function WorkflowProgress({ status }: { status: WorkflowStatus }) {
  const { i18n } = useTranslation()
  const c = workflowCopy(i18n.resolvedLanguage).progress
  return <ol className='workflow-progress' aria-label={c.current}>
    {steps.map((step, index) => {
      const complete = rank[status] >= rank[step.minimum]
      const current = status === 'NO_DATA' ? step.key === 'data' : (
        status === 'DATA_LOADED' ? step.key === 'work' :
          status === 'ANALYZED' ? step.key === 'plan' : false
      )
      return <li key={step.key} className={complete ? 'workflow-step workflow-step--complete' : current ? 'workflow-step workflow-step--current' : 'workflow-step'}>
        <span>{complete ? '✓' : index + 1}</span>
        <strong>{c[step.key]}</strong>
        <small>{complete ? c.complete : current ? c.current : c.waiting}</small>
      </li>
    })}
  </ol>
}

export function WorkflowGate({ kind }: { kind: 'data' | 'analysis' | 'plan' | 'sample' }) {
  const { i18n } = useTranslation()
  const c = workflowCopy(i18n.resolvedLanguage).gate
  const values = {
    data: { title: c.noDataTitle, body: c.noDataBody, label: c.goPlanning, to: '/planning' },
    analysis: { title: c.analysisTitle, body: c.analysisBody, label: c.goWork, to: '/work-items' },
    plan: { title: c.planTitle, body: c.planBody, label: c.generatePlan, to: '/work-items' },
    sample: { title: c.sampleOnlyTitle, body: c.sampleOnlyBody, label: c.goPlanning, to: '/planning' },
  }[kind]
  return <section className='workflow-gate'>
    <span aria-hidden='true'>→</span>
    <div><h1>{values.title}</h1><p>{values.body}</p><Link className='button' to={values.to}>{values.label}</Link></div>
  </section>
}
