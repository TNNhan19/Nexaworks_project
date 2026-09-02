import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { managerCopy } from '../../utils/managerCopy'
import { formatDateTime, formatMoneyCompact, formatMoneyExact, statusLabel, statusTone } from '../../utils/presentation'

export function PageIntro({ eyebrow, title, description, action }: { eyebrow: string; title: string; description: string; action?: ReactNode }) {
  return <header className='manager-page-header'><div><span className='eyebrow'>{eyebrow}</span><h1>{title}</h1><p>{description}</p></div>{action && <div className='manager-page-header__action'>{action}</div>}</header>
}

export function ConclusionCard({ eyebrow, title, tone, evidence, status }: { eyebrow: string; title: string; tone: 'positive' | 'warning' | 'critical' | 'neutral'; evidence?: ReactNode; status?: string }) {
  const { i18n } = useTranslation()
  return <section className={`conclusion-card conclusion-card--${tone}`} data-testid='management-conclusion'><div className='conclusion-card__icon' aria-hidden='true'>{tone === 'positive' ? '✓' : tone === 'neutral' ? 'i' : '!'}</div><div><span className='conclusion-card__eyebrow'>{eyebrow}</span><h2>{title}</h2>{evidence && <div className='conclusion-card__evidence'>{evidence}</div>}</div>{status && <span className='audit-code'>{statusLabel(status, i18n.resolvedLanguage)}</span>}</section>
}

export function ManagementSection({ title, description, children, className = '' }: { title: string; description?: string; children: ReactNode; className?: string }) {
  return <section className={`management-section ${className}`}><header className='management-section__header'><div><h2>{title}</h2>{description && <p>{description}</p>}</div></header>{children}</section>
}

export function Money({ value, currency = 'JPY', compact = true }: { value: number | null | undefined; currency?: string; compact?: boolean }) {
  const { i18n } = useTranslation()
  const locale = i18n.resolvedLanguage ?? 'en'
  const exact = formatMoneyExact(value, locale, currency)
  return <span title={exact} aria-label={exact}>{compact ? formatMoneyCompact(value, locale, currency) : exact}</span>
}

export function EmptyResult({ title, text }: { title?: string; text?: string }) {
  const { i18n } = useTranslation()
  const c = managerCopy(i18n.resolvedLanguage).common
  return <div className='content-empty manager-empty'><div className='empty-icon' aria-hidden='true'>↗</div><h1>{title ?? c.noResult}</h1><p>{text ?? c.runFirst}</p><Link className='button' to='/scenarios'>{c.goScenarios}</Link></div>
}

export function ManagerError({ onRetry }: { onRetry: () => void }) {
  const { i18n } = useTranslation()
  const c = managerCopy(i18n.resolvedLanguage).common
  return <div className='async-state async-state--error' role='alert'><div className='error-symbol'>!</div><h2>{c.unavailable}</h2><p>{c.runFirst}</p><button className='button' onClick={onRetry}>{c.retry}</button></div>
}

export function ManagerLoading() {
  const { i18n } = useTranslation()
  return <div className='async-state' role='status'><span className='spinner' /><p>{managerCopy(i18n.resolvedLanguage).common.loading}</p></div>
}

export function RunContext({ runId, timestamp, scenarioName }: { runId: string; timestamp?: string; scenarioName?: string }) {
  const { i18n } = useTranslation()
  const c = managerCopy(i18n.resolvedLanguage).common
  const locale = i18n.resolvedLanguage ?? 'en'
  return <div className='run-context-strip' aria-label={c.runContext}>{scenarioName && <span><strong>{c.scenarioContext}:</strong> {scenarioName}</span>}<span><strong>{c.runContext}:</strong> {timestamp ? formatDateTime(timestamp, locale) : runId}</span><code title={runId}>{runId}</code></div>
}

export function ManagerStatus({ status, showCode = false, testId }: { status: string; showCode?: boolean; testId?: string }) {
  const { i18n } = useTranslation()
  const tone = statusTone(status)
  return <span className={`manager-status manager-status--${tone} status-badge--${tone === 'positive' ? 'feasible' : tone === 'critical' ? (status === 'NEGATIVE_CASH' ? 'negative' : 'infeasible') : tone === 'warning' ? 'at-risk' : 'infeasible'}`} data-testid={testId}><span aria-hidden='true'>{tone === 'positive' ? '✓' : tone === 'critical' ? '!' : '•'}</span>{statusLabel(status, i18n.resolvedLanguage)}{showCode && <code>{status}</code>}</span>
}
