import { useState } from 'react'
import { BellRing, Building2, Plus, UserPlus } from 'lucide-react'
import { api } from '../api'
import { Empty, ErrorBox, Field, Modal, Skeleton, useAsync, useToast } from '../components/ui'
import { ROLE_LABEL } from '../util'

export default function Admin() {
  const toast = useToast()
  const users = useAsync(() => api.get('/api/users'))
  const depts = useAsync(() => api.get('/api/departments'))
  const [userModal, setUserModal] = useState(null) // {} for new, user for edit
  const [deptModal, setDeptModal] = useState(null)
  const [scan, setScan] = useState(null)
  const [scanning, setScanning] = useState(false)

  async function runScan(notify) {
    setScanning(true)
    try { const r = await api.post(`/api/admin/scan?notify_users=${notify}`); setScan(r); toast(notify ? `Digest sent via ${r.notified_via}` : 'Scan complete') } catch (e) { toast(e.message, 'err') } finally { setScanning(false) }
  }

  return (
    <div className="page">
      <div className="page-head"><div><h1>Users &amp; departments</h1><p>Who can see and change what. Lab in-charges are locked to their own department.</p></div></div>
      <div className="stack">
        <div className="card">
          <div className="card-head"><h3>Users</h3><button className="btn sm primary" onClick={() => setUserModal({})}><UserPlus size={15} /> Add user</button></div>
          {users.error ? <div style={{ padding: 20 }}><ErrorBox error={users.error} retry={users.reload} /></div> : !users.data ? <div style={{ padding: 20 }}><Skeleton h={160} /></div> : (
            <div className="table-wrap"><table className="t">
              <thead><tr><th>Name</th><th>Role</th><th>Department</th><th>Status</th><th /></tr></thead>
              <tbody>{users.data.map((u) => (
                <tr key={u.id}>
                  <td className="primary-cell"><b>{u.name}</b><span>{u.email}</span></td>
                  <td>{ROLE_LABEL[u.role]}</td>
                  <td>{u.department_code ? <span className="tag">{u.department_code}</span> : <span className="faint">All</span>}</td>
                  <td><span className={`pill ${u.active ? 'ok' : 'out_of_service'}`}>{u.active ? 'Active' : 'Disabled'}</span></td>
                  <td className="right"><button className="btn sm" onClick={() => setUserModal(u)}>Edit</button></td>
                </tr>
              ))}</tbody>
            </table></div>
          )}
        </div>

        <div className="grid cols-2">
          <div className="card">
            <div className="card-head"><h3>Departments</h3><button className="btn sm" onClick={() => setDeptModal({})}><Plus size={15} /> Add</button></div>
            {!depts.data ? <div style={{ padding: 20 }}><Skeleton h={120} /></div> : depts.data.length === 0 ? <Empty icon={Building2} title="No departments" /> : (
              <ul className="list">{depts.data.map((d) => (
                <li key={d.id}><span className="tag">{d.code}</span><div className="grow"><b>{d.name}</b></div><button className="btn sm ghost" onClick={() => setDeptModal(d)}>Edit</button></li>
              ))}</ul>
            )}
          </div>

          <div className="card">
            <div className="card-head"><h3>Due-date scan</h3><BellRing size={18} className="faint" /></div>
            <div className="card-pad stack" style={{ gap: 14 }}>
              <p className="muted" style={{ margin: 0 }}>On AWS this runs daily as a scheduled Lambda and emails overdue equipment to the lab teams through SNS. Run it now to preview the digest.</p>
              <div className="row wrap"><button className="btn" disabled={scanning} onClick={() => runScan(false)}>Run scan</button><button className="btn" disabled={scanning} onClick={() => runScan(true)}>Run &amp; send digest</button></div>
              {scan && <pre className="mono" style={{ margin: 0, background: 'var(--bg)', border: '1px solid var(--line)', borderRadius: 10, padding: 14, maxHeight: 260, overflow: 'auto', whiteSpace: 'pre-wrap' }}>{scan.digest}</pre>}
            </div>
          </div>
        </div>
      </div>

      {userModal && depts.data && <UserForm user={userModal} depts={depts.data} onClose={() => setUserModal(null)} onSaved={() => { setUserModal(null); toast('User saved'); users.reload() }} />}
      {deptModal && <DeptForm dept={deptModal} onClose={() => setDeptModal(null)} onSaved={() => { setDeptModal(null); toast('Department saved'); depts.reload() }} />}
    </div>
  )
}

