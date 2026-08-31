import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { ApiClientError } from '../api/client'
import { baselineCatalogApi, scenarioApi } from '../api/endpoints'
import type { BaselineCatalog, Scenario, ScenarioInput, ScenarioRun } from '../api/types'
import { StatusBadge } from '../components/dashboard/StatusBadge'
import { ErrorState, LoadingState } from '../components/system/AsyncState'

type NumericField = number | ''
type OverrideRow = { id: string; value: NumericField }
interface FormState {
  name: string; description: string; status: 'ACTIVE' | 'INACTIVE'
  startingCash: NumericField; fixedOutflow: NumericField; minimumBuffer: NumericField
  people: OverrideRow[]; workItems: OverrideRow[]; commercialOptions: OverrideRow[]
}
const emptyCatalog: BaselineCatalog = { people: [], workItems: [], commercialOptions: [] }
const emptyForm = (): FormState => ({
  name: '', description: '', status: 'ACTIVE', startingCash: '', fixedOutflow: '',
  minimumBuffer: '', people: [], workItems: [], commercialOptions: [],
})
function fromScenario(s: Scenario): FormState {
  const company = s.overrides.company
  return {
    name: s.name, description: s.description, status: s.status,
    startingCash: company?.starting_cash_jpy ?? '',
    fixedOutflow: company?.fixed_cash_outflow_jpy ?? '',
    minimumBuffer: company?.minimum_cash_buffer_jpy ?? '',
    people: s.overrides.people.map((x) => ({ id: x.person_id, value: x.capacity_hours ?? '' })),
    workItems: s.overrides.work_items.map((x) => ({ id: x.work_item_id, value: x.required_hours ?? '' })),
    commercialOptions: s.overrides.commercial_options.map((x) => ({ id: x.option_id, value: x.estimated_win_probability ?? '' })),
  }
}
function toInput(form: FormState): ScenarioInput {
  const company = {
    ...(form.startingCash !== '' ? { starting_cash_jpy: form.startingCash } : {}),
    ...(form.fixedOutflow !== '' ? { fixed_cash_outflow_jpy: form.fixedOutflow } : {}),
    ...(form.minimumBuffer !== '' ? { minimum_cash_buffer_jpy: form.minimumBuffer } : {}),
  }
  return {
    name: form.name.trim(), description: form.description.trim(), status: form.status,
    overrides: {
      ...(Object.keys(company).length ? { company } : {}),
      people: form.people.map((x) => ({ person_id: x.id, capacity_hours: x.value as number })),
      work_items: form.workItems.map((x) => ({ work_item_id: x.id, required_hours: x.value as number })),
      commercial_options: form.commercialOptions.map((x) => ({ option_id: x.id, estimated_win_probability: x.value as number })),
    },
  }
}
function validate(form: FormState, catalog: BaselineCatalog, t: (key: string) => string): string[] {
  const errors: string[] = []
  if (!form.name.trim()) errors.push(t('scenarios.validation.name'))
  if ([form.startingCash, form.fixedOutflow, form.minimumBuffer].some((v) => v !== '' && v < 0)) errors.push(t('scenarios.validation.nonNegative'))
  const groups: Array<[OverrideRow[], string[]]> = [[form.people, catalog.people], [form.workItems, catalog.workItems], [form.commercialOptions, catalog.commercialOptions]]
  for (const [rows, ids] of groups) {
    if (rows.some((x) => !x.id || !ids.includes(x.id))) errors.push(t('scenarios.validation.baselineId'))
    if (new Set(rows.map((x) => x.id)).size !== rows.length) errors.push(t('scenarios.validation.duplicate'))
    if (rows.some((x) => x.value === '' || x.value < 0)) errors.push(t('scenarios.validation.nonNegative'))
  }
  if (form.commercialOptions.some((x) => x.value !== '' && x.value > 1)) errors.push(t('scenarios.validation.probability'))
  return [...new Set(errors)]
}
function errorMessages(error: unknown): string[] {
  if (error instanceof ApiClientError) return [error.message, ...error.details]
  return [error instanceof Error ? error.message : 'Unknown error']
}
function OverrideRows({ label, valueLabel, rows, ids, probability = false, onChange }: {
  label: string; valueLabel: string; rows: OverrideRow[]; ids: string[]; probability?: boolean
  onChange: (rows: OverrideRow[]) => void
}) {
  const { t } = useTranslation()
  const available = ids.filter((id) => !rows.some((row) => row.id === id))
  const changeId = (index: number, id: string) => onChange(rows.map((row, i) => i === index ? { ...row, id } : row))
  const changeValue = (index: number, raw: string) => onChange(rows.map((row, i) => i === index ? { ...row, value: raw === '' ? '' : Number(raw) } : row))
  return <fieldset className='override-group'>
    <legend>{label}</legend>
    {rows.map((row, index) => <div className='override-row' key={`${row.id}-${index}`}>
      <label><span>{t('scenarios.target')}</span>
        <select aria-label={`${label} ${t('scenarios.target')}`} value={row.id} onChange={(e) => changeId(index, e.target.value)}>
          <option value=''>{t('scenarios.selectId')}</option>
          {ids.map((id) => <option key={id} value={id}>{id}</option>)}
        </select>
      </label>
      <label><span>{valueLabel}</span>
        <input aria-label={`${label} ${valueLabel}`} type='number' min='0' max={probability ? '1' : undefined} step={probability ? '0.01' : '0.1'} value={row.value} onChange={(e) => changeValue(index, e.target.value)} />
      </label>
      <button type='button' className='button button--ghost' onClick={() => onChange(rows.filter((_, i) => i !== index))}>{t('scenarios.remove')}</button>
    </div>)}
    <button type='button' className='button button--secondary' disabled={!available.length} onClick={() => onChange([...rows, { id: available[0] ?? '', value: '' }])}>{t('scenarios.addOverride')}</button>
  </fieldset>
}
function ScenarioEditor({ initial, catalog, busy, onCancel, onSave }: {
  initial: FormState; catalog: BaselineCatalog; busy: boolean
  onCancel: () => void; onSave: (form: FormState) => Promise<void>
}) {
  const { t } = useTranslation()
  const [form, setForm] = useState(initial)
  const [errors, setErrors] = useState<string[]>([])
  async function submit(event: React.FormEvent) {
    event.preventDefault()
    const found = validate(form, catalog, t)
    if (found.length) { setErrors(found); return }
    setErrors([])
    try { await onSave(form) } catch (error) { setErrors(errorMessages(error)) }
  }
  const numeric = (key: 'startingCash' | 'fixedOutflow' | 'minimumBuffer', raw: string) =>
    setForm({ ...form, [key]: raw === '' ? '' : Number(raw) })
  return <form className='scenario-editor' onSubmit={(event) => void submit(event)} noValidate>
    <div className='editor-heading'>
      <div><span className='eyebrow'>{t('scenarios.overrideEditor')}</span><h2>{t('scenarios.details')}</h2></div>
      <button type='button' className='button button--ghost' onClick={onCancel}>{t('scenarios.cancel')}</button>
    </div>
    {errors.length > 0 && <div className='form-errors' role='alert'>
      <strong>{t('scenarios.validation.title')}</strong>
      <ul>{errors.map((error) => <li key={error}>{error}</li>)}</ul>
    </div>}
    <div className='form-grid'>
      <label><span>{t('scenarios.name')}</span><input value={form.name} maxLength={200} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label>
      <label><span>{t('scenarios.status')}</span><select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value as FormState['status'] })}><option value='ACTIVE'>ACTIVE</option><option value='INACTIVE'>INACTIVE</option></select></label>
      <label className='form-grid__wide'><span>{t('scenarios.description')}</span><textarea value={form.description} maxLength={2000} rows={3} onChange={(e) => setForm({ ...form, description: e.target.value })} /></label>
    </div>
    <h3>{t('scenarios.companyOverrides')}</h3>
    <div className='form-grid form-grid--three'>
      <label><span>{t('scenarios.startingCash')}</span><input type='number' min='0' value={form.startingCash} onChange={(e) => numeric('startingCash', e.target.value)} /></label>
      <label><span>{t('scenarios.fixedOutflow')}</span><input type='number' min='0' value={form.fixedOutflow} onChange={(e) => numeric('fixedOutflow', e.target.value)} /></label>
      <label><span>{t('scenarios.minimumBuffer')}</span><input type='number' min='0' value={form.minimumBuffer} onChange={(e) => numeric('minimumBuffer', e.target.value)} /></label>
    </div>
    <OverrideRows label={t('scenarios.personCapacity')} valueLabel={t('scenarios.hours')} rows={form.people} ids={catalog.people} onChange={(people) => setForm({ ...form, people })} />
    <OverrideRows label={t('scenarios.workHours')} valueLabel={t('scenarios.hours')} rows={form.workItems} ids={catalog.workItems} onChange={(workItems) => setForm({ ...form, workItems })} />
    <OverrideRows label={t('scenarios.winProbability')} valueLabel={t('scenarios.probability')} rows={form.commercialOptions} ids={catalog.commercialOptions} probability onChange={(commercialOptions) => setForm({ ...form, commercialOptions })} />
    <div className='form-actions'><button className='button' disabled={busy}>{busy ? t('scenarios.saving') : t('scenarios.save')}</button></div>
  </form>
}
function RunSummary({ run }: { run: ScenarioRun }) {
  const { t, i18n } = useTranslation()
  const decision = run.final_decision
  return <article className='run-row'>
    <div><strong>{new Intl.DateTimeFormat(i18n.resolvedLanguage, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(run.timestamp))}</strong><span className='run-id'>{run.run_id}</span></div>
    {run.status === 'COMPLETED' && decision ? <div className='run-statuses'>
      <StatusBadge status={decision.overall_status} />
      <StatusBadge status={decision.operational_status} />
      <StatusBadge status={decision.financial_status} />
    </div> : <span className='error-text'>{run.error?.message ?? t('scenarios.runFailed')}</span>}
    <Link className='button button--secondary' to={`/plan?run_id=${encodeURIComponent(run.run_id)}`}>{t('scenarios.openRun')}</Link>
  </article>
}
export function ScenariosPage() {
  const { t } = useTranslation()
  const [scenarios, setScenarios] = useState<Scenario[]>([])
  const [catalog, setCatalog] = useState<BaselineCatalog>(emptyCatalog)
  const [runs, setRuns] = useState<Record<string, ScenarioRun[]>>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [reloadKey, setReloadKey] = useState(0)
  const [editing, setEditing] = useState<Scenario | 'new' | null>(null)
  const [busy, setBusy] = useState('')
  const [deleteId, setDeleteId] = useState<string | null>(null)
  const [actionError, setActionError] = useState('')
  useEffect(() => {
    let current = true
    setLoading(true)
    void Promise.all([scenarioApi.list(), baselineCatalogApi.load()])
      .then(async ([items, loadedCatalog]) => {
        const histories = await Promise.all(items.map(async (item) => [item.id, await scenarioApi.runs(item.id)] as const))
        if (current) {
          setScenarios(items); setCatalog(loadedCatalog); setRuns(Object.fromEntries(histories))
          setError(''); setLoading(false)
        }
      })
      .catch((reason: unknown) => {
        if (current) { setError(errorMessages(reason).join(' ')); setLoading(false) }
      })
    return () => { current = false }
  }, [reloadKey])
  async function save(form: FormState) {
    setBusy('save')
    try {
      if (editing === 'new') {
        const created = await scenarioApi.create(toInput(form))
        setScenarios((items) => [...items, created])
        setRuns((items) => ({ ...items, [created.id]: [] }))
      } else if (editing) {
        const updated = await scenarioApi.update(editing.id, toInput(form))
        setScenarios((items) => items.map((item) => item.id === updated.id ? updated : item))
      }
      setEditing(null)
    } finally { setBusy('') }
  }
  async function remove(id: string) {
    setBusy(id); setActionError('')
    try {
      await scenarioApi.delete(id)
      setScenarios((items) => items.filter((item) => item.id !== id))
      setDeleteId(null)
    } catch (reason) { setActionError(errorMessages(reason).join(' ')) }
    finally { setBusy('') }
  }
  async function runScenario(id: string) {
    setBusy(id); setActionError('')
    try {
      const run = await scenarioApi.run(id)
      setRuns((items) => ({ ...items, [id]: [...(items[id] ?? []), run] }))
    } catch (reason) { setActionError(errorMessages(reason).join(' ')) }
    finally { setBusy('') }
  }
  if (loading) return <div><h1>{t('scenarios.title')}</h1><LoadingState /></div>
  if (error) return <div><h1>{t('scenarios.title')}</h1><ErrorState message={error} onRetry={() => setReloadKey((value) => value + 1)} /></div>
  return <div>
    <div className='page-heading page-heading--actions'>
      <div><span className='eyebrow'>{t('scenarios.eyebrow')}</span><h1>{t('scenarios.title')}</h1><p>{t('scenarios.descriptionText')}</p></div>
      <button className='button' onClick={() => setEditing('new')}>{t('scenarios.create')}</button>
    </div>
    {actionError && <div className='form-errors' role='alert'>{actionError}</div>}
    {editing && <ScenarioEditor key={editing === 'new' ? 'new' : editing.id} initial={editing === 'new' ? emptyForm() : fromScenario(editing)} catalog={catalog} busy={busy === 'save'} onCancel={() => setEditing(null)} onSave={save} />}
    {!editing && scenarios.length === 0 && <div className='content-empty'><h2>{t('scenarios.emptyTitle')}</h2><p>{t('scenarios.emptyText')}</p></div>}
    <div className='scenario-list'>
      {scenarios.map((scenario) => <article className='scenario-card' key={scenario.id}>
        <div className='scenario-card__heading'>
          <div><span className='eyebrow'>{scenario.status}</span><h2>{scenario.name}</h2><p>{scenario.description || t('scenarios.noDescription')}</p></div>
          <div className='scenario-actions'>
            <button className='button button--secondary' onClick={() => setEditing(scenario)}>{t('scenarios.edit')}</button>
            <button className='button' disabled={busy === scenario.id} onClick={() => void runScenario(scenario.id)}>{busy === scenario.id ? t('scenarios.running') : t('scenarios.run')}</button>
            <button className='button button--danger' onClick={() => setDeleteId(scenario.id)}>{t('scenarios.delete')}</button>
          </div>
        </div>
        {deleteId === scenario.id && <div className='delete-confirm' role='alertdialog' aria-label={t('scenarios.confirmDelete')}>
          <span>{t('scenarios.confirmDelete')}</span>
          <button className='button button--danger' disabled={busy === scenario.id} onClick={() => void remove(scenario.id)}>{t('scenarios.confirm')}</button>
          <button className='button button--ghost' onClick={() => setDeleteId(null)}>{t('scenarios.cancel')}</button>
        </div>}
        <section className='run-history' aria-label={t('scenarios.history')}>
          <h3>{t('scenarios.history')}</h3>
          {(runs[scenario.id] ?? []).length === 0
            ? <p className='muted'>{t('scenarios.noRuns')}</p>
            : [...runs[scenario.id]].reverse().map((run) => <RunSummary key={run.run_id} run={run} />)}
        </section>
      </article>)}
    </div>
  </div>
}
