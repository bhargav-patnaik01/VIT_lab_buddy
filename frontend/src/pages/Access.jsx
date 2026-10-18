import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Activity, ArrowDownLeft, ArrowUpRight, DoorOpen, Nfc } from 'lucide-react'
import { api } from '../api'
import { useAuth } from '../auth'
import { Empty, ErrorBox, Field, Modal, Skeleton, useAsync, useToast } from '../components/ui'
import { ago, fmtDateTime, fmtHours, fmtTime } from '../util'

export default function Access() {
  const { user, isAdmin } = useAuth()
  const nav = useNavigate()
  const toast = useToast()
  const [tab, setTab] = useState('entries')
  const [dept, setDept] = useState('')
  const [logging, setLogging] = useState(false)
  const labs = useAsync(() => api.get('/api/access/summary'))
  const events = useAsync(() => api.get(`/api/access?days=7${dept ? `&department_id=${dept}` : ''}`), [dept])
  const sessions = useAsync(() => api.get('/api/usage?limit=150'))
  const canLog = user.role === 'admin' || user.role === 'incharge'
  const reloadAll = () => { labs.reload(); events.reload() }

  return (
    <div className="page">
      <div className="page-head">
        <div><h1>Lab access &amp; usage</h1><p>Who is in each lab, and how the instruments are being used.</p></div>
        {canLog && <div className="page-actions"><button className="btn primary" onClick={() => setLogging(true)}><Nfc size={17} /> Log entry / exit</button></div>}
      </div>

      {labs.error ? <ErrorBox error={labs.error} retry={labs.reload} /> : (
        <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(230px, 1fr))', marginBottom: 22 }}>
          {!labs.data ? [0, 1, 2].map((i) => <Skeleton key={i} h={140} style={{ borderRadius: 14 }} />) : labs.data.map((l) => (
            <div className="card lab" key={l.department_id}>
              <h4><span>{l.code}</span><span className="tag live"><span className="dot-live" />live</span></h4>
              <div className="big">{l.inside.length}<span className="muted" style={{ fontSize: 14, fontWeight: 500 }}> inside now</span></div>
              <div className="muted" style={{ fontSize: 12.5 }}>{l.entries_today} entries today</div>
              <div className="chips">{l.inside.slice(0, 6).map((p) => <span className="chip" key={p}>{p}</span>)}{l.inside.length > 6 && <span className="chip">+{l.inside.length - 6}</span>}</div>
            </div>
          ))}
        </div>
      )}

      <div className="tabs">
        <button className={`tab ${tab === 'entries' ? 'on' : ''}`} onClick={() => setTab('entries')}>Entry &amp; exit log</button>
        <button className={`tab ${tab === 'usage' ? 'on' : ''}`} onClick={() => setTab('usage')}>Equipment usage</button>
      </div>

      {tab === 'entries' && (
        <div className="card">
          {labs.data?.length > 1 && (
            <div className="filters"><select className="select" value={dept} onChange={(e) => setDept(e.target.value)} aria-label="Lab"><option value="">All labs</option>{labs.data.map((l) => <option key={l.department_id} value={l.department_id}>{l.code} · {l.name}</option>)}</select><span className="muted">Last 7 days</span></div>
          )}
          {events.error ? <div style={{ padding: 20 }}><ErrorBox error={events.error} retry={events.reload} /></div> : !events.data ? <div style={{ padding: 20 }}><Skeleton h={200} /></div> : events.data.length === 0 ? (
            <Empty icon={DoorOpen} title="No entries logged">Swipes from RFID readers will appear here.</Empty>
          ) : (
            <div className="table-wrap"><table className="t">
              <thead><tr><th>Time</th><th>Lab</th><th>Person</th><th>Direction</th><th>Method</th></tr></thead>
              <tbody>{events.data.map((e) => (
                <tr key={e.id}>
                  <td className="nowrap">{fmtDateTime(e.at)} <span className="faint">· {ago(e.at)}</span></td>
                  <td><span className="tag">{e.department_code}</span></td>
                  <td><b style={{ fontWeight: 600 }}>{e.person_ref}</b>{e.card_uid && <div className="mono faint">{e.card_uid}</div>}</td>
                  <td>{e.direction === 'in' ? <span className="row" style={{ color: 'var(--ok)', fontWeight: 600 }}><ArrowDownLeft size={16} /> Entered</span> : <span className="row muted" style={{ fontWeight: 600 }}><ArrowUpRight size={16} /> Left</span>}</td>
                  <td><span className="tag">{e.method}</span></td>
                </tr>
              ))}</tbody>
            </table></div>
          )}
        </div>
      )}

      {tab === 'usage' && (
        <div className="card">
          {sessions.error ? <div style={{ padding: 20 }}><ErrorBox error={sessions.error} retry={sessions.reload} /></div> : !sessions.data ? <div style={{ padding: 20 }}><Skeleton h={200} /></div> : sessions.data.length === 0 ? (
            <Empty icon={Activity} title="No usage recorded" />
          ) : (
            <div className="table-wrap"><table className="t">
              <thead><tr><th>Started</th><th>Instrument</th><th>User</th><th>Purpose</th><th className="right">Duration</th><th>Source</th></tr></thead>
              <tbody>{sessions.data.map((s) => (
                <tr key={s.id} className="link" onClick={() => nav(`/instruments/${s.instrument_id}`)}>
                  <td className="nowrap">{fmtDateTime(s.started_at)}</td>
                  <td className="primary-cell"><b>{s.instrument_name}</b><span className="mono">{s.asset_tag}</span></td>
                  <td>{s.user_ref}</td><td className="muted">{s.purpose || '—'}</td>
                  <td className="right nowrap">{s.ended_at ? fmtHours(s.hours) : <span className="tag live"><span className="dot-live" />running · {fmtTime(s.started_at)}</span>}</td>
                  <td><span className="tag">{s.source}</span></td>
                </tr>
              ))}</tbody>
            </table></div>
          )}
        </div>
      )}

      {logging && labs.data && <LogEntry labs={isAdmin ? labs.data : labs.data.filter((l) => l.department_id === user.department_id)} onClose={() => setLogging(false)} onSaved={() => { setLogging(false); toast('Entry logged'); reloadAll() }} />}
    </div>
  )
}

