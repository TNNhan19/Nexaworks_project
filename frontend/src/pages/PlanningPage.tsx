import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Money, PageIntro } from '../components/business/BusinessUI'
import { formatDate } from '../utils/presentation'
import { useWorkflow } from '../workflow/WorkflowContext'
import { workflowCopy } from '../workflow/copy'
import { WorkflowProgress } from '../workflow/WorkflowUI'

export function PlanningPage() {
  const { i18n } = useTranslation()
  const c = workflowCopy(i18n.resolvedLanguage).planning
  const locale = i18n.resolvedLanguage ?? 'en'
  const navigate = useNavigate()
  const workflow = useWorkflow()
  const [fileError, setFileError] = useState(false)

  const useSample = async () => {
    await workflow.loadSample().catch(() => undefined)
  }
  const loadFile = async (file?: File) => {
    if (!file) return
    setFileError(false)
    try {
      const parsed = JSON.parse(await file.text()) as Record<string, unknown>
      await workflow.loadDataset(parsed)
    } catch {
      setFileError(true)
    }
  }

  if (!workflow.catalog) return <div>
    <PageIntro eyebrow={c.eyebrow} title={c.title} description={c.description} />
    <WorkflowProgress status={workflow.status} />
    <div className='planning-intake-grid'>
      <section className='planning-intake-card planning-intake-card--primary'>
        <span aria-hidden='true'>{'{}'}</span>
        <h2>{c.upload}</h2>
        <p>{c.uploadHelp}</p>
        <label className='button file-button'>
          {c.choose}
          <input aria-label={c.choose} type='file' accept='.json,application/json' disabled={workflow.busy} onChange={(event) => void loadFile(event.target.files?.[0])} />
        </label>
      </section>
      <section className='planning-intake-card'>
        <span aria-hidden='true'>◇</span>
        <h2>{c.sample}</h2>
        <p>{workflowCopy(i18n.resolvedLanguage).entry.description}</p>
        <button className='button button--secondary' disabled={workflow.busy} onClick={() => void useSample()}>{c.sample}</button>
      </section>
    </div>
    {(fileError || workflow.error) && <div className='form-errors' role='alert'>{c.invalid}</div>}
    {workflow.busy && <p className='inline-loading' role='status'>{c.reviewing}</p>}
  </div>

  const summary = workflow.catalog.summary
  const metrics = [
    [c.horizon, `${formatDate(summary.planning_start, locale)} – ${formatDate(summary.planning_end, locale)}`],
    [c.workItems, summary.work_item_count],
    [c.people, summary.people_count],
    [c.capacity, `${summary.total_people_capacity_hours.toLocaleString(locale)} h`],
    [c.commercial, summary.commercial_option_count],
    [c.resources, summary.shared_resource_count],
    [c.effects, summary.portfolio_effect_count],
  ] as const
  return <div>
    <PageIntro eyebrow={c.eyebrow} title={c.loaded} description={workflow.source === 'sample' ? c.sampleSource : c.uploadedSource} />
    <WorkflowProgress status={workflow.status} />
    <section className='planning-review-card'>
      <div className='planning-review-metrics'>
        {metrics.map(([label, value]) => <article key={label}><span>{label}</span><strong>{value}</strong></article>)}
        <article><span>{c.startingCash}</span><strong><Money value={summary.starting_cash_jpy} currency={summary.currency} /></strong></article>
        <article><span>{c.buffer}</span><strong><Money value={summary.minimum_cash_buffer_jpy} currency={summary.currency} /></strong></article>
      </div>
      <div className='workflow-actions'>
        <button className='button button--ghost' onClick={workflow.reset}>{c.startOver}</button>
        <button className='button' onClick={() => navigate('/work-items')}>{c.reviewWork}</button>
      </div>
    </section>
  </div>
}
