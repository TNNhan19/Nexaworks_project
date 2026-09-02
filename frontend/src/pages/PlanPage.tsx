import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { scenarioApi } from '../api/endpoints'
import type { PlanDecision, ScenarioRun } from '../api/types'
import { ConclusionCard, ManagementSection, ManagerError, ManagerLoading, PageIntro, RunContext } from '../components/business/BusinessUI'
import { RunContextNav } from '../components/run/RunContextNav'
import { interpolate, managerCopy } from '../utils/managerCopy'
import { decisionLabel, formatDate, statusTone } from '../utils/presentation'
import { businessReason, decisionConclusion, decisionCopy, decisionImpact, priorityLabel } from '../utils/decisionPresentation'
import { decisionGroup, workLevelDecisions, type DecisionGroup } from '../utils/planDecisions'
import { useWorkflow } from '../workflow/WorkflowContext'
import { localized, template, workflowCopy } from '../workflow/copy'
import { WorkflowGate, WorkflowProgress } from '../workflow/WorkflowUI'

const sum = (values: number[]) => values.reduce((total, value) => total + value, 0)

function WorkCard({ item, run, activeWorkflow }: { item: PlanDecision; run: ScenarioRun; activeWorkflow: boolean }) {
  const { i18n } = useTranslation()
  const c = managerCopy(i18n.resolvedLanguage).plan
  const wc = workflowCopy(i18n.resolvedLanguage)
  const dc = decisionCopy(i18n.resolvedLanguage)
  const workflow = useWorkflow()
  const locale = i18n.resolvedLanguage ?? 'en'
  const opportunity = run.commercial.opportunities.find((entry) => entry.work_item_id === item.work_item_id)
  const option = opportunity?.options.find((entry) => entry.option_id === item.selected_option_id)
  const schedule = run.plan.schedule.filter((entry) => entry.action_id === item.action_id)
  const assignments = run.plan.assignments.filter((entry) => entry.action_id === item.action_id)
  const dates = schedule.map((entry) => entry.date).sort()
  const people = assignments.length
    ? [...assignments]
      .sort((a, b) => (a.assignment_role === 'OWNER' ? -1 : 0) - (b.assignment_role === 'OWNER' ? -1 : 0))
      .map((entry) => {
        const person = workflow.catalog?.people.find((candidate) => candidate.id === entry.person_id)
        const name = person?.name || entry.person_id
        const role = entry.assignment_role === 'OWNER' ? wc.assignment.owner : wc.assignment.contributor
        return name === entry.person_id
          ? `${entry.person_id} (${role})`
          : `${name} · ${entry.person_id} (${role})`
      })
    : [...new Set(schedule.map((entry) => entry.person_id))]
  const totalHours = assignments.length ? sum(assignments.map((entry) => entry.assigned_hours)) : sum(schedule.map((entry) => entry.hours))
  const mainReason = item.reason_codes[0]
  const friendlyReason = businessReason(mainReason, i18n.resolvedLanguage)
  const impact = decisionImpact(mainReason, item.prerequisite_ids, i18n.resolvedLanguage)
  const priority = priorityLabel(item.business_value_score, i18n.resolvedLanguage)
  const mandatory = item.reason_codes.some((code) => code.includes('MANDATORY')) || run.final_decision.mandatory_summary.outcomes.some((outcome) => outcome.work_item_id === item.work_item_id)
  const hasBasis = item.prerequisite_ids.length > 0 || mandatory || Boolean(priority)
  return <article className={`work-decision-card work-decision-card--${decisionGroup(item, run.plan)}`} data-testid={`decision-${item.action_id}`}>
    <div className='work-decision-card__heading'><div>{opportunity?.title ? <><h3>{opportunity.title}</h3><span className='secondary-id'>{item.work_item_id} · {item.action_id}</span></> : <><h3>{item.work_item_id}</h3><span className='secondary-id'>{item.action_id}</span></>}</div><span className='business-decision-label'>{decisionLabel(item.decision, i18n.resolvedLanguage)}</span></div>
    {option && <p className='selected-option'>{interpolate(c.option, { label: option.label || option.option_id })}</p>}
    {opportunity && <div className='commercial-evidence'><strong>{c.commercial}</strong>{opportunity.options.map((entry) => <span key={entry.option_id}>{entry.label || entry.option_id}{entry.win_probability == null ? '' : ` · ${(entry.win_probability * 100).toLocaleString(locale, { maximumFractionDigits: 1 })}%`}</span>)}</div>}
    <dl className='work-facts'><div><dt>{c.schedule}</dt><dd>{dates.length ? interpolate(c.dates, { start: formatDate(dates[0], locale), end: formatDate(dates.at(-1), locale) }) : '—'}</dd></div><div><dt>{c.team}</dt><dd>{people.length ? people.join(', ') : '—'}</dd></div><div><dt>{c.hours}</dt><dd>{totalHours.toLocaleString(locale, { maximumFractionDigits: 1 })} h</dd></div></dl>
    <div className='decision-conclusion'><strong>{dc.conclusion}</strong><p>{decisionConclusion(item.decision, i18n.resolvedLanguage)}</p></div>
    {friendlyReason && <div className='business-reason'><span aria-hidden='true'>→</span><div><strong>{dc.reason}</strong><p>{friendlyReason}</p></div></div>}
    {hasBasis && <div className='decision-basis'><strong>{dc.basis}</strong><ul>{item.prerequisite_ids.length > 0 && <li>{dc.dependency}: {item.prerequisite_ids.join(', ')}</li>}{mandatory && <li>{dc.mandatory}</li>}{priority && <li>{dc.priority}: {priority}</li>}</ul></div>}
    {impact && <div className='decision-impact'><strong>{dc.impact}</strong><p>{impact}</p></div>}
    {activeWorkflow && decisionGroup(item, run.plan) !== 'do' && <div className='contextual-actions'><Link to='/scenarios?focus=capacity'>{wc.contextual.capacity}</Link></div>}
  </article>
}

