import { NavLink } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

export function RunContextNav({ runId }: { runId: string }) {
  const { t } = useTranslation()
  const query = `?run_id=${encodeURIComponent(runId)}`
  return <nav className='run-context-nav' aria-label={t('runNav.label')}>
    <NavLink to={`/plan${query}`}>{t('nav.plan')}</NavLink>
    <NavLink to={`/cash-flow${query}`}>{t('nav.cashFlow')}</NavLink>
    <NavLink to={`/explanations${query}`}>{t('nav.explanations')}</NavLink>
  </nav>
}
