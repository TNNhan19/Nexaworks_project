import { useTranslation } from 'react-i18next'
import { useLocation } from 'react-router-dom'
import { navigationItems } from './navigation'

interface HeaderProps { onMenuClick: () => void }

export function Header({ onMenuClick }: HeaderProps) {
  const { t, i18n } = useTranslation()
  const location = useLocation()
  const current = navigationItems.find((item) => location.pathname === item.path)?.key ?? 'dashboard'
  return (
    <header className="app-header">
      <button className="menu-button" onClick={onMenuClick} aria-label={t('header.openMenu')}><span /><span /><span /></button>
      <div className="header-title"><span>{t('header.workspace')}</span><strong>{t(`nav.${current}`)}</strong></div>
      <label className="language-select">
        <span>{t('header.language')}</span>
        <select aria-label={t('header.language')} value={i18n.resolvedLanguage ?? 'en'} onChange={(event) => void i18n.changeLanguage(event.target.value)}>
          <option value="en">EN</option><option value="ja">JA</option><option value="vi">VI</option>
        </select>
      </label>
    </header>
  )
}
