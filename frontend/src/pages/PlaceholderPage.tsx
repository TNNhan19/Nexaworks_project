import { useTranslation } from 'react-i18next'
import type { NavigationKey } from '../components/layout/navigation'

export function PlaceholderPage({ page }: { page: NavigationKey }) {
  const { t } = useTranslation()
  return <section className="placeholder-page"><div className="placeholder-icon" aria-hidden="true">N</div><span className="eyebrow">{t('placeholder.eyebrow')}</span><h1>{t(`nav.${page}`)}</h1><p>{t('placeholder.description')}</p></section>
}
