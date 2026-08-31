import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { decisionApi, systemApi } from '../api/endpoints'
import type {
  BaselineSummary,
  ExplanationRecord,
  FinalDecisionResult,
  FutureReceiptSummary,
  HealthResponse,
  PersonCapacitySummary,
  ScenarioCashSummary,
} from '../api/types'
import { CapacityBar } from '../components/dashboard/CapacityBar'
import { StatusBadge } from '../components/dashboard/StatusBadge'
import { ErrorState, LoadingState } from '../components/system/AsyncState'

// ─── State ────────────────────────────────────────────────────────────────

type DashboardState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | {
      status: 'ready'
      health: HealthResponse
      baseline: BaselineSummary
      decision: FinalDecisionResult
    }

// ─── Formatters ────────────────────────────────────────────────────────────

function fmtMoney(value: number | null | undefined, currency: string, locale: string): string {
  if (value == null) return '—'
  return new Intl.NumberFormat(locale, { style: 'currency', currency, maximumFractionDigits: 0 }).format(value)
}

function fmtDate(value: string | null | undefined, locale: string): string {
  if (!value) return '—'
  return new Intl.DateTimeFormat(locale, { year: 'numeric', month: 'short', day: 'numeric' }).format(
    new Date(`${value}T00:00:00`),
  )
}

function fmtHours(value: number, locale: string): string {
  return value.toLocaleString(locale, { maximumFractionDigits: 1 })
}

function fmtPct(value: number): string {
  return `${Math.round(value)}%`
}

// ─── Sub-sections ─────────────────────────────────────────────────────────

function SectionHeader({ title }: { title: string }) {
  return (
    <div className="exec-section-header">
      <h2>{title}</h2>
    </div>
  )
}

// 1. Decision Status
function DecisionStatusSection({ decision }: { decision: FinalDecisionResult }) {
  const { t } = useTranslation()
  return (
    <section className="exec-section" aria-labelledby="section-decision-status">
      <SectionHeader title={t('exec.decisionStatus')} />
      <div className="exec-grid-3">
        <div className="status-card">
          <span className="status-card__label">{t('exec.overallStatus')}</span>
          <StatusBadge status={decision.overall_status} testId="badge-overall" />
        </div>
        <div className="status-card">
          <span className="status-card__label">{t('exec.operationalStatus')}</span>
          <StatusBadge status={decision.operational_status} testId="badge-operational" />
        </div>
        <div className="status-card">
          <span className="status-card__label">{t('exec.financialStatus')}</span>
          <StatusBadge status={decision.financial_status} testId="badge-financial" />
        </div>
      </div>
    </section>
  )
}

// 2. Portfolio Summary
function PortfolioSection({ decision }: { decision: FinalDecisionResult }) {
  const { t } = useTranslation()
  const s = decision.executive_summary
  const ms = decision.mandatory_summary

  const counts = [
    { label: t('exec.selected'), value: s.selected_count, cls: '' },
    { label: t('exec.delayed'), value: s.delayed_count, cls: s.delayed_count > 0 ? 'count-card__value--warn' : '' },
    { label: t('exec.noBid'), value: s.no_bid_count, cls: '' },
    { label: t('exec.mandatoryScheduled'), value: ms.scheduled_count, cls: '' },
    {
      label: t('exec.mandatoryInfeasible'),
      value: ms.infeasible_count,
      cls: ms.infeasible_count > 0 ? 'count-card__value--danger' : '',
    },
  ]

  return (
    <section className="exec-section" aria-labelledby="section-portfolio">
      <SectionHeader title={t('exec.portfolioSummary')} />
      <div className="exec-grid-4" style={{ gridTemplateColumns: 'repeat(5,1fr)' }}>
        {counts.map((c) => (
          <div className="count-card" key={c.label}>
            <span className="count-card__label">{c.label}</span>
            <span className={`count-card__value ${c.cls}`} data-testid={`count-${c.label}`}>
              {c.value.toLocaleString()}
            </span>
          </div>
        ))}
      </div>
    </section>
  )
}

