import { useTranslation } from 'react-i18next'

export function LoadingState() {
  const { t } = useTranslation()
  return <div className="async-state" role="status"><span className="spinner" /><p>{t('async.loading')}</p></div>
}

export function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  const { t } = useTranslation()
  return <div className="async-state async-state--error" role="alert"><div className="error-symbol">!</div><h2>{t('async.errorTitle')}</h2><p>{message}</p><button className="button" onClick={onRetry}>{t('async.retry')}</button></div>
}
