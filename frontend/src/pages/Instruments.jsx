import { useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Download, FlaskConical, Plus, Search } from 'lucide-react'
import { api } from '../api'
import { useAuth } from '../auth'
import InstrumentForm from '../components/InstrumentForm'
import { Empty, ErrorBox, Skeleton, StatusPill, useAsync, useToast } from '../components/ui'
import { dueText, fmtDate } from '../util'

const STATUS_FILTERS = [
  ['', 'All statuses'],
  ['overdue,failed,uncalibrated,due_soon', 'Needs attention'],
  ['ok', 'Calibrated'],
  ['due_soon', 'Due soon'],
  ['overdue,failed', 'Overdue or failed'],
  ['uncalibrated', 'Not calibrated'],
  ['out_of_service', 'Out of service'],
  ['retired', 'Retired'],
]

export default function Instruments() {
  const { user, isAdmin } = useAuth()
  const nav = useNavigate()
  const toast = useToast()
  const [params, setParams] = useSearchParams()
  const [adding, setAdding] = useState(false)
  const { data, error, loading, reload } = useAsync(() => Promise.all([api.get('/api/instruments'), api.get('/api/departments')]))
  const [items, depts] = data || [[], []]

  const q = params.get('q') || '', status = params.get('status') || '', dept = params.get('dept') || '', cat = params.get('cat') || ''
  const setParam = (k, v) => setParams((p) => { const n = new URLSearchParams(p); v ? n.set(k, v) : n.delete(k); return n }, { replace: true })
  const canAdd = user.role === 'admin' || user.role === 'incharge'

  const categories = useMemo(() => [...new Set(items.map((i) => i.category))].sort(), [items])
  const rows = useMemo(() => {
    const wanted = status ? new Set(status.split(',')) : null
    const needle = q.trim().toLowerCase()
    return items.filter((i) => {
      if (!wanted && (i.status === 'retired')) return false // retired hidden unless asked for
      if (wanted && !wanted.has(i.due.status) && !wanted.has(i.status)) return false
      if (dept && String(i.department_id) !== dept) return false
      if (cat && i.category !== cat) return false
      return !needle || [i.name, i.asset_tag, i.serial_no, i.make, i.model, i.location].some((s) => (s || '').toLowerCase().includes(needle))
    })
  }, [items, q, status, dept, cat])

  async function exportCsv() {
    try { await api.download('/api/reports/instruments.csv', 'instrument-calibration-status.csv'); toast('Report downloaded') } catch (e) { toast(e.message, 'err') }
  }

  return (
    <div className="page">
      <div className="page-head">
        <div><h1>Instruments</h1><p>Every instrument, its calibration state and next due date.</p></div>
        <div className="page-actions">
          <button className="btn" onClick={exportCsv}><Download size={16} /> Export CSV</button>
          {canAdd && <button className="btn primary" onClick={() => setAdding(true)}><Plus size={17} /> Add instrument</button>}
        </div>
      </div>

      <div className="card">
        <div className="filters">
          <div className="searchbox"><Search size={16} /><input className="input" placeholder="Search name, tag, serial, make…" value={q} onChange={(e) => setParam('q', e.target.value)} aria-label="Search instruments" /></div>
          <select className="select" value={status} onChange={(e) => setParam('status', e.target.value)} aria-label="Filter by status">
            {STATUS_FILTERS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            {status && !STATUS_FILTERS.some(([v]) => v === status) && <option value={status}>Custom filter</option>}
          </select>
          {depts.length > 1 && (
            <select className="select" value={dept} onChange={(e) => setParam('dept', e.target.value)} aria-label="Filter by department">
              <option value="">All departments</option>{depts.map((d) => <option key={d.id} value={d.id}>{d.code} · {d.name}</option>)}
            </select>
          )}
          <select className="select" value={cat} onChange={(e) => setParam('cat', e.target.value)} aria-label="Filter by category">
            <option value="">All categories</option>{categories.map((c) => <option key={c}>{c}</option>)}
          </select>
        </div>

        {error ? <div style={{ padding: 20 }}><ErrorBox error={error} retry={reload} /></div> : loading ? (
          <div style={{ padding: 20, display: 'grid', gap: 12 }}>{[0, 1, 2, 3, 4, 5].map((i) => <Skeleton key={i} h={46} />)}</div>
        ) : rows.length === 0 ? (
          <Empty icon={FlaskConical} title="No instruments match">Try clearing a filter{canAdd ? ' or add a new instrument' : ''}.</Empty>
        ) : (
          <>
            <div className="table-wrap">
              <table className="t">
                <thead><tr><th>Instrument</th><th>Dept</th><th>Basis</th><th>Last calibrated</th><th>Next due</th><th>Status</th></tr></thead>
                <tbody>
                  {rows.map((i) => (
                    <tr key={i.id} className="link" onClick={() => nav(`/instruments/${i.id}`)}>
                      <td className="primary-cell">
                        <b>{i.name}</b>
                        <span><span className="mono">{i.asset_tag}</span> · {[i.make, i.model].filter(Boolean).join(' ') || i.category}</span>
                      </td>
                      <td><span className="tag">{i.department_code}</span></td>
                      <td className="muted nowrap">{i.calibration_mode === 'time' ? `${i.interval_days} days` : i.calibration_mode === 'usage' ? `${i.interval_hours} h use` : `${i.interval_days} d / ${i.interval_hours} h`}</td>
                      <td className="nowrap">{fmtDate(i.due.last_calibrated_on)}</td>
                      <td className="nowrap">{i.due.next_due_on ? <><b style={{ fontWeight: 600 }}>{fmtDate(i.due.next_due_on)}</b><div className="faint" style={{ fontSize: 12 }}>{dueText(i.due)}</div></> : i.due.hours_remaining != null ? <span className="muted">{dueText(i.due)}</span> : '—'}</td>
                      <td><div className="row"><StatusPill status={i.due.status} />{i.in_use && <span className="tag live" title={`In use by ${i.in_use_by}`}><span className="dot-live" />In use</span>}</div></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="t-foot"><span>Showing {rows.length} of {items.length} instruments</span></div>
          </>
        )}
      </div>

      {adding && <InstrumentForm departments={isAdmin ? depts : depts.filter((d) => d.id === user.department_id)} onClose={() => setAdding(false)} onSaved={(i) => { setAdding(false); nav(`/instruments/${i.id}`) }} />}
    </div>
  )
}
