import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { ApiClientError } from '../api/client'
import { baselineCatalogApi, scenarioApi } from '../api/endpoints'
import type { BaselineCatalog, Scenario, ScenarioInput, ScenarioRun } from '../api/types'
import type { PlanningCatalog } from '../workflow/types'
import { ManagerError, ManagerLoading, ManagerStatus, PageIntro } from '../components/business/BusinessUI'
import { managerCopy } from '../utils/managerCopy'
import { formatDateTime } from '../utils/presentation'
import { useWorkflow } from '../workflow/WorkflowContext'
import { WorkflowGate } from '../workflow/WorkflowUI'

type NumericField = number | ''
type OverrideRow = { id: string; value: NumericField }
interface FormState { name: string; description: string; status: 'ACTIVE' | 'INACTIVE'; startingCash: NumericField; fixedOutflow: NumericField; minimumBuffer: NumericField; people: OverrideRow[]; workItems: OverrideRow[]; receiptDays: OverrideRow[]; deferredWorkItems: string[]; commercialOptions: OverrideRow[] }
const emptyCatalog: BaselineCatalog = { people: [], workItems: [], commercialOptions: [] }
const emptyForm = (): FormState => ({ name: '', description: '', status: 'ACTIVE', startingCash: '', fixedOutflow: '', minimumBuffer: '', people: [], workItems: [], receiptDays: [], deferredWorkItems: [], commercialOptions: [] })
function fromScenario(s: Scenario): FormState {
  const company = s.overrides.company
  return {
    name: s.name,
    description: s.description,
    status: s.status,
    startingCash: company?.starting_cash_jpy ?? '',
    fixedOutflow: company?.fixed_cash_outflow_jpy ?? '',
    minimumBuffer: company?.minimum_cash_buffer_jpy ?? '',
    people: s.overrides.people.map((x) => ({ id: x.person_id, value: x.capacity_hours ?? '' })),
    workItems: s.overrides.work_items.filter((x) => x.required_hours != null).map((x) => ({ id: x.work_item_id, value: x.required_hours ?? '' })),
    receiptDays: s.overrides.work_items.filter((x) => x.cash_in_days != null).map((x) => ({ id: x.work_item_id, value: x.cash_in_days ?? '' })),
    deferredWorkItems: s.overrides.deferred_work_item_ids ?? [],
    commercialOptions: s.overrides.commercial_options.map((x) => ({ id: x.option_id, value: x.estimated_win_probability == null ? '' : x.estimated_win_probability * 100 })),
  }
}
function toInput(form: FormState): ScenarioInput {
  const company = {
    ...(form.startingCash !== '' ? { starting_cash_jpy: form.startingCash } : {}),
    ...(form.fixedOutflow !== '' ? { fixed_cash_outflow_jpy: form.fixedOutflow } : {}),
    ...(form.minimumBuffer !== '' ? { minimum_cash_buffer_jpy: form.minimumBuffer } : {}),
  }
  const workOverrides = new Map<string, { work_item_id: string; required_hours?: number; cash_in_days?: number }>()
  for (const row of form.workItems) workOverrides.set(row.id, { ...(workOverrides.get(row.id) ?? { work_item_id: row.id }), required_hours: Number(row.value) })
  for (const row of form.receiptDays) workOverrides.set(row.id, { ...(workOverrides.get(row.id) ?? { work_item_id: row.id }), cash_in_days: Number(row.value) })
  return {
    name: form.name.trim(),
    description: form.description.trim(),
    status: form.status,
    overrides: {
      ...(Object.keys(company).length ? { company } : {}),
      people: form.people.map((x) => ({ person_id: x.id, capacity_hours: Number(x.value) })),
      work_items: [...workOverrides.values()],
      commercial_options: form.commercialOptions.map((x) => ({ option_id: x.id, estimated_win_probability: Number(x.value) / 100 })),
      deferred_work_item_ids: form.deferredWorkItems,
    },
  }
}
function errorsFor(form: FormState, catalog: BaselineCatalog): string[] { const errors: string[] = []; if (!form.name.trim()) errors.push('name'); if ([form.startingCash, form.fixedOutflow, form.minimumBuffer].some((value) => value !== '' && value < 0)) errors.push('value'); const groups: Array<[OverrideRow[], string[]]> = [[form.people, catalog.people], [form.workItems, catalog.workItems], [form.receiptDays, catalog.workItems], [form.commercialOptions, catalog.commercialOptions]]; for (const [rows, ids] of groups) { if (rows.some((row) => !ids.includes(row.id))) errors.push('target'); if (new Set(rows.map((row) => row.id)).size !== rows.length) errors.push('duplicate'); if (rows.some((row) => row.value === '' || row.value < 0)) errors.push('value') } if (form.commercialOptions.some((row) => row.value !== '' && row.value > 100)) errors.push('probability'); if (form.deferredWorkItems.some((id) => !catalog.workItems.includes(id))) errors.push('target'); if (new Set(form.deferredWorkItems).size !== form.deferredWorkItems.length) errors.push('duplicate'); return [...new Set(errors)] }
function apiErrors(error: unknown) { return error instanceof ApiClientError ? [error.message, ...error.details] : [error instanceof Error ? error.message : 'Unknown error'] }
function validationMessage(code: string, language?: string) { const lang = language?.startsWith('vi') ? 'vi' : language?.startsWith('ja') ? 'ja' : 'en'; const messages = { en: { name: 'Scenario name is required.', value: 'Enter a value of zero or more.', target: 'Select a valid baseline item.', duplicate: 'Each item can only be changed once.', probability: 'Win probability must be between 0% and 100%.' }, ja: { name: 'シナリオ名を入力してください。', value: '0以上の値を入力してください。', target: '有効な対象を選択してください。', duplicate: '同じ対象は一度だけ変更できます。', probability: '受注確率は0%から100%で入力してください。' }, vi: { name: 'Vui lòng nhập tên kịch bản.', value: 'Nhập giá trị bằng hoặc lớn hơn 0.', target: 'Chọn một mục hợp lệ từ dữ liệu nền.', duplicate: 'Mỗi mục chỉ được thay đổi một lần.', probability: 'Xác suất thắng phải từ 0% đến 100%.' } } as const; return messages[lang][code as keyof typeof messages.en] ?? code }

