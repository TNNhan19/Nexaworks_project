import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { scenarioApi } from '../api/endpoints'
import type { NumericDelta, RunComparison, Scenario, ScenarioRun, SetDelta } from '../api/types'
import { EmptyResult, ManagementSection, ManagerError, ManagerLoading, ManagerStatus, Money, PageIntro } from '../components/business/BusinessUI'
import { managerCopy } from '../utils/managerCopy'
import { formatDateTime, reasonLabel } from '../utils/presentation'
import { useWorkflow } from '../workflow/WorkflowContext'
import { WorkflowGate } from '../workflow/WorkflowUI'

interface RunOption { run: ScenarioRun; scenario: Scenario }
function DeltaList({ delta }: { delta: SetDelta }) { const { i18n } = useTranslation(); const c = managerCopy(i18n.resolvedLanguage).comparison; return <div className='business-delta-list'><div><strong>{c.added}</strong>{delta.added.length ? delta.added.map((id) => <span className='delta-chip delta-chip--added' key={id}>+ {id}</span>) : <span className='muted'>—</span>}</div><div><strong>{c.removed}</strong>{delta.removed.length ? delta.removed.map((id) => <span className='delta-chip delta-chip--removed' key={id}>− {id}</span>) : <span className='muted'>—</span>}</div></div> }
function deltaText(item: NumericDelta, language?: string, currency = false) { const c = managerCopy(language).comparison; if (item.delta == null || item.delta === 0) return c.noChange; const sign = item.delta > 0 ? '+' : ''; return currency ? `${sign}${new Intl.NumberFormat(language ?? 'en', { style: 'currency', currency: 'JPY', maximumFractionDigits: 0 }).format(item.delta)}` : `${sign}${item.delta.toLocaleString(language ?? 'en', { maximumFractionDigits: 1 })}` }
function changeLabel(delta: number | null, language?: string) { const c = managerCopy(language).comparison; if (!delta) return c.noChange; return delta > 0 ? c.improved : c.worsened }

