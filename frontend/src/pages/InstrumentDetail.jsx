import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Activity, AlertTriangle, CheckCircle2, ChevronRight, ClipboardCheck, Clock, FileCheck2, FileText, Hourglass, Pencil, Play, Square, Upload } from 'lucide-react'
import { api } from '../api'
import { useAuth } from '../auth'
import InstrumentForm from '../components/InstrumentForm'
import { UsageBars } from '../components/charts'
import { Empty, ErrorBox, Field, Modal, Skeleton, StatusPill, useAsync, useToast } from '../components/ui'
import { dueText, fmtDate, fmtDateTime, fmtHours, todayISO } from '../util'

const BANNER_ICON = { ok: CheckCircle2, due_soon: Hourglass, overdue: AlertTriangle, failed: AlertTriangle, uncalibrated: ClipboardCheck, out_of_service: Clock, retired: Clock }

export default function InstrumentDetail() {
  const { id } = useParams()
  const { canWrite } = useAuth()
  const toast = useToast()
  const [tab, setTab] = useState('calibration')
  const [modal, setModal] = useState(null) // calibrate | usage | start | edit
  const inst = useAsync(() => api.get(`/api/instruments/${id}`), [id])
  const cals = useAsync(() => api.get(`/api/instruments/${id}/calibrations`), [id])
  const usage = useAsync(() => api.get(`/api/instruments/${id}/usage?days=30`), [id])
  const depts = useAsync(() => api.get('/api/departments'), [])

  const refresh = () => { inst.reload(); cals.reload(); usage.reload() }

  if (inst.error) {
    const missing = inst.error.status === 404
    return (
      <div className="page">
        <ErrorBox error={inst.error} retry={missing ? undefined : inst.reload} />
        {missing && <p className="muted">This instrument doesn’t exist or isn’t in your department. <Link to="/instruments">Back to instruments</Link></p>}
      </div>
    )
  }
  if (!inst.data) return <div className="page"><Skeleton h={34} w={320} /><Skeleton h={120} style={{ marginTop: 20, borderRadius: 14 }} /><Skeleton h={300} style={{ marginTop: 18, borderRadius: 14 }} /></div>

  const i = inst.data
  const d = i.due
  const writable = canWrite(i.department_id)
  const Banner = BANNER_ICON[d.status] || CheckCircle2
  const pctTime = d.days_remaining != null && i.interval_days ? Math.max(0, Math.min(100, (1 - d.days_remaining / i.interval_days) * 100)) : null
  const pctHours = d.hours_remaining != null && i.interval_hours ? Math.max(0, Math.min(100, (d.usage_hours_since / i.interval_hours) * 100)) : null
  const tone = (p) => (p >= 100 ? 'over' : p >= 90 ? 'soon' : 'ok')

  async function stopSession() {
    try { await api.post(`/api/instruments/${i.id}/usage/stop`); toast('Session ended'); refresh() } catch (e) { toast(e.message, 'err') }
  }
  async function openCert(c) {
    try { const { url } = await api.get(`/api/calibrations/${c.id}/certificate-url`); window.open(url, '_blank', 'noopener') } catch (e) { toast(e.message, 'err') }
  }

  return (
    <div className="page">
      <div className="crumbs"><Link to="/instruments">Instruments</Link><ChevronRight size={14} /><span>{i.asset_tag}</span></div>
      <div className="detail-head" style={{ marginBottom: 20 }}>
        <div>
          <div className="row wrap" style={{ gap: 12 }}><h1 style={{ fontSize: 26 }}>{i.name}</h1><StatusPill status={d.status} /></div>
          <p className="muted" style={{ margin: '6px 0 0' }}><span className="mono">{i.asset_tag}</span> · {i.department_code} · {i.category}{i.location ? ` · ${i.location}` : ''}</p>
        </div>
        {writable && i.status !== 'retired' && (
          <div className="page-actions">
            {i.in_use
              ? <button className="btn" onClick={stopSession}><Square size={15} /> End session ({i.in_use_by})</button>
              : i.status === 'active' && <button className="btn" onClick={() => setModal('start')}><Play size={15} /> Start session</button>}
            <button className="btn" onClick={() => setModal('usage')}><Clock size={16} /> Log usage</button>
            <button className="btn primary" onClick={() => setModal('calibrate')}><ClipboardCheck size={17} /> Record calibration</button>
            <button className="icon-btn btn" style={{ width: 38, padding: 0 }} onClick={() => setModal('edit')} aria-label="Edit instrument" title="Edit"><Pencil size={16} /></button>
          </div>
        )}
      </div>

      <div className={`banner ${d.status}`}>
        <Banner size={26} />
        <div className="grow">
          <b>{{ ok: 'Within calibration', due_soon: 'Calibration due soon', overdue: 'Calibration overdue', failed: 'Last calibration failed', uncalibrated: 'No calibration on record', out_of_service: 'Out of service', retired: 'Retired' }[d.status]}</b>
          <div>{d.reason || (d.next_due_on ? `Next due ${fmtDate(d.next_due_on)}` : '')}</div>
        </div>
        {i.in_use && <span className="tag live"><span className="dot-live" />In use by {i.in_use_by}</span>}
      </div>

      <div className="grid cols-main">
        <div className="stack">
          {(pctTime != null || pctHours != null) && (
            <div className="card card-pad stack" style={{ gap: 18 }}>
              {pctTime != null && (
                <div><div className="row" style={{ justifyContent: 'space-between', marginBottom: 8 }}><b>Time interval</b><span className="muted">{fmtDate(d.last_calibrated_on)} → <b style={{ color: 'var(--text)' }}>{fmtDate(d.next_due_on)}</b> · {dueText({ days_remaining: d.days_remaining })}</span></div>
                  <div className="progress"><i className={tone(pctTime)} style={{ width: `${pctTime}%` }} /></div></div>
              )}
              {pctHours != null && (
                <div><div className="row" style={{ justifyContent: 'space-between', marginBottom: 8 }}><b>Usage since last calibration</b><span className="muted">{fmtHours(d.usage_hours_since)} of {fmtHours(i.interval_hours)} · {d.hours_remaining <= 0 ? <b style={{ color: 'var(--over)' }}>limit exceeded</b> : `${fmtHours(d.hours_remaining)} left`}</span></div>
                  <div className="progress"><i className={tone(pctHours)} style={{ width: `${Math.min(100, pctHours)}%` }} /></div></div>
              )}
            </div>
          )}

          <div>
            <div className="tabs" role="tablist">
              <button className={`tab ${tab === 'calibration' ? 'on' : ''}`} role="tab" onClick={() => setTab('calibration')}>Calibration history</button>
              <button className={`tab ${tab === 'usage' ? 'on' : ''}`} role="tab" onClick={() => setTab('usage')}>Usage log</button>
            </div>

            {tab === 'calibration' && (
              <div className="card">
                {cals.loading && !cals.data ? <div style={{ padding: 20 }}><Skeleton h={80} /></div> : !cals.data?.length ? (
                  <Empty icon={ClipboardCheck} title="No calibrations recorded">{writable ? 'Record the first calibration to start the due-date clock.' : 'Nothing has been recorded yet.'}</Empty>
                ) : (
                  <ul className="timeline">
                    {cals.data.map((c) => (
                      <li key={c.id} className={c.result}>
                        <div className="row wrap" style={{ justifyContent: 'space-between', gap: 8 }}>
                          <div><span className="when">{fmtDate(c.performed_on)}</span> <span className={`pill ${c.result === 'pass' ? 'ok' : c.result === 'fail' ? 'failed' : 'due_soon'}`} style={{ marginLeft: 6, textTransform: 'capitalize' }}>{c.result}</span></div>
                          {c.has_certificate
                            ? <button className="btn sm" onClick={() => openCert(c)}><FileText size={14} /> Certificate</button>
                            : <span className="faint" style={{ fontSize: 12.5 }}>No certificate attached</span>}
                        </div>
                        <div className="meta">{[c.performed_by, c.certificate_no && `Cert. ${c.certificate_no}`].filter(Boolean).join(' · ') || 'Details not recorded'} · logged by {c.created_by}</div>
                        {c.notes && <div style={{ marginTop: 4 }}>{c.notes}</div>}
                        {c.certificate_sha256 && <div className="hashline" title="SHA-256 of the stored certificate file — proves it hasn't been altered"><FileCheck2 size={12} style={{ verticalAlign: '-2px' }} /> sha256 {c.certificate_sha256.slice(0, 20)}…</div>}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}

            {tab === 'usage' && (
              <div className="card">
                <div className="card-head"><h3>Last 30 days</h3><span className="sub" style={{ margin: 0 }}>{usage.data ? fmtHours(usage.data.total_hours) : ''} total</span></div>
                {usage.data && <div style={{ paddingTop: 18 }}><UsageBars daily={usage.data.daily} /></div>}
                {!usage.data?.sessions.length ? <Empty icon={Activity} title="No usage logged">Sessions appear here as they are started, logged or sent by the instrument controller.</Empty> : (
                  <div className="table-wrap"><table className="t">
                    <thead><tr><th>Started</th><th>User</th><th>Purpose</th><th className="right">Duration</th><th>Source</th></tr></thead>
                    <tbody>{usage.data.sessions.map((s) => (
                      <tr key={s.id}><td className="nowrap">{fmtDateTime(s.started_at)}</td><td>{s.user_ref}</td><td className="muted">{s.purpose || '—'}</td>
                        <td className="right nowrap">{s.ended_at ? fmtHours(s.hours) : <span className="tag live"><span className="dot-live" />running</span>}</td><td><span className="tag">{s.source}</span></td></tr>
                    ))}</tbody>
                  </table></div>
                )}
              </div>
            )}
          </div>
        </div>

        <div className="card card-pad" style={{ alignSelf: 'start' }}>
          <h3 style={{ marginBottom: 16 }}>Details</h3>
          <dl className="kv" style={{ gridTemplateColumns: '1fr 1fr' }}>
            <div><dt>Make</dt><dd>{i.make || '—'}</dd></div>
            <div><dt>Model</dt><dd>{i.model || '—'}</dd></div>
            <div><dt>Serial no.</dt><dd className="mono">{i.serial_no || '—'}</dd></div>
            <div><dt>Location</dt><dd>{i.location || '—'}</dd></div>
            <div><dt>Commissioned</dt><dd>{fmtDate(i.commissioned_on)}</dd></div>
            <div><dt>Calibration basis</dt><dd>{i.calibration_mode === 'time' ? `Every ${i.interval_days} days` : i.calibration_mode === 'usage' ? `Every ${i.interval_hours} h of use` : `${i.interval_days} days or ${i.interval_hours} h`}</dd></div>
            <div><dt>Last calibrated</dt><dd>{fmtDate(d.last_calibrated_on)}</dd></div>
            <div><dt>Next due</dt><dd>{fmtDate(d.next_due_on)}</dd></div>
          </dl>
          {i.notes && <><h4 style={{ margin: '20px 0 6px', fontSize: 12, textTransform: 'uppercase', letterSpacing: '.06em', color: 'var(--faint)' }}>Notes</h4><p style={{ margin: 0 }}>{i.notes}</p></>}
        </div>
      </div>

      {modal === 'calibrate' && <CalibrationForm inst={i} onClose={() => setModal(null)} onSaved={() => { setModal(null); toast('Calibration recorded'); refresh() }} />}
      {modal === 'usage' && <UsageForm inst={i} onClose={() => setModal(null)} onSaved={() => { setModal(null); toast('Usage logged'); refresh() }} />}
      {modal === 'start' && <StartForm inst={i} onClose={() => setModal(null)} onSaved={() => { setModal(null); toast('Session started'); refresh() }} />}
      {modal === 'edit' && depts.data && <InstrumentForm instrument={i} departments={depts.data} onClose={() => setModal(null)} onSaved={() => { setModal(null); refresh() }} />}
    </div>
  )
}

function CalibrationForm({ inst, onClose, onSaved }) {
  const [f, setF] = useState({ performed_on: todayISO(), performed_by: '', certificate_no: '', result: 'pass', notes: '' })
  const [file, setFile] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const set = (k) => (e) => setF((x) => ({ ...x, [k]: e.target.value }))

  async function submit(e) {
    e.preventDefault()
    if (file && file.size > 5 * 1024 * 1024) return setError('Certificate must be 5 MB or smaller')
    setBusy(true); setError('')
    const fd = new FormData()
    Object.entries(f).forEach(([k, v]) => fd.append(k, v))
    if (file) fd.append('certificate', file)
    try { await api.form(`/api/instruments/${inst.id}/calibrations`, fd); onSaved() } catch (err) { setError(err.message); setBusy(false) }
  }

  return (
    <Modal title={`Record calibration · ${inst.asset_tag}`} onClose={onClose}
      footer={<><button className="btn" type="button" onClick={onClose}>Cancel</button><button className="btn primary" form="cal-form" disabled={busy}>{busy ? <span className="spinner" /> : 'Save calibration'}</button></>}>
      <form id="cal-form" onSubmit={submit} className="stack" style={{ gap: 16 }}>
        {error && <div className="alert" role="alert">{error}</div>}
        <div className="form-grid">
          <Field label="Calibrated on *"><input className="input" type="date" required max={todayISO()} value={f.performed_on} onChange={set('performed_on')} /></Field>
          <Field label="Result *"><select className="select" value={f.result} onChange={set('result')}><option value="pass">Pass</option><option value="adjusted">Pass after adjustment</option><option value="fail">Fail</option></select></Field>
          <Field label="Performed by"><input className="input" value={f.performed_by} onChange={set('performed_by')} placeholder="Agency or technician" /></Field>
          <Field label="Certificate no."><input className="input" value={f.certificate_no} onChange={set('certificate_no')} /></Field>
        </div>
        <Field label="Certificate file" hint="PDF, PNG or JPG up to 5 MB. A SHA-256 fingerprint is stored so any later change is detectable.">
          <label className="btn" style={{ justifyContent: 'flex-start', height: 'auto', padding: '12px 14px', borderStyle: 'dashed', fontWeight: 500 }}>
            <Upload size={18} /> {file ? <b style={{ fontWeight: 600 }}>{file.name}</b> : 'Choose a file…'}
            <input type="file" accept=".pdf,.png,.jpg,.jpeg" className="sr" onChange={(e) => setFile(e.target.files[0] || null)} />
          </label>
        </Field>
        <Field label="Notes"><textarea className="textarea" value={f.notes} onChange={set('notes')} placeholder="Deviations, adjustments made, reference standards used…" /></Field>
        {f.result === 'fail' && <div className="alert">A failed calibration marks the instrument as non-compliant until a passing calibration is recorded.</div>}
      </form>
    </Modal>
  )
}

function StartForm({ inst, onClose, onSaved }) {
  const [f, setF] = useState({ user_ref: '', purpose: '' })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function submit(e) {
    e.preventDefault(); setBusy(true); setError('')
    try { await api.post(`/api/instruments/${inst.id}/usage/start`, f); onSaved() } catch (err) { setError(err.message); setBusy(false) }
  }
  return (
    <Modal title={`Start session · ${inst.asset_tag}`} onClose={onClose} footer={<><button className="btn" type="button" onClick={onClose}>Cancel</button><button className="btn primary" form="start-form" disabled={busy}>{busy ? <span className="spinner" /> : 'Start'}</button></>}>
      <form id="start-form" onSubmit={submit} className="stack" style={{ gap: 16 }}>
        {error && <div className="alert" role="alert">{error}</div>}
        <Field label="Who is using it? *" hint="Registration number or staff name — used to trace faulty data to a user."><input className="input" required autoFocus value={f.user_ref} onChange={(e) => setF({ ...f, user_ref: e.target.value })} /></Field>
        <Field label="Purpose"><input className="input" value={f.purpose} onChange={(e) => setF({ ...f, purpose: e.target.value })} placeholder="Lab experiment, project, practical exam…" /></Field>
      </form>
    </Modal>
  )
}

function UsageForm({ inst, onClose, onSaved }) {
  const now = new Date(); now.setMinutes(now.getMinutes() - now.getTimezoneOffset())
  const [f, setF] = useState({ user_ref: '', purpose: '', started_at: now.toISOString().slice(0, 16), hours: '1' })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const set = (k) => (e) => setF((x) => ({ ...x, [k]: e.target.value }))
  async function submit(e) {
    e.preventDefault(); setBusy(true); setError('')
    try { await api.post(`/api/instruments/${inst.id}/usage`, { ...f, hours: Number(f.hours), started_at: new Date(f.started_at).toISOString() }); onSaved() } catch (err) { setError(err.message); setBusy(false) }
  }
  return (
    <Modal title={`Log usage · ${inst.asset_tag}`} onClose={onClose} footer={<><button className="btn" type="button" onClick={onClose}>Cancel</button><button className="btn primary" form="usage-form" disabled={busy}>{busy ? <span className="spinner" /> : 'Log usage'}</button></>}>
      <form id="usage-form" onSubmit={submit} className="stack" style={{ gap: 16 }}>
        {error && <div className="alert" role="alert">{error}</div>}
        <div className="form-grid">
          <Field label="User *"><input className="input" required value={f.user_ref} onChange={set('user_ref')} /></Field>
          <Field label="Hours used *"><input className="input" type="number" required min="0.1" max="240" step="0.1" value={f.hours} onChange={set('hours')} /></Field>
          <Field label="Started *" className="full"><input className="input" type="datetime-local" required value={f.started_at} onChange={set('started_at')} /></Field>
          <Field label="Purpose" className="full"><input className="input" value={f.purpose} onChange={set('purpose')} /></Field>
        </div>
      </form>
    </Modal>
  )
}
