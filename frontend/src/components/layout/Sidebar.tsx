import { NavLink } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { NavIcon } from './NavIcon'
import { navigationItems } from './navigation'
import nexaWorksLogo from '../../logo/NexaWorks_logo.png'

interface SidebarProps { open: boolean; onClose: () => void }

export function Sidebar({ open, onClose }: SidebarProps) {
  const { t } = useTranslation()
  return <>
    <aside className={`sidebar${open ? ' sidebar--open' : ''}`} aria-label="Primary navigation">
      <div className="brand">
        <img className="brand__logo" src={nexaWorksLogo} alt={`${t('appName')} ${t('appSubtitle')}`} />
      </div>
      <nav className="nav-list">
        {navigationItems.map((item) => (
          <NavLink key={item.path} to={item.path} onClick={onClose} className={({ isActive }) => `nav-link${isActive ? ' nav-link--active' : ''}`}>
            <NavIcon name={item.icon} /><span>{t(`nav.${item.key}`)}</span>
          </NavLink>
        ))}
      </nav>
    </aside>
    {open && <button className="sidebar-backdrop" onClick={onClose} aria-label={t('header.closeMenu')} />}
  </>
}
