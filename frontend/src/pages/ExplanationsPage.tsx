import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { scenarioApi } from '../api/endpoints'
import type { DecisionExplanation, ExplanationRecord, ScenarioRun } from '../api/types'
import type { PlanningWorkItem } from '../workflow/types'
import { ManagerError, ManagerLoading, PageIntro, RunContext } from '../components/business/BusinessUI'
import { RunContextNav } from '../components/run/RunContextNav'
import { interpolate, managerCopy } from '../utils/managerCopy'
import { decisionLabel, formatDate, reasonTopic } from '../utils/presentation'
import { businessEvidence, businessReason, committedCustomerFact, decisionConclusion, decisionCopy, decisionImpact, priorityLabel, type BusinessEvidence } from '../utils/decisionPresentation'
import { localized } from '../workflow/copy'
import { useWorkflow } from '../workflow/WorkflowContext'
import { WorkflowGate, WorkflowProgress } from '../workflow/WorkflowUI'

type Topic = ReturnType<typeof reasonTopic>
const topics: Topic[] = ['commitments', 'capacity', 'commercial', 'cash', 'dependencies', 'risk']

function primitive(value: unknown, key: string, locale: string) {
  if (typeof value === 'number' && key.endsWith('_jpy')) return new Intl.NumberFormat(locale, { style: 'currency', currency: 'JPY', maximumFractionDigits: 0 }).format(value)
  if (typeof value === 'number' && key.includes('hours')) return `${value.toLocaleString(locale)} h`
  if (typeof value === 'string' && (key === 'date' || key.endsWith('_date') || key.includes('completion'))) return formatDate(value, locale)
  return String(value)
}

function Evidence({ items }: { items: BusinessEvidence[] }) {
  const { i18n } = useTranslation()
  const locale = i18n.resolvedLanguage ?? 'en'
  return <dl className='evidence-grid'>{items.map((item) => <div key={`${item.fieldKey}-${String(item.value)}`}><dt>{item.label}</dt><dd>{primitive(item.value, item.fieldKey, locale)}</dd></div>)}</dl>
}

