import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Money, PageIntro } from '../components/business/BusinessUI'
import { formatDate, humanizeCode } from '../utils/presentation'
import { businessReason, decisionConclusion, decisionCopy, decisionImpact, priorityLabel } from '../utils/decisionPresentation'
import { employeeMatchCopy, matchEmployees, type EmployeeFit, type EmployeeMatch } from '../utils/employeeMatching'
import { useWorkflow } from '../workflow/WorkflowContext'
import type { PlanningWorkItem, WorkflowFeasibility, WorkflowScoredCandidate } from '../workflow/types'
import { localized, workflowCopy } from '../workflow/copy'
import { WorkflowGate, WorkflowProgress } from '../workflow/WorkflowUI'

type Filter = 'all' | 'mandatory' | 'commercial' | 'other'
type Priority = 'veryHigh' | 'high' | 'medium' | 'low'

function priorityFor(index: number, count: number): Priority {
  if (count <= 1 || index < Math.ceil(count * 0.25)) return 'veryHigh'
  if (index < Math.ceil(count * 0.5)) return 'high'
  if (index < Math.ceil(count * 0.75)) return 'medium'
  return 'low'
}

function WorkItemCard({
  item, feasibility, candidate, priority, commercial, onSelect,
}: {
  item: PlanningWorkItem
  feasibility?: WorkflowFeasibility
  candidate?: WorkflowScoredCandidate
  priority?: Priority
  commercial: boolean
  onSelect: () => void
}) {
  const { i18n } = useTranslation()
  const c = workflowCopy(i18n.resolvedLanguage).work
  const locale = i18n.resolvedLanguage ?? 'en'
  const dc = decisionCopy(i18n.resolvedLanguage)
  const workflow = useWorkflow()
  const customer = workflow.catalog?.customers.find((value) => value.id === item.customer_id)
  const findings = feasibility ? [...feasibility.hard_failures, ...feasibility.blockers, ...feasibility.warnings] : []
  const candidateFindings = candidate ? [...candidate.reasons, ...candidate.warnings] : []
  const rawCodes = [...findings, ...candidateFindings].map((value) => value.code)
  const analysisReasons = rawCodes
    .map((code) => businessReason(code, i18n.resolvedLanguage))
    .filter((value): value is string => Boolean(value))
    .filter((value, index, values) => values.indexOf(value) === index)
    .slice(0, 3)
  const dependencyIds = feasibility?.dependencies.missing.length ? feasibility.dependencies.missing : item.dependencies
  const impact = decisionImpact(rawCodes[0], dependencyIds, i18n.resolvedLanguage)
  const scorePriority = priorityLabel(candidate?.business_value_score, i18n.resolvedLanguage)
  const priorityText = scorePriority ?? c[priority ?? 'low']
  const title = localized(item.title, i18n.resolvedLanguage) || item.id
  return <article className='portfolio-work-card portfolio-work-card--selectable' data-testid={`work-item-${item.id}`} role='button' tabIndex={0} aria-label={title} onClick={onSelect} onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onSelect() } }}>
    <header>
      <div><h2>{title}</h2><span className='secondary-id'>{item.id} · {humanizeCode(item.type)}</span></div>
      <span className={item.mandatory ? 'work-kind work-kind--mandatory' : commercial ? 'work-kind work-kind--commercial' : 'work-kind'}>{item.mandatory ? c.mandatoryLabel : commercial ? c.commercial : c.optionalLabel}</span>
    </header>
    <dl className='work-review-facts'>
      <div><dt>{c.hours}</dt><dd>{item.required_hours.toLocaleString(locale)} h</dd></div>
      <div><dt>{c.deadline}</dt><dd>{formatDate(item.due_date, locale)}</dd></div>
      <div><dt>{c.customer}</dt><dd>{customer?.name || item.customer_id || c.none}</dd></div>
      <div><dt>{c.dependencies}</dt><dd>{item.dependencies.length ? item.dependencies.join(', ') : c.none}</dd></div>
    </dl>
    {item.revenue_jpy > 0 && <p className='work-commercial-fact'><Money value={item.revenue_jpy} compact={false} /> · {(item.success_probability * 100).toLocaleString(locale, { maximumFractionDigits: 0 })}%</p>}
    {!feasibility ? <div className='not-analyzed-state'><span>○</span>{c.notAnalyzed}</div> : <>
      <div className='work-analysis-summary'>
        <div><span>{dc.priority}</span><strong className={`priority priority--${priority}`}>{priorityText}</strong></div>
        <div><span>{dc.conclusion}</span><strong>{decisionConclusion(feasibility.status, i18n.resolvedLanguage)}</strong></div>
      </div>
      {analysisReasons.length > 0 && <div className='work-analysis-reasons'><strong>{dc.reason}</strong><ul>{analysisReasons.map((reason) => <li key={reason}>{reason}</li>)}</ul></div>}
      <div className='decision-basis'><strong>{dc.basis}</strong><ul>{item.dependencies.length > 0 && <li>{dc.dependency}: {item.dependencies.join(', ')}</li>}{item.mandatory && <li>{dc.mandatory}</li>}<li>{dc.priority}: {priorityText}</li></ul></div>
      {impact && <div className='decision-impact'><strong>{dc.impact}</strong><p>{impact}</p></div>}
    </>}
  </article>
}