function ChangeRows({ title, helper, targetLabel, valueLabel, rows, ids, probability = false, onChange }: { title: string; helper: string; targetLabel: string; valueLabel: string; rows: OverrideRow[]; ids: string[]; probability?: boolean; onChange: (rows: OverrideRow[]) => void }) {
  const { i18n } = useTranslation(); const c = managerCopy(i18n.resolvedLanguage).scenarios; const available = ids.filter((id) => !rows.some((row) => row.id === id))
  return <fieldset className='business-override-group'><legend>{title}</legend><p>{helper}</p>{rows.map((row, index) => <div className='business-override-row' key={`${row.id}-${index}`}><label><span>{targetLabel}</span><select aria-label={`${title} ${targetLabel}`} value={row.id} onChange={(event) => onChange(rows.map((item, itemIndex) => itemIndex === index ? { ...item, id: event.target.value } : item))}><option value=''>{c.select}</option>{ids.map((id) => <option key={id} value={id}>{id}</option>)}</select></label><label><span>{valueLabel}</span><input aria-label={`${title} ${valueLabel}`} type='number' min='0' max={probability ? '100' : undefined} step={probability ? '1' : '0.1'} value={row.value} onChange={(event) => onChange(rows.map((item, itemIndex) => itemIndex === index ? { ...item, value: event.target.value === '' ? '' : Number(event.target.value) } : item))} /></label><button type='button' className='button button--ghost' onClick={() => onChange(rows.filter((_, itemIndex) => itemIndex !== index))}>{c.remove}</button></div>)}<button type='button' className='button button--secondary' disabled={!available.length} onClick={() => onChange([...rows, { id: available[0] ?? '', value: '' }])}>+ {c.add}</button></fieldset>
}