function LogEntry({ labs, onClose, onSaved }) {
  const [f, setF] = useState({ department_id: labs[0]?.department_id, person_ref: '', direction: 'in', card_uid: '' })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function submit(e) {
    e.preventDefault(); setBusy(true); setError('')
    try { await api.post('/api/access', { ...f, department_id: Number(f.department_id), method: f.card_uid ? 'rfid' : 'manual' }); onSaved() } catch (err) { setError(err.message); setBusy(false) }
  }
  return (
    <Modal title="Log lab entry / exit" onClose={onClose} footer={<><button className="btn" type="button" onClick={onClose}>Cancel</button><button className="btn primary" form="acc-form" disabled={busy}>{busy ? <span className="spinner" /> : 'Log'}</button></>}>
      <form id="acc-form" onSubmit={submit} className="stack" style={{ gap: 16 }}>
        {error && <div className="alert" role="alert">{error}</div>}
        <p className="muted" style={{ margin: 0 }}>Normally RFID readers post these automatically. Use this to record a manual entry or to try the flow.</p>
        {labs.length > 1 && <Field label="Lab"><select className="select" value={f.department_id} onChange={(e) => setF({ ...f, department_id: e.target.value })}>{labs.map((l) => <option key={l.department_id} value={l.department_id}>{l.code} · {l.name}</option>)}</select></Field>}
        <Field label="Person *" hint="Registration number or staff name"><input className="input" required autoFocus value={f.person_ref} onChange={(e) => setF({ ...f, person_ref: e.target.value })} /></Field>
        <Field label="Direction"><div><div className="seg"><button type="button" className={f.direction === 'in' ? 'on' : ''} onClick={() => setF({ ...f, direction: 'in' })}>Entering</button><button type="button" className={f.direction === 'out' ? 'on' : ''} onClick={() => setF({ ...f, direction: 'out' })}>Leaving</button></div></div></Field>
        <Field label="Card UID (optional)"><input className="input mono" value={f.card_uid} onChange={(e) => setF({ ...f, card_uid: e.target.value })} placeholder="04:A1:B2:C3" /></Field>
      </form>
    </Modal>
  )
}