function MatchGroup({ title, fit, matches, copy }: { title: string; fit: EmployeeFit; matches: EmployeeMatch[]; copy: ReturnType<typeof employeeMatchCopy> }) {
  return <section className={`employee-match-group employee-match-group--${fit}`}><h3>{title}<span>{matches.length}</span></h3>{matches.length ? <div className='employee-match-list'>{matches.map((match) => <article className='employee-match-card' key={match.person.id}>
    <div className='employee-match-card__heading'><div className='employee-match-avatar'>{(match.person.name || match.person.id).split(' ').map((part) => part[0]).join('').slice(0, 2).toUpperCase()}</div><div><strong>{match.person.name || match.person.id}</strong><span>{match.person.id}</span></div></div>
    <dl>
      <div><dt>{copy.skills}</dt><dd>{copy.matched}: {match.matchedSkills.length ? match.matchedSkills.join(', ') : '—'}</dd>{match.missingSkills.length > 0 && <small>{copy.missing}: {match.missingSkills.join(', ')}</small>}</div>
      <div><dt>{copy.languages}</dt><dd>{copy.matched}: {match.matchedLanguages.length ? match.matchedLanguages.join(', ').toUpperCase() : '—'}</dd>{match.missingLanguages.length > 0 && <small>{copy.missing}: {match.missingLanguages.join(', ').toUpperCase()}</small>}</div>
      <div><dt>{copy.capacity}</dt><dd>{match.availableHours.toLocaleString()} / {match.requiredHours.toLocaleString()} h</dd><small>{match.capacitySufficient ? copy.sufficient : copy.insufficient}</small></div>
    </dl>
  </article>)}</div> : <p className='muted'>{copy.noPeople}</p>}</section>
}

function EmployeeSuggestions({ work, matches, onClose }: { work: PlanningWorkItem; matches: EmployeeMatch[]; onClose: () => void }) {
  const { i18n } = useTranslation()
  const copy = employeeMatchCopy(i18n.resolvedLanguage)
  const title = localized(work.title, i18n.resolvedLanguage) || work.id
  const groups: Array<{ fit: EmployeeFit; label: string }> = [{ fit: 'best', label: copy.best }, { fit: 'partial', label: copy.partial }, { fit: 'notFit', label: copy.notFit }]
  return <div className='employee-suggestion-backdrop' role='dialog' aria-modal='true' aria-labelledby='employee-suggestion-title' onClick={onClose}><div className='employee-suggestion-panel' onClick={(event) => event.stopPropagation()}>
    <header><div><span className='eyebrow'>{work.id}</span><h2 id='employee-suggestion-title'>{copy.title}: {title}</h2><p>{copy.description}</p></div><button type='button' className='modal-close-btn' aria-label={copy.close} onClick={onClose}>×</button></header>
    <div className='employee-suggestion-requirements'>{work.required_skills.length > 0 && <span>{copy.skills}: {work.required_skills.map((item) => `${item.skill} ≥ ${item.min_level}`).join(', ')}</span>}{work.required_languages.length > 0 && <span>{copy.languages}: {work.required_languages.join(', ').toUpperCase()}</span>}<span>{copy.capacity}: {work.required_hours.toLocaleString()} h</span></div>
    <div className='employee-suggestion-groups'>{groups.map((group) => <MatchGroup key={group.fit} title={group.label} fit={group.fit} matches={matches.filter((match) => match.fit === group.fit)} copy={copy} />)}</div>
  </div></div>
}