function SelectionRows({ values, ids, onChange }: { values: string[]; ids: string[]; onChange: (values: string[]) => void }) {
  const { i18n } = useTranslation()
  const c = managerCopy(i18n.resolvedLanguage).scenarios
  const available = ids.filter((id) => !values.includes(id))
  return <fieldset className='business-override-group'><legend>{c.deferWork}</legend><p>{c.deferWorkHelp}</p>{values.map((id, index) => <div className='business-override-row business-override-row--single' key={id}><label><span>{c.targetWork}</span><select value={id} onChange={(event) => onChange(values.map((value, itemIndex) => itemIndex === index ? event.target.value : value))}>{ids.map((workId) => <option key={workId} value={workId}>{workId}</option>)}</select></label><button type='button' className='button button--ghost' onClick={() => onChange(values.filter((_, itemIndex) => itemIndex !== index))}>{c.remove}</button></div>)}<button type='button' className='button button--secondary' disabled={!available.length} onClick={() => onChange([...values, available[0]])}>+ {c.add}</button></fieldset>
}

function ScenarioEditor({ initial, catalog, busy, onCancel, onSave }: { initial: FormState; catalog: BaselineCatalog; busy: boolean; onCancel: () => void; onSave: (form: FormState) => Promise<void> }) {
  const { i18n } = useTranslation(); const c = managerCopy(i18n.resolvedLanguage).scenarios; const [form, setForm] = useState(initial); const [errors, setErrors] = useState<string[]>([])
  async function submit(event: React.FormEvent) { event.preventDefault(); const found = errorsFor(form, catalog); if (found.length) { setErrors(found.map((code) => validationMessage(code, i18n.resolvedLanguage))); return } setErrors([]); try { await onSave(form) } catch (error) { setErrors(apiErrors(error)) } }
  const numeric = (key: 'startingCash' | 'fixedOutflow' | 'minimumBuffer', raw: string) => setForm({ ...form, [key]: raw === '' ? '' : Number(raw) })
  return <form className='scenario-editor business-form' onSubmit={(event) => void submit(event)} noValidate><div className='editor-heading'><div><span className='eyebrow'>{c.create}</span><h2>{form.name || c.create}</h2><p>{c.helper}</p></div><button type='button' className='button button--ghost' onClick={onCancel}>{c.cancel}</button></div>{errors.length > 0 && <div className='form-errors' role='alert'><ul>{errors.map((error) => <li key={error}>{error}</li>)}</ul></div>}
    <div className='form-grid'><label><span>{c.name}</span><input value={form.name} maxLength={200} onChange={(event) => setForm({ ...form, name: event.target.value })} /></label><label><span>{c.status}</span><select value={form.status} onChange={(event) => setForm({ ...form, status: event.target.value as FormState['status'] })}><option value='ACTIVE'>{c.active}</option><option value='INACTIVE'>{c.inactive}</option></select></label><label className='form-grid__wide'><span>{c.descriptionLabel}</span><textarea value={form.description} maxLength={2000} rows={3} onChange={(event) => setForm({ ...form, description: event.target.value })} /></label></div>
    <section className='form-business-section'><h3>{c.finance}</h3><div className='form-grid form-grid--three'><label><span>{c.startingCash}</span><small>{c.startingCashHelp}</small><input type='number' min='0' value={form.startingCash} onChange={(event) => numeric('startingCash', event.target.value)} /></label><label><span>{c.fixedOutflow}</span><small>{c.fixedOutflowHelp}</small><input type='number' min='0' value={form.fixedOutflow} onChange={(event) => numeric('fixedOutflow', event.target.value)} /></label><label><span>{c.buffer}</span><small>{c.bufferHelp}</small><input type='number' min='0' value={form.minimumBuffer} onChange={(event) => numeric('minimumBuffer', event.target.value)} /></label></div></section>
    <section className='form-business-section'><h3>{c.people}</h3><ChangeRows title={c.personCapacity} helper={c.personCapacityHelp} targetLabel={c.targetPerson} valueLabel={c.valueHours} rows={form.people} ids={catalog.people} onChange={(people) => setForm({ ...form, people })} /></section>
    <section className='form-business-section'><h3>{c.work}</h3><ChangeRows title={c.workHours} helper={c.workHoursHelp} targetLabel={c.targetWork} valueLabel={c.effortHours} rows={form.workItems} ids={catalog.workItems} onChange={(workItems) => setForm({ ...form, workItems })} /><ChangeRows title={c.receiptTiming} helper={c.receiptTimingHelp} targetLabel={c.targetWork} valueLabel={c.receiptDays} rows={form.receiptDays} ids={catalog.workItems} onChange={(receiptDays) => setForm({ ...form, receiptDays })} /><SelectionRows values={form.deferredWorkItems} ids={catalog.workItems} onChange={(deferredWorkItems) => setForm({ ...form, deferredWorkItems })} /></section>
    <section className='form-business-section'><h3>{c.commercial}</h3><ChangeRows title={c.probability} helper={c.probabilityHelp} targetLabel={c.targetOption} valueLabel={c.valueProbability} rows={form.commercialOptions} ids={catalog.commercialOptions} probability onChange={(commercialOptions) => setForm({ ...form, commercialOptions })} /></section>
    <div className='form-actions'><button className='button' disabled={busy}>{busy ? c.saving : c.save}</button></div></form>
}