// 3. Capacity
function CapacitySection({
  decision,
  locale,
}: {
  decision: FinalDecisionResult
  locale: string
}) {
  const { t } = useTranslation()
  const cap = decision.capacity_summary
  const people: PersonCapacitySummary[] = [...cap.people].sort((a, b) => b.utilisation_pct - a.utilisation_pct)

  return (
    <section className="exec-section" aria-labelledby="section-capacity">
      <SectionHeader title={t('exec.capacitySection')} />
      <div className="exec-grid-3" style={{ gridTemplateColumns: '1fr' }}>
        <div className="capacity-total">
          <div className="capacity-total__stat">
            <span>{t('exec.totalUsed')}</span>
            <strong>{fmtHours(cap.total_used_hours, locale)} h</strong>
          </div>
          <div className="capacity-total__stat">
            <span>{t('exec.totalAvailable')}</span>
            <strong>{fmtHours(cap.total_capacity_hours, locale)} h</strong>
          </div>
          <div className="capacity-total__stat">
            <span>{t('exec.totalRemaining')}</span>
            <strong>{fmtHours(cap.total_remaining_hours, locale)} h</strong>
          </div>
          {cap.violations.length > 0 && (
            <div className="capacity-total__stat">
              <span style={{ color: 'var(--danger)' }}>
                ⚠ {cap.violations.length} violation{cap.violations.length !== 1 ? 's' : ''}
              </span>
            </div>
          )}
        </div>

        {people.length > 0 && (
          <div className="capacity-table">
            <table>
              <thead>
                <tr>
                  <th>{t('exec.person')}</th>
                  <th>{t('exec.usedHours')}</th>
                  <th>{t('exec.capacityHours')}</th>
                  <th>{t('exec.utilisation')}</th>
                  <th style={{ width: 120 }}></th>
                </tr>
              </thead>
              <tbody>
                {people.map((p) => (
                  <tr key={p.person_id}>
                    <td>{p.person_id}</td>
                    <td>{fmtHours(p.used_hours, locale)}</td>
                    <td>{fmtHours(p.capacity_hours, locale)}</td>
                    <td>{fmtPct(p.utilisation_pct)}</td>
                    <td>
                      <CapacityBar pct={p.utilisation_pct} aria-label={`${p.person_id} utilisation`} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  )
}

// 4. Cash Risk
function cashStatusBadgeValue(status: string): string {
  switch (status) {
    case 'CASH_SAFE': return 'CASH_SAFE'
    case 'BUFFER_BREACH': return 'BUFFER_BREACH'
    case 'NEGATIVE_CASH': return 'NEGATIVE_CASH'
    default: return 'CASH_AT_RISK'
  }
}

function CashScenarioCard({
  scenario,
  currency,
  locale,
}: {
  scenario: ScenarioCashSummary
  currency: string
  locale: string
}) {
  const { t } = useTranslation()
  return (
    <div className="cash-scenario-row" data-testid={`cash-scenario-${scenario.scenario}`}>
      <div className="cash-scenario-row__header">
        <span className="cash-scenario-row__label">{scenario.scenario}</span>
        <StatusBadge status={cashStatusBadgeValue(scenario.status)} testId={`badge-cash-${scenario.scenario}`} />
      </div>
      <div className="cash-scenario-row__amount">{fmtMoney(scenario.ending_cash_jpy, currency, locale)}</div>
      <div style={{ marginTop: 6, fontSize: 12, color: 'var(--slate-500)' }}>
        {t('exec.endingCash')}
        {scenario.days_below_buffer > 0 && (
          <> · {t('exec.daysBelow', { n: scenario.days_below_buffer })}</>
        )}
      </div>
    </div>
  )
}

function CashRiskSection({
  decision,
  baseline,
  locale,
}: {
  decision: FinalDecisionResult
  baseline: BaselineSummary
  locale: string
}) {
  const { t } = useTranslation()
  const cash = decision.cash_summary
  const s = decision.executive_summary
  const currency = baseline.currency

  return (
    <section className="exec-section" aria-labelledby="section-cash-risk">
      <SectionHeader title={t('exec.cashRisk')} />
      <div className="exec-grid-3">
        {cash.scenarios.map((sc) => (
          <CashScenarioCard key={sc.scenario} scenario={sc} currency={currency} locale={locale} />
        ))}
        <div className="cash-meta-row">
          <div className="cash-meta-item">
            <span>{t('exec.minimumBuffer')}</span>
            <strong>{fmtMoney(cash.minimum_buffer_jpy, currency, locale)}</strong>
          </div>
          <div className="cash-meta-item">
            <span>{t('exec.firstBreach')}</span>
            <strong data-testid="cash-first-breach">
              {s.first_buffer_breach_date ? fmtDate(s.first_buffer_breach_date, locale) : t('exec.noBreach')}
            </strong>
          </div>
          {s.minimum_cash_date && (
            <div className="cash-meta-item">
              <span>{t('exec.endingCash')} (min date)</span>
              <strong>{fmtDate(s.minimum_cash_date, locale)}</strong>
            </div>
          )}
        </div>
      </div>
    </section>
  )
}

// 5. Key Findings
function FindingRow({ rec, variant }: { rec: ExplanationRecord; variant: 'risk' | 'strength' }) {
  return (
    <div className="finding-row" data-testid={`finding-${rec.code}`}>
      <div className={`finding-row__dot finding-row__dot--${variant}`} />
      <div>
        <div className="finding-code">{rec.code}</div>
        <div className="finding-meta">
          {rec.severity} · {rec.source_phase}
          {rec.source_id && ` · ${rec.source_id}`}
        </div>
      </div>
    </div>
  )
}

function KeyFindingsSection({ decision }: { decision: FinalDecisionResult }) {
  const { t } = useTranslation()
  const s = decision.executive_summary

  // Map risk codes to matching explanation records for detail; fall back to code-only display
  const riskRecords: ExplanationRecord[] = s.major_risks.map((code) => {
    const match = decision.explanation_records.find((r) => r.code === code)
    return match ?? { code, severity: 'WARNING', source_phase: 'FINAL_VALIDATION', source_id: null, action_id: null, evidence: {} }
  })

  const strengthRecords: ExplanationRecord[] = s.major_strengths.map((code) => {
    const match = decision.explanation_records.find((r) => r.code === code)
    return match ?? { code, severity: 'INFO', source_phase: 'FINAL_VALIDATION', source_id: null, action_id: null, evidence: {} }
  })

  return (
    <section className="exec-section" aria-labelledby="section-findings">
      <SectionHeader title={t('exec.keyFindings')} />
      <div className="exec-grid-2">
        <div>
          <div style={{ marginBottom: 10 }}>
            <span className="eyebrow">{t('exec.majorRisks')}</span>
          </div>
          <div className="finding-list">
            {riskRecords.length === 0 ? (
              <p className="findings-empty">{t('exec.noRisks')}</p>
            ) : (
              riskRecords.map((r, i) => <FindingRow key={`${r.code}-${i}`} rec={r} variant="risk" />)
            )}
          </div>
        </div>
        <div>
          <div style={{ marginBottom: 10 }}>
            <span className="eyebrow">{t('exec.majorStrengths')}</span>
          </div>
          <div className="finding-list">
            {strengthRecords.length === 0 ? (
              <p className="findings-empty">{t('exec.noStrengths')}</p>
            ) : (
              strengthRecords.map((r, i) => <FindingRow key={`${r.code}-${i}`} rec={r} variant="strength" />)
            )}
          </div>
        </div>
      </div>
    </section>
  )
}

// 6. Future Receipts
function ReceiptRow({
  receipt,
  currency,
  locale,
}: {
  receipt: FutureReceiptSummary
  currency: string
  locale: string
}) {
  return (
    <tr data-testid={`receipt-${receipt.source_id}`}>
      <td>{receipt.source_id}</td>
      <td>{receipt.event_type}</td>
      <td className="receipt-table__amount">{fmtMoney(receipt.expected_amount_jpy, currency, locale)}</td>
      <td>{fmtDate(receipt.date, locale)}</td>
    </tr>
  )
}

function FutureReceiptsSection({
  decision,
  baseline,
  locale,
}: {
  decision: FinalDecisionResult
  baseline: BaselineSummary
  locale: string
}) {
  const { t } = useTranslation()
  const receipts = decision.cash_summary.future_receipts
  const currency = baseline.currency

  return (
    <section className="exec-section" aria-labelledby="section-receipts">
      <SectionHeader title={t('exec.futureReceipts')} />
      {receipts.length === 0 ? (
        <p className="findings-empty">{t('exec.noReceipts')}</p>
      ) : (
        <div className="receipt-table-wrap">
          <table className="receipt-table">
            <thead>
              <tr>
                <th>{t('exec.receiptSource')}</th>
                <th>{t('exec.source')}</th>
                <th className="receipt-table__amount">{t('exec.receiptAmount')}</th>
                <th>{t('exec.receiptDate')}</th>
              </tr>
            </thead>
            <tbody>
              {receipts.map((r) => (
                <ReceiptRow key={`${r.source_id}-${r.date}`} receipt={r} currency={currency} locale={locale} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

// ─── Main page ─────────────────────────────────────────────────────────────

export function DashboardPage() {
  const { t, i18n } = useTranslation()
  const [reloadKey, setReloadKey] = useState(0)
  const [state, setState] = useState<DashboardState>({ status: 'loading' })

  useEffect(() => {
    let current = true
    setState({ status: 'loading' })
    void Promise.all([systemApi.health(), systemApi.baselineSummary(), decisionApi.finalDecision()])
      .then(([health, baseline, decision]) => {
        if (current) setState({ status: 'ready', health, baseline, decision })
      })
      .catch((error: unknown) => {
        if (current)
          setState({ status: 'error', message: error instanceof Error ? error.message : 'Unknown error' })
      })
    return () => { current = false }
  }, [reloadKey])

  if (state.status === 'loading') return <LoadingState />
  if (state.status === 'error')
    return <ErrorState message={state.message} onRetry={() => setReloadKey((v) => v + 1)} />

  const { health, baseline, decision } = state
  const locale = i18n.resolvedLanguage ?? 'en'

  return (
    <div>
      {/* Page header — baseline metadata strip (kept from Phase 5A) */}
      <div className="page-heading">
        <span className="eyebrow">{t('dashboard.eyebrow')}</span>
        <h1>{t('dashboard.title')}</h1>
        <p>{t('dashboard.description')}</p>
      </div>

      {/* Baseline metadata row */}
      <div className="metric-grid" style={{ marginBottom: 42 }}>
        <article className="metric-card">
          <span>{t('dashboard.backend')}</span>
          <strong className="text-success">{health.status === 'ok' ? t('dashboard.connected') : health.status}</strong>
          {health.status === 'ok' && <i className="connection-indicator" />}
        </article>
        <article className="metric-card">
          <span>{t('dashboard.people')}</span>
          <strong>{baseline.people_count.toLocaleString(locale)}</strong>
        </article>
        <article className="metric-card">
          <span>{t('dashboard.workItems')}</span>
          <strong>{baseline.work_item_count.toLocaleString(locale)}</strong>
        </article>
        <article className="metric-card metric-card--wide">
          <span>{t('dashboard.horizon')}</span>
          <strong>
            {new Intl.DateTimeFormat(locale, { year: 'numeric', month: 'short', day: 'numeric' }).format(
              new Date(`${baseline.planning_start}T00:00:00`),
            )}{' '}
            –{' '}
            {new Intl.DateTimeFormat(locale, { year: 'numeric', month: 'short', day: 'numeric' }).format(
              new Date(`${baseline.planning_end}T00:00:00`),
            )}
          </strong>
        </article>
      </div>

      {/* Phase 5B sections */}
      <DecisionStatusSection decision={decision} />
      <PortfolioSection decision={decision} />
      <CapacitySection decision={decision} locale={locale} />
      <CashRiskSection decision={decision} baseline={baseline} locale={locale} />
      <KeyFindingsSection decision={decision} />
      <FutureReceiptsSection decision={decision} baseline={baseline} locale={locale} />
    </div>
  )
}
