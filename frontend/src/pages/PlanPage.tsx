import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { scenarioApi } from '../api/endpoints'
import type { ScenarioRun } from '../api/types'
import { StatusBadge } from '../components/dashboard/StatusBadge'
import { LoadingState } from '../components/system/AsyncState'

function hours(value: number): string {
  return value.toLocaleString(undefined, { maximumFractionDigits: 1 })
}
function Values({ values }: { values: string[] }) {
  return values.length ? <div className='chip-list'>{values.map((value) => <span className='code-chip' key={value}>{value}</span>)}</div> : <span className='muted'>-</span>
}
function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return <section className='plan-section'><div className='exec-section-header'><h2>{title}</h2></div>{children}</section>
}

export function PlanPage() {
  const { t, i18n } = useTranslation()
  const [params] = useSearchParams()
  const runId = params.get('run_id')
  const [run, setRun] = useState<ScenarioRun | null>(null)
  const [loading, setLoading] = useState(Boolean(runId))
  const [error, setError] = useState('')
  const [reloadKey, setReloadKey] = useState(0)
  useEffect(() => {
    if (!runId) { setLoading(false); setRun(null); setError(''); return }
    let current = true
    setLoading(true); setError('')
    void scenarioApi.getRun(runId)
      .then((result) => { if (current) { setRun(result); setLoading(false) } })
      .catch((reason: unknown) => {
        if (current) { setError(reason instanceof Error ? reason.message : 'Unknown error'); setLoading(false) }
      })
    return () => { current = false }
  }, [runId, reloadKey])
  if (!runId) return <div className='content-empty'>
    <h1>{t('plan.title')}</h1><h2>{t('plan.emptyTitle')}</h2><p>{t('plan.emptyText')}</p>
    <Link className='button' to='/scenarios'>{t('plan.openScenarios')}</Link>
  </div>
  if (loading) return <LoadingState />
  if (error) return <div className='async-state async-state--error' role='alert'>
    <div className='error-symbol'>!</div><h2>{t('plan.errorTitle')}</h2><p>{error}</p>
    <button className='button' onClick={() => setReloadKey((value) => value + 1)}>{t('async.retry')}</button>
  </div>
  if (!run || run.status === 'FAILED') return <div className='content-empty'>
    <h1>{t('plan.failedTitle')}</h1><p>{run?.error?.message ?? t('plan.failedText')}</p>
    <Link className='button' to='/scenarios'>{t('plan.openScenarios')}</Link>
  </div>
  const plan = run.plan
  const decision = run.final_decision
  return <div>
    <div className='page-heading'>
      <span className='eyebrow'>{t('plan.eyebrow')}</span><h1>{t('plan.title')}</h1>
      <p>{t('plan.runMetadata', { id: run.run_id, date: new Intl.DateTimeFormat(i18n.resolvedLanguage, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(run.timestamp)) })}</p>
    </div>
    <Section title={t('plan.status')}>
      <div className='exec-grid-4'>
        <div className='status-card'><span className='status-card__label'>{t('plan.status')}</span><span className='decision-label'>{plan.status}</span></div>
        <div className='status-card'><span className='status-card__label'>{t('exec.overallStatus')}</span><StatusBadge status={decision.overall_status} /></div>
        <div className='status-card'><span className='status-card__label'>{t('exec.operationalStatus')}</span><StatusBadge status={decision.operational_status} /></div>
        <div className='status-card'><span className='status-card__label'>{t('exec.financialStatus')}</span><StatusBadge status={decision.financial_status} /></div>
      </div>
      <div className='plan-outcomes'>
        <div><strong>{t('plan.selected')}</strong><Values values={plan.selected_actions} /></div>
        <div><strong>{t('plan.delayed')}</strong><Values values={plan.delayed_actions} /></div>
        <div><strong>{t('plan.noBid')}</strong><Values values={plan.no_bid_opportunities} /></div>
      </div>
    </Section>
    <Section title={t('plan.mandatory')}>
      <div className='summary-strip'>
        <span>{t('plan.total')}: <strong>{decision.mandatory_summary.total_mandatory}</strong></span>
        <span>{t('plan.scheduled')}: <strong>{decision.mandatory_summary.scheduled_count}</strong></span>
        <span>{t('plan.infeasible')}: <strong>{decision.mandatory_summary.infeasible_count}</strong></span>
        <span>{t('plan.omitted')}: <strong>{decision.mandatory_summary.omitted_count}</strong></span>
      </div>
      {decision.mandatory_summary.outcomes.length > 0 && <div className='data-table-wrap'><table className='data-table'>
        <thead><tr><th>{t('plan.workItem')}</th><th>{t('plan.outcome')}</th><th>{t('plan.prerequisites')}</th><th>{t('plan.completion')}</th></tr></thead>
        <tbody>{decision.mandatory_summary.outcomes.map((item) => <tr key={item.work_item_id}>
          <td>{item.work_item_id}</td><td>{item.infeasible ? t('plan.infeasible') : item.scheduled ? t('plan.scheduled') : t('plan.omitted')}</td>
          <td><Values values={item.prerequisite_ids} /></td><td>{item.completion_date ?? '-'}</td>
        </tr>)}</tbody>
      </table></div>}
    </Section>
    <Section title={t('plan.decisions')}>
      <div className='data-table-wrap'><table className='data-table'>
        <thead><tr><th>{t('plan.workItem')}</th><th>{t('plan.action')}</th><th>{t('plan.decision')}</th><th>{t('plan.option')}</th><th>{t('plan.reasonCodes')}</th></tr></thead>
        <tbody>{plan.decisions.map((item) => <tr key={item.action_id}>
          <td>{item.work_item_id}</td><td>{item.action_id}</td><td><span className='decision-label'>{item.decision}</span></td>
          <td>{item.selected_option_id ?? '-'}</td><td><Values values={item.reason_codes} /></td>
        </tr>)}</tbody>
      </table></div>
    </Section>
    <Section title={t('plan.schedule')}>
      {plan.schedule.length === 0 ? <p className='muted'>{t('plan.none')}</p> : <div className='data-table-wrap'><table className='data-table'>
        <thead><tr><th>{t('plan.date')}</th><th>{t('plan.action')}</th><th>{t('plan.person')}</th><th>{t('plan.hours')}</th><th>{t('plan.allocation')}</th></tr></thead>
        <tbody>{plan.schedule.map((item, index) => <tr key={`${item.date}-${item.action_id}-${item.person_id}-${index}`}>
          <td>{item.date}</td><td>{item.action_id}</td><td>{item.person_id}</td><td>{hours(item.hours)}</td><td>{item.allocation_type}</td>
        </tr>)}</tbody>
      </table></div>}
    </Section>
    <Section title={t('plan.assignments')}>
      {plan.assignments.length === 0 ? <p className='muted'>{t('plan.none')}</p> : <div className='data-table-wrap'><table className='data-table'>
        <thead><tr><th>{t('plan.person')}</th><th>{t('plan.action')}</th><th>{t('plan.hours')}</th><th>{t('plan.skills')}</th><th>{t('plan.languages')}</th></tr></thead>
        <tbody>{plan.assignments.map((item, index) => <tr key={`${item.action_id}-${item.person_id}-${index}`}>
          <td>{item.person_id}</td><td>{item.action_id}</td><td>{hours(item.assigned_hours)}</td><td><Values values={item.skills_covered} /></td><td><Values values={item.languages_covered} /></td>
        </tr>)}</tbody>
      </table></div>}
    </Section>
    <Section title={t('plan.prerequisites')}>
      {plan.prerequisite_closures.length === 0 ? <p className='muted'>{t('plan.none')}</p> : <div className='data-table-wrap'><table className='data-table'>
        <thead><tr><th>{t('plan.action')}</th><th>{t('plan.required')}</th><th>{t('plan.unlocks')}</th><th>{t('plan.order')}</th><th>{t('plan.issues')}</th></tr></thead>
        <tbody>{plan.prerequisite_closures.map((item) => <tr key={item.target_action_id}>
          <td>{item.target_action_id}</td><td><Values values={item.required_prerequisites} /></td><td><Values values={item.unlock_triggers} /></td>
          <td><Values values={item.completion_order} /></td><td>{item.cycle_detected ? t('plan.cycle') : <Values values={item.invalid_references} />}</td>
        </tr>)}</tbody>
      </table></div>}
    </Section>
    <Section title={t('plan.capacity')}>
      <div className='data-table-wrap'><table className='data-table'>
        <thead><tr><th>{t('plan.person')}</th><th>{t('plan.capacityHours')}</th><th>{t('plan.usedHours')}</th><th>{t('plan.remainingHours')}</th><th>{t('plan.availableDays')}</th></tr></thead>
        <tbody>{plan.person_capacity.map((item) => <tr key={item.person_id}>
          <td>{item.person_id}</td><td>{hours(item.capacity_hours)}</td><td>{hours(item.used_hours)}</td><td>{hours(item.remaining_hours)}</td><td>{item.available_days}</td>
        </tr>)}</tbody>
      </table></div>
    </Section>
    <Section title={t('plan.resources')}>
      {plan.resource_capacity.length === 0 ? <p className='muted'>{t('plan.none')}</p> : <div className='data-table-wrap'><table className='data-table'>
        <thead><tr><th>{t('plan.resource')}</th><th>{t('plan.capacityHours')}</th><th>{t('plan.usedHours')}</th><th>{t('plan.remainingHours')}</th><th>{t('plan.exclusive')}</th></tr></thead>
        <tbody>{plan.resource_capacity.map((item) => <tr key={item.resource_id}>
          <td>{item.resource_id}</td><td>{hours(item.capacity_hours)}</td><td>{hours(item.used_hours)}</td><td>{hours(item.remaining_hours)}</td><td>{item.exclusive ? t('plan.yes') : t('plan.no')}</td>
        </tr>)}</tbody>
      </table></div>}
    </Section>
    <Section title={t('plan.commercial')}>
      {run.commercial.opportunities.length === 0 ? <p className='muted'>{t('plan.none')}</p> : <div className='data-table-wrap'><table className='data-table'>
        <thead><tr><th>{t('plan.workItem')}</th><th>{t('plan.opportunity')}</th><th>{t('plan.decision')}</th><th>{t('plan.option')}</th><th>{t('plan.probability')}</th></tr></thead>
        <tbody>{run.commercial.opportunities.flatMap((opportunity) => {
          const workDecision = plan.decisions.find((item) => item.work_item_id === opportunity.work_item_id)
          return opportunity.options.map((option) => <tr key={option.option_id}>
            <td>{opportunity.work_item_id}</td><td>{opportunity.title}</td><td>{workDecision?.decision ?? '-'}</td>
            <td>{option.option_id} - {option.label}{workDecision?.selected_option_id === option.option_id ? ` (${t('plan.selected')})` : ''}</td>
            <td>{option.win_probability == null ? '-' : `${Math.round(option.win_probability * 100)}%`}</td>
          </tr>)
        })}</tbody>
      </table></div>}
    </Section>
  </div>
}