export function WorkItemsPage() {
  const { i18n } = useTranslation()
  const c = workflowCopy(i18n.resolvedLanguage).work
  const workflow = useWorkflow()
  const navigate = useNavigate()
  const [filter, setFilter] = useState<Filter>('all')
  const [selectedWork, setSelectedWork] = useState<PlanningWorkItem | null>(null)
  const commercialIds = useMemo(() => new Set((workflow.catalog?.commercial_options ?? []).map((item) => item.work_item_id)), [workflow.catalog])
  const filtered = (workflow.catalog?.work_items ?? []).filter((item) => {
    if (filter === 'mandatory') return item.mandatory
    if (filter === 'commercial') return commercialIds.has(item.id)
    if (filter === 'other') return !item.mandatory && !commercialIds.has(item.id)
    return true
  })
  const candidateByWork = useMemo(() => {
    const map = new Map<string, WorkflowScoredCandidate>()
    for (const candidate of workflow.analysis?.scoring.candidates ?? []) {
      const current = map.get(candidate.work_item_id)
      if (!current || (candidate.business_value_score ?? -1) > (current.business_value_score ?? -1)) map.set(candidate.work_item_id, candidate)
    }
    return map
  }, [workflow.analysis])
  const rankedIds = useMemo(() => [...(workflow.catalog?.work_items ?? [])]
    .sort((a, b) => (candidateByWork.get(b.id)?.business_value_score ?? -1) - (candidateByWork.get(a.id)?.business_value_score ?? -1))
    .map((item) => item.id), [workflow.catalog, candidateByWork])
  const remainingHours = useMemo(() => new Map((workflow.generation?.plan.person_capacity ?? []).map((person) => [person.person_id, person.remaining_hours])), [workflow.generation])
  const employeeMatches = useMemo(() => selectedWork && workflow.catalog ? matchEmployees(selectedWork, workflow.catalog.people, remainingHours) : [], [selectedWork, workflow.catalog, remainingHours])

  if (!workflow.catalog) return <WorkflowGate kind='data' />
  const analyze = async () => { await workflow.analyze().catch(() => undefined) }
  const generate = async () => {
    try { await workflow.generate(); navigate('/plan') } catch { /* context exposes the error */ }
  }
  return <div>
    <PageIntro eyebrow={c.eyebrow} title={c.title} description={c.description} />
    <WorkflowProgress status={workflow.status} />
    {workflow.analysis && <div className='analysis-principle'><span aria-hidden='true'>i</span><div><strong>{c.analysisReady}</strong><p>{c.analysisExplain}</p></div></div>}
    <div className='work-filter-bar' role='group' aria-label={c.title}>
      {(['all', 'mandatory', 'commercial', 'other'] as Filter[]).map((value) => <button key={value} className={filter === value ? 'filter-chip filter-chip--active' : 'filter-chip'} onClick={() => setFilter(value)}>{c[value]}</button>)}
    </div>
    <div className='portfolio-work-grid'>{filtered.map((item) => {
      const feasibility = workflow.analysis?.feasibility.find((value) => value.work_item_id === item.id)
      const candidate = candidateByWork.get(item.id)
      const rank = rankedIds.indexOf(item.id)
      return <WorkItemCard key={item.id} item={item} feasibility={feasibility} candidate={candidate} priority={workflow.analysis ? priorityFor(rank, rankedIds.length) : undefined} commercial={commercialIds.has(item.id)} onSelect={() => setSelectedWork(item)} />
    })}</div>
    {selectedWork && <EmployeeSuggestions work={selectedWork} matches={employeeMatches} onClose={() => setSelectedWork(null)} />}
    <div className='workflow-sticky-action'>
      {!workflow.analysis ? <button className='button' disabled={workflow.busy} onClick={() => void analyze()}>{workflow.busy ? c.analyzing : c.analyze}</button> :
        workflow.status !== 'PLAN_GENERATED' ? <button className='button' disabled={workflow.busy} onClick={() => void generate()}>{workflow.busy ? c.generating : c.generate}</button> :
          <button className='button' onClick={() => navigate('/plan')}>{c.openPlan}</button>}
      {workflow.error && <span role='alert'>{workflow.error}</span>}
    </div>
  </div>
}
