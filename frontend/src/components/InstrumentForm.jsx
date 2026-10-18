import { useState } from 'react'
import { api } from '../api'
import { useAuth } from '../auth'
import { Field, Modal, useToast } from './ui'

const CATEGORIES = ['Electronics', 'Mechanical', 'Dimensional', 'Pressure', 'Temperature', 'Optical', 'Electrochemical', 'Weighing', 'Volumetric', 'Magnetic', 'Time', 'General']

// Create (instrument == null) or edit an instrument. `departments` is the list the user may create into.
export default function InstrumentForm({ instrument, departments, onClose, onSaved }) {
  const { user } = useAuth()
  const toast = useToast()
  const editing = !!instrument
  const [f, setF] = useState({
    asset_tag: instrument?.asset_tag ?? '',
    name: instrument?.name ?? '',
    category: instrument?.category ?? 'General',
    department_id: instrument?.department_id ?? (user.department_id || departments[0]?.id || ''),
    make: instrument?.make ?? '', model: instrument?.model ?? '', serial_no: instrument?.serial_no ?? '', location: instrument?.location ?? '',
    commissioned_on: instrument?.commissioned_on ?? '',
    status: instrument?.status ?? 'active',
    calibration_mode: instrument?.calibration_mode ?? 'time',
    interval_days: instrument?.interval_days ?? 365,
    interval_hours: instrument?.interval_hours ?? '',
    notes: instrument?.notes ?? '',
  })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const set = (k) => (e) => setF((x) => ({ ...x, [k]: e.target.value }))
  const useTime = f.calibration_mode !== 'usage'
  const useHours = f.calibration_mode !== 'time'

  async function save(e) {
    e.preventDefault()
    setBusy(true); setError('')
    const body = {
      ...f,
      department_id: Number(f.department_id),
      commissioned_on: f.commissioned_on || null,
      interval_days: useTime ? Number(f.interval_days) || null : null,
      interval_hours: useHours ? Number(f.interval_hours) || null : null,
    }
    try {
      let saved
      if (editing) {
        const { asset_tag, department_id, ...patch } = body // tag and department are fixed after creation
        saved = await api.put(`/api/instruments/${instrument.id}`, patch)
      } else saved = await api.post('/api/instruments', body)
      toast(editing ? 'Instrument updated' : `${saved.asset_tag} added`)
      onSaved(saved)
    } catch (err) { setError(err.message); setBusy(false) }
  }

  return (
    <Modal drawer title={editing ? `Edit ${instrument.asset_tag}` : 'Add instrument'} onClose={onClose}
      footer={<><button className="btn" onClick={onClose} type="button">Cancel</button><button className="btn primary" form="inst-form" disabled={busy}>{busy ? <span className="spinner" /> : editing ? 'Save changes' : 'Add instrument'}</button></>}>
      <form id="inst-form" onSubmit={save} className="stack" style={{ gap: 20 }}>
        {error && <div className="alert" role="alert">{error}</div>}
        <div className="form-grid">
          <Field label="Asset tag *" hint={editing ? 'Cannot be changed' : 'Unique, e.g. VIT-ELE-009'}>
            <input className="input" required minLength={2} value={f.asset_tag} onChange={set('asset_tag')} disabled={editing} />
          </Field>
          <Field label="Department *">
            <select className="select" value={f.department_id} onChange={set('department_id')} disabled={editing || user.role === 'incharge'}>
              {departments.map((d) => <option key={d.id} value={d.id}>{d.code} · {d.name}</option>)}
            </select>
          </Field>
          <Field label="Instrument name *" className="full"><input className="input" required value={f.name} onChange={set('name')} placeholder="e.g. Digital Storage Oscilloscope" /></Field>
          <Field label="Category"><input className="input" list="cats" value={f.category} onChange={set('category')} /><datalist id="cats">{CATEGORIES.map((c) => <option key={c} value={c} />)}</datalist></Field>
          <Field label="Location"><input className="input" value={f.location} onChange={set('location')} placeholder="Lab 204" /></Field>
          <Field label="Make"><input className="input" value={f.make} onChange={set('make')} /></Field>
          <Field label="Model"><input className="input" value={f.model} onChange={set('model')} /></Field>
          <Field label="Serial number"><input className="input" value={f.serial_no} onChange={set('serial_no')} /></Field>
          <Field label="Commissioned on"><input className="input" type="date" value={f.commissioned_on} onChange={set('commissioned_on')} /></Field>
          {editing && (
            <Field label="Status" className="full" hint="Retired instruments leave the compliance totals; out-of-service ones cannot be booked.">
              <select className="select" value={f.status} onChange={set('status')}>
                <option value="active">Active</option><option value="out_of_service">Out of service</option><option value="retired">Retired</option>
              </select>
            </Field>
          )}
        </div>

        <div className="card card-pad" style={{ background: '#fafbfd', boxShadow: 'none' }}>
          <Field label="Calibrate based on" hint="Usage-based calibration uses the hours logged against the instrument since its last calibration.">
            <div><div className="seg" role="group">
              {[['time', 'Time interval'], ['usage', 'Hours of use'], ['both', 'Whichever first']].map(([v, l]) => (
                <button type="button" key={v} className={f.calibration_mode === v ? 'on' : ''} onClick={() => setF((x) => ({ ...x, calibration_mode: v }))}>{l}</button>
              ))}
            </div></div>
          </Field>
          <div className="form-grid" style={{ marginTop: 14 }}>
            {useTime && <Field label="Every (days)"><input className="input" type="number" min="1" max="3650" required value={f.interval_days} onChange={set('interval_days')} /></Field>}
            {useHours && <Field label="Every (hours of use)"><input className="input" type="number" min="1" step="any" required value={f.interval_hours} onChange={set('interval_hours')} placeholder="e.g. 500" /></Field>}
          </div>
        </div>
        <Field label="Notes"><textarea className="textarea" value={f.notes} onChange={set('notes')} /></Field>
      </form>
    </Modal>
  )
}