function ComparisonWorkspace() {
  const { i18n } = useTranslation(); const c = managerCopy(i18n.resolvedLanguage).comparison; const [options, setOptions] = useState<RunOption[]>([]); const [runA, setRunA] = useState(''); const [runB, setRunB] = useState(''); const [comparison, setComparison] = useState<RunComparison | null>(null); const [loading, setLoading] = useState(true); const [comparing, setComparing] = useState(false); const [error, setError] = useState(false); const [reloadKey, setReloadKey] = useState(0)
  useEffect(() => { let current = true; setLoading(true); setError(false); void scenarioApi.list().then(async (scenarios) => { const histories = await Promise.all(scenarios.map(async (scenario) => ({ scenario, runs: await scenarioApi.runs(scenario.id) }))); if (!current) return; const loaded = histories.flatMap(({ scenario, runs }) => runs.filter((run) => run.status === 'COMPLETED').map((run) => ({ run, scenario }))); setOptions(loaded); setRunA((value) => value || loaded[0]?.run.run_id || ''); setRunB((value) => value || loaded[1]?.run.run_id || loaded[0]?.run.run_id || ''); setLoading(false) }).catch(() => { if (current) { setError(true); setLoading(false) } }); return () => { current = false } }, [reloadKey])
  const optionMap = useMemo(() => new Map(options.map((option) => [option.run.run_id, option])), [options])
  async function compare() { if (!runA || !runB) return; setComparing(true); setError(false); try { setComparison(await scenarioApi.compareRuns(runA, runB)) } catch { setError(true); setComparison(null) } finally { setComparing(false) } }
  if (loading) return <ManagerLoading />; if (options.length === 0 && !error) return <EmptyResult />; if (error && !options.length) return <ManagerError onRetry={() => setReloadKey((value) => value + 1)} />
  const a = optionMap.get(runA); const b = optionMap.get(runB); const locale = i18n.resolvedLanguage ?? 'en'
  return <div><PageIntro eyebrow={c.eyebrow} title={c.title} description={c.description} /><section className='comparison-picker manager-comparison-picker'><label><span>{c.baseline}</span><select value={runA} onChange={(event) => { setRunA(event.target.value); setComparison(null) }}>{options.map(({ run, scenario }) => <option value={run.run_id} key={run.run_id}>{scenario.name} · {formatDateTime(run.timestamp, locale)}</option>)}</select></label><span className='comparison-vs' aria-hidden='true'>VS</span><label><span>{c.scenario}</span><select value={runB} onChange={(event) => { setRunB(event.target.value); setComparison(null) }}>{options.map(({ run, scenario }) => <option value={run.run_id} key={run.run_id}>{scenario.name} · {formatDateTime(run.timestamp, locale)}</option>)}</select></label><button className='button' disabled={comparing} onClick={() => void compare()}>{comparing ? c.comparing : c.compare}</button></section>{runA === runB && <p className='same-run-note'>{c.same}</p>}{error && <div className='form-errors' role='alert'><p>{managerCopy(i18n.resolvedLanguage).common.unavailable}</p><button className='button button--ghost' onClick={() => void compare()}>{managerCopy(i18n.resolvedLanguage).common.retry}</button></div>}
    {comparison && a && b && <div className='comparison-results'><div className='comparison-identities'><article><span>{c.baseline}</span><h2>{a.scenario.name}</h2><p>{formatDateTime(a.run.timestamp, locale)}</p><code>{a.run.run_id}</code></article><span className='comparison-arrow' aria-hidden='true'>→</span><article><span>{c.scenario}</span><h2>{b.scenario.name}</h2><p>{formatDateTime(b.run.timestamp, locale)}</p><code>{b.run.run_id}</code></article></div>
      <ManagementSection title={c.conclusion}><div className='comparison-story-list'>
        <article><div><span>{c.cash}</span><strong><Money value={comparison.cash.expected_ending_cash_jpy.run_a} compact={false} /> <i>→</i> <Money value={comparison.cash.expected_ending_cash_jpy.run_b} compact={false} /></strong></div><span className={`change-pill change-pill--${comparison.cash.expected_ending_cash_jpy.delta && comparison.cash.expected_ending_cash_jpy.delta > 0 ? 'positive' : comparison.cash.expected_ending_cash_jpy.delta && comparison.cash.expected_ending_cash_jpy.delta < 0 ? 'negative' : 'neutral'}`}>{changeLabel(comparison.cash.expected_ending_cash_jpy.delta, i18n.resolvedLanguage)} · {deltaText(comparison.cash.expected_ending_cash_jpy, i18n.resolvedLanguage, true)}</span></article>
        <article><div><span>{c.financial}</span><strong><ManagerStatus status={comparison.status_transition.financial_status.from} /> <i>→</i> <ManagerStatus status={comparison.status_transition.financial_status.to} /></strong></div></article>
        <article><div><span>{c.capacity}</span><strong>{comparison.capacity.used_hours.run_a?.toLocaleString(locale)} h <i>→</i> {comparison.capacity.used_hours.run_b?.toLocaleString(locale)} h</strong></div><span className='change-pill'>{deltaText(comparison.capacity.used_hours, i18n.resolvedLanguage)}</span></article>
        <article><div><span>{c.selected}</span><strong>{comparison.selected.added.length || comparison.selected.removed.length ? c.change : c.noChange}</strong></div></article>
      </div></ManagementSection>
      <ManagementSection title={c.workChanges}><div className='comparison-delta-grid'><article><h3>{c.selected}</h3><DeltaList delta={comparison.selected} /></article><article><h3>{c.delayed}</h3><DeltaList delta={comparison.delayed} /></article><article><h3>{c.noBid}</h3><DeltaList delta={comparison.no_bid} /></article></div></ManagementSection>
      <ManagementSection title={c.risksRemoved}><div className='risk-change-grid'><article><h3>{c.risksRemoved}</h3>{comparison.major_risks.removed.length ? comparison.major_risks.removed.map((code) => <div className='translated-code' key={code}><strong>{reasonLabel(code, i18n.resolvedLanguage)}</strong><code>{code}</code></div>) : <p className='muted'>{c.noChange}</p>}</article><article><h3>{c.risksRemaining}</h3>{comparison.major_risks.added.length ? comparison.major_risks.added.map((code) => <div className='translated-code' key={code}><strong>{reasonLabel(code, i18n.resolvedLanguage)}</strong><code>{code}</code></div>) : <p className='muted'>{c.noChange}</p>}</article></div></ManagementSection>
      <details className='audit-details audit-details--page'><summary>{managerCopy(i18n.resolvedLanguage).common.details}</summary><div className='audit-grid'>{Object.entries(comparison.status_transition).map(([key, value]) => <code key={key}>{key}: {value.from} → {value.to}</code>)}<code>{comparison.buffer_breach.change}</code>{comparison.major_strengths.added.map((code) => <code key={`strength-added-${code}`}>+ {code}</code>)}{comparison.major_strengths.removed.map((code) => <code key={`strength-removed-${code}`}>− {code}</code>)}</div></details>
    </div>}
  </div>
}





export function ComparisonPage() {
  const workflow = useWorkflow()
  if (!workflow.catalog) return <WorkflowGate kind='data' />
  if (!workflow.generation) return <WorkflowGate kind='plan' />
  if (workflow.source !== 'sample') return <WorkflowGate kind='sample' />
  return <ComparisonWorkspace />
}
