import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { CalendarClock, DoorOpen, FlaskConical, LayoutDashboard, LogOut, Menu, ScrollText, Settings2, ShieldCheck } from 'lucide-react'
import { useAuth } from '../auth'
import { ROLE_LABEL, initials } from '../util'

export default function Layout() {
  const { user, logout, isAdmin } = useAuth()
  const [open, setOpen] = useState(false)
  const loc = useLocation()
  useEffect(() => setOpen(false), [loc.pathname])

  const link = (to, Icon, label) => (
    <NavLink to={to} className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
      <Icon size={19} /> {label}
    </NavLink>
  )

  return (
    <div className="app">
      <header className="topbar">
        <button className="icon-btn menu-btn" onClick={() => setOpen((o) => !o)} aria-label="Toggle navigation"><Menu size={22} /></button>
        <img className="logo" src="/vit-logo.png" alt="Vellore Institute of Technology" />
        <span className="divider" />
        <div className="product">
          <b>Lab Calibration &amp; Access Tracker</b>
          <span>Equipment compliance portal</span>
        </div>
        <span className="spacer" />
        <div className="userchip">
          <div className="avatar" aria-hidden>{initials(user.name)}</div>
          <div className="who">
            <b>{user.name}</b>
            <span>{ROLE_LABEL[user.role]}{user.department_code ? ` · ${user.department_code}` : ''}</span>
          </div>
          <button className="icon-btn" onClick={logout} title="Sign out" aria-label="Sign out"><LogOut size={19} /></button>
        </div>
      </header>

      <div className="shell">
        <nav className={`sidebar ${open ? 'open' : ''}`} aria-label="Main">
          <div className="group">Overview</div>
          {link('/', LayoutDashboard, 'Dashboard')}
          <div className="group">Equipment</div>
          {link('/instruments', FlaskConical, 'Instruments')}
          {link('/schedule', CalendarClock, 'Calibration schedule')}
          <div className="group">Labs</div>
          {link('/access', DoorOpen, 'Lab access & usage')}
          <div className="group">Compliance</div>
          {link('/audit', ShieldCheck, 'Audit trail')}
          {isAdmin && (<><div className="group">Administration</div>{link('/admin', Settings2, 'Users & departments')}</>)}
          <div className="foot">
            <ScrollText size={14} style={{ verticalAlign: '-2px' }} /> {user.role === 'head' ? 'Read-only access to all departments' : user.role === 'incharge' ? 'Access limited to your department' : 'Full access to all departments'}
          </div>
        </nav>
        <div className={`scrim ${open ? 'open' : ''}`} onClick={() => setOpen(false)} />
        <main className="main"><Outlet /></main>
      </div>
    </div>
  )
}