function UserForm({ user, depts, onClose, onSaved }) {
  const editing = !!user.id
  const [f, setF] = useState({ name: user.name || '', email: user.email || '', role: user.role || 'incharge', department_id: user.department_id || depts[0]?.id || '', password: '', active: user.active ?? true })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const set = (k) => (e) => setF((x) => ({ ...x, [k]: e.target.value }))
  async function submit(e) {
    e.preventDefault(); setBusy(true); setError('')
    const dept = f.role === 'incharge' ? Number(f.department_id) : null
    try {
      if (editing) await api.put(`/api/users/${user.id}`, { name: f.name, role: f.role, department_id: dept, active: f.active, ...(f.password ? { password: f.password } : {}) })
      else await api.post('/api/users', { name: f.name, email: f.email, role: f.role, department_id: dept, password: f.password })
      onSaved()
    } catch (err) { setError(err.message); setBusy(false) }
  }
  return (
    <Modal title={editing ? 'Edit user' : 'Add user'} onClose={onClose} footer={<><button className="btn" type="button" onClick={onClose}>Cancel</button><button className="btn primary" form="user-form" disabled={busy}>{busy ? <span className="spinner" /> : 'Save'}</button></>}>
      <form id="user-form" onSubmit={submit} className="stack" style={{ gap: 16 }}>
        {error && <div className="alert" role="alert">{error}</div>}
        <Field label="Full name *"><input className="input" required value={f.name} onChange={set('name')} /></Field>
        <Field label="Email *"><input className="input" type="email" required disabled={editing} value={f.email} onChange={set('email')} /></Field>
        <div className="form-grid">
          <Field label="Role *"><select className="select" value={f.role} onChange={set('role')}><option value="incharge">Lab in-charge</option><option value="head">Department head (read-only)</option><option value="admin">Administrator</option></select></Field>
          {f.role === 'incharge' && <Field label="Department *"><select className="select" value={f.department_id} onChange={set('department_id')}>{depts.map((d) => <option key={d.id} value={d.id}>{d.code} · {d.name}</option>)}</select></Field>}
        </div>
        <Field label={editing ? 'New password' : 'Password *'} hint={editing ? 'Leave blank to keep the current password' : 'At least 8 characters'}><input className="input" type="password" autoComplete="new-password" minLength={8} required={!editing} value={f.password} onChange={set('password')} /></Field>
        {editing && <label className="row" style={{ gap: 10 }}><input type="checkbox" checked={f.active} onChange={(e) => setF({ ...f, active: e.target.checked })} /> Account active</label>}
      </form>
    </Modal>
  )
}

function DeptForm({ dept, onClose, onSaved }) {
  const editing = !!dept.id
  const [f, setF] = useState({ code: dept.code || '', name: dept.name || '' })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function submit(e) {
    e.preventDefault(); setBusy(true); setError('')
    try { editing ? await api.put(`/api/departments/${dept.id}`, f) : await api.post('/api/departments', f); onSaved() } catch (err) { setError(err.message); setBusy(false) }
  }
  return (
    <Modal title={editing ? 'Edit department' : 'Add department'} onClose={onClose} footer={<><button className="btn" type="button" onClick={onClose}>Cancel</button><button className="btn primary" form="dept-form" disabled={busy}>{busy ? <span className="spinner" /> : 'Save'}</button></>}>
      <form id="dept-form" onSubmit={submit} className="stack" style={{ gap: 16 }}>
        {error && <div className="alert" role="alert">{error}</div>}
        <Field label="Short code *" hint="2–16 letters, e.g. ELE"><input className="input" required minLength={2} maxLength={16} value={f.code} onChange={(e) => setF({ ...f, code: e.target.value.toUpperCase() })} /></Field>
        <Field label="Name *"><input className="input" required value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></Field>
      </form>
    </Modal>
  )
}
