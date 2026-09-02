import { useMemo } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import type { FinalDecisionResult, PlanDecision, ScenarioCashSummary } from '../api/types'
import { CapacityBar } from '../components/dashboard/CapacityBar'
import { ConclusionCard, ManagerStatus, Money, PageIntro } from '../components/business/BusinessUI'
import { interpolate, managerCopy } from '../utils/managerCopy'
import { formatDate, reasonLabel, scenarioLabel, statusTone } from '../utils/presentation'
import { decisionGroup, workDecisionCounts, workLevelDecisions } from '../utils/planDecisions'
import { useWorkflow } from '../workflow/WorkflowContext'
import { localized, workflowCopy } from '../workflow/copy'
import { WorkflowGate, WorkflowProgress } from '../workflow/WorkflowUI'

const percentage = (used: number, total: number) => (total > 0 ? (used / total) * 100 : 0)
const hours = (value: number, locale: string) => value.toLocaleString(locale, { maximumFractionDigits: 1 })

function conclusion(decision: FinalDecisionResult, language?: string) {
  const c = managerCopy(language).dashboard
  if (decision.financial_status !== 'CASH_SAFE') return c.operationalButCashRisk
  if (decision.overall_status === 'PLAN_FEASIBLE') return c.safe
  if (decision.overall_status === 'PLAN_INFEASIBLE') return c.infeasible
  return c.partial
}

function CashCard({ item, currency, locale }: { item: ScenarioCashSummary; currency: string; locale: string }) {
  const { i18n } = useTranslation()
  const c = managerCopy(i18n.resolvedLanguage).dashboard
  return (
    <article className={`cash-outlook-card cash-outlook-card--${statusTone(item.status)}`} data-testid={`cash-scenario-${item.scenario}`}>
      <div>
        <span>{scenarioLabel(item.scenario, i18n.resolvedLanguage)}</span>
        <ManagerStatus status={item.status} />
      </div>
      <strong><Money value={item.ending_cash_jpy} currency={currency} compact={false} /></strong>
      <p>{item.first_buffer_breach_date ? interpolate(c.unsafeFrom, { date: formatDate(item.first_buffer_breach_date, locale) }) : c.safeFrom}</p>
    </article>
  )
}