function uniqueEvidence(items: BusinessEvidence[]) {
  const seen = new Set<string>()
  return items.filter((item) => {
    const key = `${item.fieldKey}:${String(item.value)}`
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

function scoreFrom(value: Record<string, unknown>): number | null {
  const score = value.business_value_score ?? value.score
  return typeof score === 'number' ? score : null
}

function dependencyIds(value: Record<string, unknown>): string[] {
  const keys = ['missing_dependencies', 'prerequisite_ids', 'dependencies', 'required_prerequisites', 'missing']
  return [...new Set(keys.flatMap((key) => Array.isArray(value[key]) ? (value[key] as unknown[]).filter((entry): entry is string => typeof entry === 'string') : []))]
}

function DecisionCard({ item, work }: { item: DecisionExplanation; work?: PlanningWorkItem }) {
  const { i18n } = useTranslation()
  const c = managerCopy(i18n.resolvedLanguage).explanation
  const dc = decisionCopy(i18n.resolvedLanguage)
  const label = decisionLabel(item.decision, i18n.resolvedLanguage)
  const reasons = [...new Set(item.reason_codes.map((code) => businessReason(code, i18n.resolvedLanguage)).filter((reason): reason is string => Boolean(reason)))]
  const evidence = uniqueEvidence([
    ...businessEvidence(item.details, i18n.resolvedLanguage),
    ...item.findings.flatMap((finding) => businessEvidence(finding.evidence, i18n.resolvedLanguage)),
  ])
  const dependencyRule = item.reason_codes.some((code) => ['DEPENDENCY_NOT_SATISFIED', 'DEPENDENCY_ORDER_ENFORCED', 'PREREQUISITE_SELECTED', 'MANDATORY_ITEM_BLOCKED'].includes(code))
  const dependencies = dependencyRule ? [...new Set([...dependencyIds(item.details), ...item.findings.flatMap((finding) => dependencyIds(finding.evidence)), ...(work?.dependencies ?? [])])] : []
  const priority = priorityLabel(scoreFrom(item.details), i18n.resolvedLanguage)
  const mandatory = Boolean(work?.mandatory) || item.reason_codes.some((code) => code.includes('MANDATORY'))
  const committed = committedCustomerFact(work?.committed, work?.customer_id, i18n.resolvedLanguage)
  const impact = item.reason_codes.map((code) => decisionImpact(code, dependencies, i18n.resolvedLanguage)).find((value): value is string => Boolean(value))
  const hasBasis = evidence.length > 0 || dependencies.length > 0 || mandatory || Boolean(committed) || Boolean(priority)
  const title = localized(work?.title, i18n.resolvedLanguage) || item.work_item_id
  return <article className='explanation-business-card'>
    <div className='explanation-business-card__heading'><div><span className='secondary-id'>{item.work_item_id}</span><h3>{interpolate(c.why, { item: title, decision: label })}</h3></div><span className='business-decision-label'>{label}</span></div>
    <div className='decision-conclusion'><strong>{dc.conclusion}</strong><p>{decisionConclusion(item.decision, i18n.resolvedLanguage)}</p></div>
    {reasons.length > 0 && <div className='primary-explanation'><strong>{dc.reason}</strong><ul>{reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul></div>}
    {hasBasis && <div className='supporting-evidence'><h4>{dc.basis}</h4>{evidence.length > 0 && <Evidence items={evidence} />}<ul>{committed && <li>{committed}</li>}{dependencies.length > 0 && <li>{dc.dependency}: {dependencies.join(', ')}</li>}{mandatory && <li>{dc.mandatory}</li>}{priority && <li>{dc.priority}: {priority}</li>}</ul></div>}
    {impact && <div className='decision-impact'><strong>{dc.impact}</strong><p>{impact}</p></div>}
  </article>
}

function FindingCard({ finding }: { finding: ExplanationRecord }) {
  const { i18n } = useTranslation()
  const dc = decisionCopy(i18n.resolvedLanguage)
  const reason = businessReason(finding.code, i18n.resolvedLanguage)
  if (!reason) return null
  const details = businessEvidence(finding.evidence, i18n.resolvedLanguage)
  const dependencies = dependencyIds(finding.evidence)
  const impact = decisionImpact(finding.code, dependencies, i18n.resolvedLanguage)
  return <article className='explanation-business-card finding-business-card'>
    <h3>{reason}</h3>
    {finding.source_id && <p className='secondary-id'>{finding.source_id}</p>}
    {details.length > 0 && <div className='supporting-evidence'><h4>{dc.basis}</h4><Evidence items={details} /></div>}
    {impact && <div className='decision-impact'><strong>{dc.impact}</strong><p>{impact}</p></div>}
  </article>
}

export function ExplanationsPage() {
  const { i18n } = useTranslation()
  const c = managerCopy(i18n.resolvedLanguage).explanation
  const [params] = useSearchParams()
  const runId = params.get('run_id')
  const workflow = useWorkflow()
  const [run, setRun] = useState<ScenarioRun | null>(null)
  const [loading, setLoading] = useState(Boolean(runId))
  const [error, setError] = useState(false)
  const [reloadKey, setReloadKey] = useState(0)
  useEffect(() => {
    if (!runId) { setLoading(false); return }
    let current = true
    setLoading(true)
    setError(false)
    void scenarioApi.getRun(runId).then((value) => { if (current) { setRun(value); setLoading(false) } }).catch(() => { if (current) { setError(true); setLoading(false) } })
    return () => { current = false }
  }, [runId, reloadKey])
  const activeWorkflowRun = workflow.generation && workflow.catalog ? {
    run_id: 'ACTIVE-PLAN', scenario_id: workflow.catalog.summary.dataset_id,
    timestamp: workflow.generatedAt ?? new Date().toISOString(), effective_input: {}, assumptions: {},
    status: 'COMPLETED', error: null, ...workflow.generation,
  } as unknown as ScenarioRun : null
  const displayRun = runId ? run : activeWorkflowRun
  const workItems = useMemo(() => {
    const effective = displayRun?.effective_input as { work_items?: PlanningWorkItem[] } | undefined
    return runId ? (effective?.work_items ?? []) : (workflow.catalog?.work_items ?? effective?.work_items ?? [])
  }, [displayRun, runId, workflow.catalog])
  const workMap = useMemo(() => new Map(workItems.map((work) => [work.id, work])), [workItems])
  const grouped = useMemo(() => {
    const output = Object.fromEntries(topics.map((topic) => [topic, { decisions: [] as DecisionExplanation[], findings: [] as ExplanationRecord[] }])) as Record<Topic, { decisions: DecisionExplanation[]; findings: ExplanationRecord[] }>
    if (displayRun?.final_decision) {
      displayRun.final_decision.decision_explanations.forEach((item) => {
        const code = item.reason_codes.find((reason) => businessReason(reason, i18n.resolvedLanguage)) ?? item.reason_codes[0] ?? ''
        output[reasonTopic(code, item.findings[0]?.source_phase)].decisions.push(item)
      })
      displayRun.final_decision.explanation_records.forEach((finding) => {
        if (businessReason(finding.code, i18n.resolvedLanguage)) output[reasonTopic(finding.code, finding.source_phase)].findings.push(finding)
      })
    }
    return output
  }, [displayRun, i18n.resolvedLanguage])
  if (runId && loading) return <ManagerLoading />
  if (runId && error) return <ManagerError onRetry={() => setReloadKey((value) => value + 1)} />
  if (!runId && !workflow.catalog) return <WorkflowGate kind='data' />
  if (!runId && !workflow.analysis) return <WorkflowGate kind='analysis' />
  if (!runId && !workflow.generation) return <WorkflowGate kind='plan' />
  if (!displayRun || displayRun.status === 'FAILED') return <WorkflowGate kind='plan' />
  return <div>{!runId && <WorkflowProgress status='PLAN_GENERATED' />}<RunContext runId={displayRun.run_id} timestamp={displayRun.timestamp} scenarioName={displayRun.scenario_id} />{runId && <RunContextNav runId={displayRun.run_id} />}<PageIntro eyebrow={c.eyebrow} title={c.title} description={c.description} /><nav className='topic-nav' aria-label={c.title}>{topics.map((topic) => <a key={topic} href={`#topic-${topic}`}>{c[topic]}</a>)}</nav>
    {topics.map((topic) => { const group = grouped[topic]; if (!group.decisions.length && !group.findings.length) return null; return <section className='explanation-topic' id={`topic-${topic}`} key={topic}><header><span className='topic-icon' aria-hidden='true'>{topic === 'cash' ? '¥' : topic === 'capacity' ? '◫' : topic === 'dependencies' ? '↳' : topic === 'commitments' ? '✓' : topic === 'commercial' ? '↗' : '!'}</span><h2>{c[topic]}</h2></header><div className='decision-explanation-list'>{group.decisions.map((item) => <DecisionCard key={item.action_id} item={item} work={workMap.get(item.work_item_id)} />)}{group.findings.map((finding, index) => <FindingCard key={`${finding.code}-${finding.source_id ?? 'global'}-${index}`} finding={finding} />)}</div></section> })}
  </div>
}