function overrideCount(scenario: Scenario) { const company = scenario.overrides.company ? Object.values(scenario.overrides.company).filter((value) => value != null).length : 0; return company + scenario.overrides.people.length + scenario.overrides.work_items.length + scenario.overrides.commercial_options.length + (scenario.overrides.deferred_work_item_ids?.length ?? 0) }
function RunRow({ run }: { run: ScenarioRun }) { const { i18n } = useTranslation(); const c = managerCopy(i18n.resolvedLanguage).scenarios; return <article className='run-row'><div><strong>{formatDateTime(run.timestamp, i18n.resolvedLanguage)}</strong><span className='run-id'>{run.run_id}</span></div>{run.status === 'COMPLETED' && run.final_decision ? <div className='run-statuses'><ManagerStatus status={run.final_decision.overall_status} /></div> : <ManagerStatus status='FAILED' />}<Link className='button button--secondary' to={`/plan?run_id=${encodeURIComponent(run.run_id)}`}>{c.open}</Link></article> }

function ScenariosWorkspace({ initialNew = null }: { initialNew?: FormState | null }) {
  const { i18n } = useTranslation(); const c = managerCopy(i18n.resolvedLanguage).scenarios
  const [scenarios, setScenarios] = useState<Scenario[]>([]); const [catalog, setCatalog] = useState<BaselineCatalog>(emptyCatalog); const [runs, setRuns] = useState<Record<string, ScenarioRun[]>>({}); const [loading, setLoading] = useState(true); const [error, setError] = useState(false); const [reloadKey, setReloadKey] = useState(0); const [editing, setEditing] = useState<Scenario | 'new' | null>(initialNew ? 'new' : null); const [busy, setBusy] = useState(''); const [deleteId, setDeleteId] = useState<string | null>(null); const [actionError, setActionError] = useState('')
  useEffect(() => { let current = true; setLoading(true); void Promise.all([scenarioApi.list(), baselineCatalogApi.load()]).then(async ([items, loadedCatalog]) => { const histories = await Promise.all(items.map(async (item) => [item.id, await scenarioApi.runs(item.id)] as const)); if (current) { setScenarios(items); setCatalog(loadedCatalog); setRuns(Object.fromEntries(histories)); setError(false); setLoading(false) } }).catch(() => { if (current) { setError(true); setLoading(false) } }); return () => { current = false } }, [reloadKey])
  async function save(form: FormState) { setBusy('save'); try { if (editing === 'new') { const created = await scenarioApi.create(toInput(form)); setScenarios((items) => [...items, created]); setRuns((items) => ({ ...items, [created.id]: [] })) } else if (editing) { const updated = await scenarioApi.update(editing.id, toInput(form)); setScenarios((items) => items.map((item) => item.id === updated.id ? updated : item)) } setEditing(null) } finally { setBusy('') } }
  async function runScenario(id: string) { setBusy(id); setActionError(''); try { const run = await scenarioApi.run(id); setRuns((items) => ({ ...items, [id]: [...(items[id] ?? []), run] })) } catch (reason) { setActionError(apiErrors(reason).join(' ')) } finally { setBusy('') } }
  async function remove(id: string) { setBusy(id); try { await scenarioApi.delete(id); setScenarios((items) => items.filter((item) => item.id !== id)); setDeleteId(null) } catch (reason) { setActionError(apiErrors(reason).join(' ')) } finally { setBusy('') } }
  if (loading) return <ManagerLoading />; if (error) return <ManagerError onRetry={() => setReloadKey((value) => value + 1)} />
  return <div><PageIntro eyebrow={c.eyebrow} title={c.title} description={c.description} action={<button className='button' onClick={() => setEditing('new')}>+ {c.create}</button>} />{actionError && <div className='form-errors' role='alert'>{actionError}</div>}{editing && <ScenarioEditor key={editing === 'new' ? 'new' : editing.id} initial={editing === 'new' ? (initialNew ?? emptyForm()) : fromScenario(editing)} catalog={catalog} busy={busy === 'save'} onCancel={() => setEditing(null)} onSave={save} />}
    {!editing && scenarios.length === 0 && <div className='content-empty'><h2>{c.noRun}</h2><p>{c.description}</p><button className='button' onClick={() => setEditing('new')}>{c.create}</button></div>}
    <div className='scenario-list'>{scenarios.map((scenario) => { const history = runs[scenario.id] ?? []; const latest = history.at(-1); return <article className='scenario-card business-scenario-card' key={scenario.id}><div className='scenario-card__heading'><div><ManagerStatus status={scenario.status} /><h2>{scenario.name}</h2><p>{scenario.description || '—'}</p></div><div className='scenario-actions'><button className='button button--secondary' onClick={() => setEditing(scenario)}>{c.edit}</button><button className='button' disabled={busy === scenario.id || scenario.status === 'INACTIVE'} onClick={() => void runScenario(scenario.id)}>{busy === scenario.id ? c.running : c.run}</button><button className='button button--ghost' onClick={() => setDeleteId(scenario.id)}>{c.delete}</button></div></div><div className='scenario-business-summary'><div><span>{c.latest}</span>{latest?.final_decision ? <ManagerStatus status={latest.final_decision.overall_status} /> : <strong>{c.noRun}</strong>}</div><div><span>{c.lastRun}</span><strong>{latest ? formatDateTime(latest.timestamp, i18n.resolvedLanguage) : c.noRun}</strong></div><div><span>{c.baselineDifference}</span><strong>{overrideCount(scenario) || c.noChanges}</strong></div></div>{deleteId === scenario.id && <div className='delete-confirm' role='alertdialog'><span>{c.delete}?</span><button className='button button--danger' onClick={() => void remove(scenario.id)}>{c.delete}</button><button className='button button--ghost' onClick={() => setDeleteId(null)}>{c.cancel}</button></div>}<details className='run-history'><summary>{c.runHistory} ({history.length})</summary>{history.length ? [...history].reverse().map((run) => <RunRow key={run.run_id} run={run} />) : <p className='muted'>{c.noRun}</p>}</details></article> })}</div>
  </div>
}