function PlanContent({ run, activeWorkflow }: { run: ScenarioRun; activeWorkflow: boolean }) {
  const { i18n } = useTranslation()
  const c = managerCopy(i18n.resolvedLanguage).plan
  const wc = workflowCopy(i18n.resolvedLanguage)
  const workflow = useWorkflow()
  const locale = i18n.resolvedLanguage ?? 'en'
  const displayDecisions = workLevelDecisions(run.plan)
  const groups: Record<DecisionGroup, PlanDecision[]> = { do: [], delay: [], noBid: [] }
  displayDecisions.forEach((item) => groups[decisionGroup(item, run.plan)].push(item))
  const counts = { do: groups.do.length, delay: groups.delay.length, noBid: groups.noBid.length }
  const plan = run.plan
  const decision = run.final_decision
  const used = decision.capacity_summary.total_used_hours
  const total = decision.capacity_summary.total_capacity_hours
  const resourcesValid = !(decision.resource_summary?.violations.length)
  const dependenciesValid = plan.prerequisite_closures.every((item) => !item.cycle_detected && item.invalid_references.length === 0)
  return <div>
    {activeWorkflow && <WorkflowProgress status='PLAN_GENERATED' />}
    <RunContext runId={run.run_id} timestamp={run.timestamp} scenarioName={run.scenario_id} />
    {!activeWorkflow && <RunContextNav runId={run.run_id} />}
    <PageIntro eyebrow={c.eyebrow} title={c.title} description={c.description} />
    <ConclusionCard eyebrow={c.conclusion} title={interpolate(c.summary, { selected: counts.do, delayed: counts.delay, noBid: counts.noBid })} tone={statusTone(decision.operational_status)} status={decision.operational_status} evidence={<ul><li>{interpolate(c.mandatory, { scheduled: decision.mandatory_summary.scheduled_count, total: decision.mandatory_summary.total_mandatory })}</li><li>{interpolate(c.capacity, { used: used.toLocaleString(locale, { maximumFractionDigits: 1 }), total: total.toLocaleString(locale, { maximumFractionDigits: 1 }) })}</li></ul>} />
    <ManagementSection title={wc.validation.title}><div className='plan-check-grid'>
      <article><span>{wc.validation.mandatory}</span><strong>{template(wc.validation.covered, { done: decision.mandatory_summary.scheduled_count, total: decision.mandatory_summary.total_mandatory })}</strong></article>
      <article><span>{wc.validation.capacity}</span><strong>{used.toLocaleString(locale)} / {total.toLocaleString(locale)} h</strong></article>
      <article><span>{wc.validation.resources}</span><strong>{resourcesValid ? wc.validation.noConflict : wc.validation.conflict}</strong></article>
      <article><span>{wc.validation.dependencies}</span><strong>{dependenciesValid ? wc.validation.valid : wc.validation.conflict}</strong></article>
      <article><span>{wc.validation.cash}</span><strong>{decision.financial_status === 'CASH_SAFE' ? wc.validation.safe : wc.validation.atRisk}</strong></article>
    </div></ManagementSection>
    {(['do', 'delay', 'noBid'] as DecisionGroup[]).map((group) => <ManagementSection key={group} title={c[group]} className={`decision-group decision-group--${group}`}><div className='work-card-grid'>{groups[group].length ? groups[group].map((item) => <WorkCard key={item.action_id} item={item} run={run} activeWorkflow={activeWorkflow} />) : <p className='muted'>{c.noItems}</p>}</div></ManagementSection>)}
    <ManagementSection title={c.assignments}><div className='manager-table-wrap'><table className='manager-table'><thead><tr><th>{c.team}</th><th>{c.work}</th><th>{c.hours}</th></tr></thead><tbody>{plan.assignments.map((item, index) => {
        const person = workflow.catalog?.people.find((candidate) => candidate.id === item.person_id)
        const role = item.assignment_role === 'OWNER' ? wc.assignment.owner : wc.assignment.contributor
        return <tr key={`${item.person_id}-${item.action_id}-${index}`}><td><strong>{person?.name || item.person_id}</strong>{person?.name && person.name !== item.person_id && <small className='secondary-id'>{item.person_id}</small>}<small>{role}{person?.role ? ` · ${localized(person.role, i18n.resolvedLanguage)}` : ''}</small></td><td>{item.action_id}</td><td>{item.assigned_hours.toLocaleString(locale, { maximumFractionDigits: 1 })} h</td></tr>
      })}</tbody></table></div></ManagementSection>
    <ManagementSection title={wc.validation.capacity}><div className='people-capacity-grid'>{plan.person_capacity.map((person) => <article key={person.person_id}><strong>{person.person_id}</strong><span>{person.used_hours.toLocaleString(locale)} / {person.capacity_hours.toLocaleString(locale)} h</span><small>{person.remaining_hours.toLocaleString(locale)} h</small></article>)}</div></ManagementSection>
    {activeWorkflow && <div className='workflow-actions workflow-actions--end'><Link className='button button--secondary' to='/cash-flow'>{wc.contextual.cash}</Link><Link className='button' to='/dashboard'>{wc.validation.executive}</Link></div>}
  </div>
}

