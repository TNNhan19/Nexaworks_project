import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { systemApi } from '../api/endpoints'
import type { BaselineSummary, HealthResponse } from '../api/types'
import { ErrorState, LoadingState } from '../components/system/AsyncState'

type DashboardState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; health: HealthResponse; baseline: BaselineSummary }

function formatDate(value: string, locale: string) {
  return new Intl.DateTimeFormat(locale, { year: 'numeric', month: 'short', day: 'numeric' })
    .format(new Date(`${value}T00:00:00`))
}

function formatMoney(value: number, currency: string, locale: string) {
  return new Intl.NumberFormat(locale, {
    style: 'currency', currency, maximumFractionDigits: 0,
  }).format(value)
}

export function DashboardPage() {
  const { t, i18n } = useTranslation()
  const [reloadKey, setReloadKey] = useState(0)
  const [state, setState] = useState<DashboardState>({ status: 'loading' })

  useEffect(() => {
    let current = true
    setState({ status: 'loading' })
    void Promise.all([systemApi.health(), systemApi.baselineSummary()])
      .then(([health, baseline]) => { if (current) setState({ status: 'ready', health, baseline }) })
      .catch((error: unknown) => {
        if (current) setState({ status: 'error', message: error instanceof Error ? error.message : 'Unknown error' })
      })
    return () => { current = false }
  }, [reloadKey])

  if (state.status === 'loading') return <LoadingState />
  if (state.status === 'error') return <ErrorState message={state.message} onRetry={() => setReloadKey((value) => value + 1)} />

  const { baseline, health } = state
  const locale = i18n.resolvedLanguage ?? 'en'
  const metrics = [
    { label: t('dashboard.backend'), value: health.status === 'ok' ? t('dashboard.connected') : health.status, tone: 'success' },
    { label: t('dashboard.people'), value: baseline.people_count.toLocaleString(locale) },
    { label: t('dashboard.workItems'), value: baseline.work_item_count.toLocaleString(locale) },
    { label: t('dashboard.horizon'), value: `${formatDate(baseline.planning_start, locale)} – ${formatDate(baseline.planning_end, locale)}`, wide: true },
  ]
  return (
    <section>
      <div className="page-heading"><span className="eyebrow">{t('dashboard.eyebrow')}</span><h1>{t('dashboard.title')}</h1><p>{t('dashboard.description')}</p></div>
      <div className="metric-grid">
        {metrics.map((metric) => <article className={`metric-card${metric.wide ? ' metric-card--wide' : ''}`} key={metric.label}><span>{metric.label}</span><strong className={metric.tone === 'success' ? 'text-success' : ''}>{metric.value}</strong>{metric.tone === 'success' && <i className="connection-indicator" />}</article>)}
      </div>
      <div className="section-heading"><div><span className="eyebrow">{t('footer.baseline')}</span><h2>{baseline.dataset_id}</h2></div><span className="version-chip">{t('footer.version', { version: baseline.dataset_version })}</span></div>
      <div className="detail-grid">
        <article className="detail-card"><span>{t('dashboard.startingCash')}</span><strong>{formatMoney(baseline.starting_cash_jpy, baseline.currency, locale)}</strong></article>
        <article className="detail-card"><span>{t('dashboard.buffer')}</span><strong>{formatMoney(baseline.minimum_cash_buffer_jpy, baseline.currency, locale)}</strong></article>
        <article className="detail-card"><span>{t('dashboard.capacity')}</span><strong>{t('dashboard.hours', { value: baseline.total_people_capacity_hours.toLocaleString(locale) })}</strong></article>
        <article className="detail-card"><span>{t('dashboard.mandatory')}</span><strong>{baseline.mandatory_work_count.toLocaleString(locale)}</strong></article>
      </div>
    </section>
  )
}