function prefilledScenario(params: URLSearchParams, baseline: PlanningCatalog['company']): FormState | null {
  if (!params.has('focus')) return null
  const form = emptyForm()
  form.name = params.get('name') ?? ''
  form.description = params.get('description') ?? ''
  if (params.get('focus') === 'cash') {
    form.startingCash = baseline.starting_cash_jpy
    form.fixedOutflow = baseline.fixed_cash_outflow_jpy
    form.minimumBuffer = baseline.minimum_cash_buffer_jpy
  }
  const startingCash = params.get('starting_cash')
  if (startingCash != null && startingCash !== '') form.startingCash = Number(startingCash)
  const cashAddition = params.get('cash_addition')
  if (cashAddition != null && cashAddition !== '') form.startingCash = baseline.starting_cash_jpy + Number(cashAddition)
  form.deferredWorkItems = (params.get('defer_work') ?? '').split(',').filter(Boolean)
  const receiptWork = params.get('receipt_work')
  const cashInDays = params.get('cash_in_days')
  if (receiptWork && cashInDays != null) form.receiptDays = [{ id: receiptWork, value: Number(cashInDays) }]
  return form
}

export function ScenariosPage() {
  const workflow = useWorkflow()
  const [params] = useSearchParams()
  if (!workflow.catalog) return <WorkflowGate kind='data' />
  if (!workflow.generation) return <WorkflowGate kind='plan' />
  if (workflow.source !== 'sample') return <WorkflowGate kind='sample' />
  return <ScenariosWorkspace initialNew={prefilledScenario(params, workflow.catalog.company)} />
}