export function PlanPage() {
  const [params] = useSearchParams()
  const runId = params.get('run_id')
  const workflow = useWorkflow()
  const [historicalRun, setHistoricalRun] = useState<ScenarioRun | null>(null)
  const [loading, setLoading] = useState(Boolean(runId))
  const [error, setError] = useState(false)
  const [reloadKey, setReloadKey] = useState(0)
  useEffect(() => {
    if (!runId) { setLoading(false); setHistoricalRun(null); return }
    let current = true
    setLoading(true)
    setError(false)
    void scenarioApi.getRun(runId).then((value) => { if (current) { setHistoricalRun(value); setLoading(false) } }).catch(() => { if (current) { setError(true); setLoading(false) } })
    return () => { current = false }
  }, [runId, reloadKey])
  if (runId && loading) return <ManagerLoading />
  if (runId && error) return <ManagerError onRetry={() => setReloadKey((value) => value + 1)} />
  if (runId) return historicalRun?.status === 'COMPLETED' ? <PlanContent run={historicalRun} activeWorkflow={false} /> : <WorkflowGate kind='plan' />
  if (!workflow.catalog) return <WorkflowGate kind='data' />
  if (!workflow.analysis) return <WorkflowGate kind='analysis' />
  if (!workflow.generation) return <WorkflowGate kind='plan' />
  const activeRun = {
    run_id: 'ACTIVE-PLAN',
    scenario_id: workflow.catalog.summary.dataset_id,
    timestamp: workflow.generatedAt ?? new Date().toISOString(),
    effective_input: {}, assumptions: {}, status: 'COMPLETED', error: null,
    ...workflow.generation,
  } as unknown as ScenarioRun
  return <PlanContent run={activeRun} activeWorkflow />
}