export function DashboardPage() {
  const { i18n } = useTranslation()
  const c = managerCopy(i18n.resolvedLanguage).dashboard
  const workflowC = workflowCopy(i18n.resolvedLanguage)
  const locale = i18n.resolvedLanguage ?? 'en'
  const workflow = useWorkflow()
  const navigate = useNavigate()

  if (!workflow.catalog) {
    const useSample = async () => {
      try {
        await workflow.loadSample()
        navigate('/planning')
      } catch {
        /* error is shown below */
      }
    }
    return (
      <div>
        <section className="workflow-entry">
          <span className="eyebrow">{workflowC.entry.eyebrow}</span>
          <h1>{workflowC.entry.title}</h1>
          <p>{workflowC.entry.description}</p>
          <div className="workflow-entry__actions">
            <button className="button" onClick={() => navigate('/planning?mode=new')}>{workflowC.entry.create}</button>
            <button className="button button--secondary" disabled={workflow.busy} onClick={() => void useSample()}>{workflowC.entry.sample}</button>
          </div>
          {workflow.error && <p className="form-errors" role="alert">{workflowC.planning.invalid}</p>}
        </section>
        <WorkflowProgress status={workflow.status} />
      </div>
    )
  }

  if (!workflow.generation) {
    return (
      <div>
        <PageIntro eyebrow={workflowC.entry.eyebrow} title={workflowC.entry.title} description={workflowC.entry.description} />
        <WorkflowProgress status={workflow.status} />
        <WorkflowGate kind={workflow.status === 'DATA_LOADED' ? 'analysis' : 'plan'} />
      </div>
    )
  }

  const baseline = workflow.catalog.summary
  const decision = workflow.generation.final_decision
  const e = decision.executive_summary
  const workCounts = workflow.generation.plan
    ? workDecisionCounts(workflow.generation.plan)
    : { do: e.selected_count, delay: e.delayed_count, noBid: e.no_bid_count }

  const cap = decision.capacity_summary
  const utilisation = percentage(cap.total_used_hours, cap.total_capacity_hours)
  const expected = decision.cash_summary.scenarios.find((item) => item.scenario === 'EXPECTED')
  const people = [...cap.people].sort((a, b) => b.utilisation_pct - a.utilisation_pct)

  const totalPeopleCount = workflow.catalog.people.length || cap.people.length || 0
  const activePeopleCount = workflow.catalog.people.filter((p) => p.capacity_hours > 0).length || totalPeopleCount
  const totalWorkCount = workflow.catalog.work_items.length || (workCounts.do + workCounts.delay + workCounts.noBid)

  // Calculate distinct decisions by unique work item ID
  const displayDecisions = useMemo(() => {
    if (!workflow.generation?.plan) return []
    return workLevelDecisions(workflow.generation.plan)
  }, [workflow.generation])

  const evidence = (
    <ul>
      <li>{interpolate(c.evidenceMandatory, { scheduled: decision.mandatory_summary.scheduled_count, total: decision.mandatory_summary.total_mandatory })}</li>
      <li>{interpolate(c.evidenceCapacity, { used: hours(cap.total_used_hours, locale), total: hours(cap.total_capacity_hours, locale) })}</li>
      <li>{interpolate(c.evidenceCash, { cash: expected ? new Intl.NumberFormat(locale, { style: 'currency', currency: baseline.currency, maximumFractionDigits: 0 }).format(expected.ending_cash_jpy) : '—' })}</li>
    </ul>
  )

  return (
    <div>
      <WorkflowProgress status={workflow.status} />
      <PageIntro eyebrow={c.eyebrow} title={c.title} description={c.description} />

      {/* TOP 4 SUMMARY STATS CARDS */}
      <div className="summary-stat-grid">
        {/* 1. Nhân sự */}
        <div className="summary-stat-card">
          <div className="summary-stat-card__info">
            <span className="summary-stat-card__label">{c.employeesCard}</span>
            <span className="summary-stat-card__value">{activePeopleCount}</span>
            <span className="summary-stat-card__sub">{interpolate(c.totalSuffix, { total: totalPeopleCount })}</span>
          </div>
          <div className="summary-stat-card__icon summary-stat-card__icon--blue">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
              <circle cx="9" cy="7" r="4" />
              <path d="M22 21v-2a4 4 0 0 0-3-3.87" />
              <path d="M16 3.13a4 4 0 0 1 0 7.75" />
            </svg>
          </div>
        </div>

        {/* 2. Tổng công việc */}
        <div className="summary-stat-card">
          <div className="summary-stat-card__info">
            <span className="summary-stat-card__label">{c.totalWorkItems}</span>
            <span className="summary-stat-card__value">{totalWorkCount}</span>
            <span className="summary-stat-card__sub">{interpolate(c.totalSuffix, { total: totalWorkCount })}</span>
          </div>
          <div className="summary-stat-card__icon summary-stat-card__icon--orange">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="2" y="7" width="20" height="14" rx="2" ry="2" />
              <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16" />
            </svg>
          </div>
        </div>

        {/* 3. Công việc thực hiện */}
        <div className="summary-stat-card">
          <div className="summary-stat-card__info">
            <span className="summary-stat-card__label">{c.executedWork}</span>
            <span className="summary-stat-card__value">{workCounts.do}</span>
            <span className="summary-stat-card__sub">{interpolate(c.totalSuffix, { total: totalWorkCount })}</span>
          </div>
          <div className="summary-stat-card__icon summary-stat-card__icon--purple">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" />
              <polyline points="12 6 12 12 16 14" />
            </svg>
          </div>
        </div>

        {/* 4. Năng lực đã sử dụng */}
        <div className="summary-stat-card">
          <div className="summary-stat-card__info">
            <span className="summary-stat-card__label">{c.capacityUsed}</span>
            <span className="summary-stat-card__value">{utilisation.toLocaleString(locale, { maximumFractionDigits: 1 })}%</span>
            <span className="summary-stat-card__sub">{hours(cap.total_used_hours, locale)}h / {hours(cap.total_capacity_hours, locale)}h</span>
          </div>
          <div className="summary-stat-card__icon summary-stat-card__icon--green">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M9 11l3 3L22 4" />
              <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
            </svg>
          </div>
        </div>
      </div>

      {/* Main Conclusion & Status Strip */}
      <ConclusionCard
        eyebrow={c.question}
        title={conclusion(decision, i18n.resolvedLanguage)}
        tone={statusTone(decision.overall_status)}
        evidence={evidence}
        status={decision.overall_status}
      />
      <div className="cash-safety-strip" aria-label={c.audit}>
        <ManagerStatus status={decision.overall_status} testId="badge-overall" />
        <ManagerStatus status={decision.operational_status} testId="badge-operational" />
        <ManagerStatus status={decision.financial_status} testId="badge-financial" />
      </div>

      {/* MIDDLE 3 WIDGETS: WORK STATUS | TEAM CAPACITY | MANAGEMENT ALERTS */}
      <div className="dashboard-middle-grid" style={{ marginTop: '24px' }}>
        {/* Widget 1: Trạng thái công việc */}
        <div className="dashboard-widget-card">
          <div className="dashboard-widget-card__header">
            <h2>
              <span className="dashboard-widget-card__header-icon">📈</span>
              {c.workStatus}
            </h2>
          </div>
          <div className="work-status-list">
            <div className="work-status-row">
              <div className="work-status-row__header">
                <span className="work-status-row__label">{c.executed}</span>
                <span className="work-status-row__count" data-testid="count-Selected">{workCounts.do}</span>
              </div>
              <div className="work-status-bar-bg">
                <div
                  className="work-status-bar-fill work-status-bar-fill--blue"
                  style={{ width: `${totalWorkCount > 0 ? (workCounts.do / totalWorkCount) * 100 : 0}%` }}
                />
              </div>
            </div>

            <div className="work-status-row">
              <div className="work-status-row__header">
                <span className="work-status-row__label">{c.postponed}</span>
                <span className="work-status-row__count" data-testid="count-Delayed">{workCounts.delay}</span>
              </div>
              <div className="work-status-bar-bg">
                <div
                  className="work-status-bar-fill work-status-bar-fill--amber"
                  style={{ width: `${totalWorkCount > 0 ? (workCounts.delay / totalWorkCount) * 100 : 0}%` }}
                />
              </div>
            </div>

            <div className="work-status-row">
              <div className="work-status-row__header">
                <span className="work-status-row__label">{c.noBidStatus}</span>
                <span className="work-status-row__count" data-testid="count-No-bid">{workCounts.noBid}</span>
              </div>
              <div className="work-status-bar-bg">
                <div
                  className="work-status-bar-fill work-status-bar-fill--slate"
                  style={{ width: `${totalWorkCount > 0 ? (workCounts.noBid / totalWorkCount) * 100 : 0}%` }}
                />
              </div>
            </div>

            <div className="work-status-row">
              <div className="work-status-row__header">
                <span className="work-status-row__label">{c.mandatoryStatus}</span>
                <span className="work-status-row__count">
                  {decision.mandatory_summary.scheduled_count}/{decision.mandatory_summary.total_mandatory}
                </span>
              </div>
              <div className="work-status-bar-bg">
                <div
                  className="work-status-bar-fill work-status-bar-fill--emerald"
                  style={{
                    width: `${decision.mandatory_summary.total_mandatory > 0
                      ? (decision.mandatory_summary.scheduled_count / decision.mandatory_summary.total_mandatory) * 100
                      : 100}%`,
                  }}
                />
              </div>
            </div>
          </div>
        </div>

        {/* Widget 2: Năng lực đội ngũ */}
        <div className="dashboard-widget-card">
          <div className="dashboard-widget-card__header">
            <h2>
              <span className="dashboard-widget-card__header-icon">👥</span>
              {c.capacity}
            </h2>
          </div>
          <CapacityBar pct={utilisation} aria-label={c.capacity} />
          <dl className="capacity-metrics-strip">
            <div className="capacity-metric-item">
              <dt>{c.availableHours}</dt>
              <dd>{hours(cap.total_capacity_hours, locale)}h</dd>
            </div>
            <div className="capacity-metric-item">
              <dt>{c.usedHours}</dt>
              <dd>{hours(cap.total_used_hours, locale)}h</dd>
            </div>
            <div className="capacity-metric-item">
              <dt>{c.remainingHours}</dt>
              <dd>{hours(cap.total_remaining_hours, locale)}h</dd>
            </div>
          </dl>
          {people.length > 0 && (
            <div className="capacity-mini-people">
              {people.slice(0, 3).map((person) => {
                const personData = workflow.catalog?.people.find((p) => p.id === person.person_id)
                return (
                  <div key={person.person_id} className="capacity-mini-person">
                    <strong>{personData?.name || person.person_id}</strong>
                    <span>
                      {hours(person.used_hours, locale)}h / {hours(person.capacity_hours, locale)}h ({person.utilisation_pct.toFixed(0)}%)
                    </span>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* Widget 3: Cảnh báo quản trị & Rủi ro */}
        <div className="dashboard-widget-card">
          <div className="dashboard-widget-card__header">
            <h2>
              <span className="dashboard-widget-card__header-icon">⚠️</span>
              {c.managementAlerts}
            </h2>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {decision.financial_status !== 'CASH_SAFE' && (
              <article className="management-alert management-alert--critical" style={{ minHeight: 'auto', padding: '14px' }}>
                <span className="management-alert__icon">!</span>
                <div>
                  <h3 style={{ margin: '0 0 3px' }}>{c.cashRiskAlert}</h3>
                  <strong>{expected ? <Money value={expected.ending_cash_jpy} currency={baseline.currency} /> : '—'}</strong>
                  <p style={{ margin: '4px 0 0', fontSize: '12px' }}>
                    {e.first_buffer_breach_date ? interpolate(c.unsafeFrom, { date: formatDate(e.first_buffer_breach_date, locale) }) : reasonLabel('NEGATIVE_CASH', i18n.resolvedLanguage)}
                  </p>
                </div>
              </article>
            )}

            {utilisation >= 90 && (
              <article className="management-alert management-alert--warning" style={{ minHeight: 'auto', padding: '14px' }}>
                <span className="management-alert__icon">!</span>
                <div>
                  <h3 style={{ margin: '0 0 3px' }}>{c.highUtilizationAlert}</h3>
                  <strong>{interpolate(c.utilised, { pct: utilisation.toLocaleString(locale, { maximumFractionDigits: 1 }) })}</strong>
                  <p style={{ margin: '4px 0 0', fontSize: '12px' }}>{c.constrained}</p>
                </div>
              </article>
            )}

            <article className="management-alert management-alert--neutral" style={{ minHeight: 'auto', padding: '14px' }}>
              <span className="management-alert__icon">✓</span>
              <div>
                <h3 style={{ margin: '0 0 3px' }}>{c.mandatoryCoverageAlert}</h3>
                <strong>{decision.mandatory_summary.scheduled_count}/{decision.mandatory_summary.total_mandatory}</strong>
                <p style={{ margin: '4px 0 0', fontSize: '12px' }}>{reasonLabel('MANDATORY_WORK_SCHEDULED', i18n.resolvedLanguage)}</p>
              </div>
            </article>

            {/* Financial outlook cards */}
            <div style={{ marginTop: '6px' }}>
              {decision.cash_summary.scenarios.map((item) => (
                <CashCard key={item.scenario} item={item} currency={baseline.currency} locale={locale} />
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* BOTTOM SECTION: COMPACT IMPORTANT / UPCOMING WORK TABLE */}
      <div className="dashboard-table-card">
        <div className="dashboard-table-card__header">
          <h2>{c.importantWork}</h2>
          <Link to="/plan">{c.viewAll}</Link>
        </div>
        <div className="compact-work-table-wrap">
          <table className="compact-work-table">
            <thead>
              <tr>
                <th>{c.colWork}</th>
                <th>{c.colPriority}</th>
                <th>{c.colStatus}</th>
                <th>{c.colDeadline}</th>
                <th>{c.colOwner}</th>
              </tr>
            </thead>
            <tbody>
              {displayDecisions.length === 0 ? (
                <tr>
                  <td colSpan={5} style={{ textAlign: 'center', color: 'var(--slate-500)' }}>
                    {c.noWorkItems}
                  </td>
                </tr>
              ) : (
                displayDecisions.slice(0, 8).map((dec: PlanDecision) => {
                  const workItem = workflow.catalog?.work_items.find((w) => w.id === dec.work_item_id)
                  const opportunity = workflow.generation?.commercial?.opportunities?.find((op) => op.work_item_id === dec.work_item_id)
                  const title = localized(workItem?.title, i18n.resolvedLanguage) || opportunity?.title || dec.work_item_id
                  const group = workflow.generation?.plan ? decisionGroup(dec, workflow.generation.plan) : 'do'

                  // Priority determination
                  const isUrgent = workItem?.mandatory || dec.decision === 'SELECTED'
                  const priorityClass = isUrgent ? 'priority-pill--high' : 'priority-pill--medium'
                  const priorityText = isUrgent ? c.priorityHigh : c.priorityMedium

                  // Status determination
                  const statusText = group === 'do' ? c.executed : group === 'delay' ? c.postponed : c.noBidStatus
                  const statusBadgeTone = group === 'do' ? 'feasible' : group === 'delay' ? 'at-risk' : 'infeasible'

                  // Due date & Assigned people
                  const dueDate = workItem?.due_date
                  const assignments = (workflow.generation?.plan.assignments || []).filter(
                    (a) => a.action_id === dec.action_id || a.action_id.startsWith(dec.work_item_id)
                  )
                  const assignedPeople = assignments.map((a) => {
                    const person = workflow.catalog?.people.find((p) => p.id === a.person_id)
                    return person?.name || a.person_id
                  })

                  return (
                    <tr key={dec.action_id || dec.work_item_id}>
                      <td>
                        <strong>{title}</strong>
                        {title !== dec.work_item_id && <span className="secondary-id" style={{ display: 'block' }}>{dec.work_item_id}</span>}
                      </td>
                      <td>
                        <span className={`priority-pill ${priorityClass}`}>{priorityText}</span>
                      </td>
                      <td>
                        <span className={`manager-status status-badge--${statusBadgeTone}`} style={{ fontSize: '11px', padding: '3px 8px' }}>
                          {statusText}
                        </span>
                      </td>
                      <td>
                        <span className="deadline-text">{dueDate ? formatDate(dueDate, locale) : '—'}</span>
                      </td>
                      <td>
                        <span style={{ fontSize: '12px' }}>
                          {assignedPeople.length > 0 ? assignedPeople.join(', ') : c.unassigned}
                        </span>
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
