import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { CalendarClock, Download } from 'lucide-react'
import { api } from '../api'
import { Empty, ErrorBox, Skeleton, StatusPill, useAsync, useToast } from '../components/ui'
import { dateParts, dueText, monthKey } from '../util'

export default function Schedule() {
  const nav = useNavigate()
  const toast = useToast()
  const [window, setWindow] = useState('all')
  const [dept, setDept] = useState('')
  const { data, error, loading, reload } = useAsync(() => Promise.all([api.get('/api/instruments'), api.get('/api/departments')]))
  const [items, depts] = data || [[], []]

  const { overdue, months, hoursOnly, never } = useMemo(() => {
    const live = items.filter((i) => i.status === 'active' && (!dept || String(i.department_id) === dept))
    const dated = live.filter((i) => i.due.next_due_on).sort((a, b) => a.due.next_due_on.localeCompare(b.due.next_due_on))
    const overdue = dated.filter((i) => i.due.days_remaining < 0 || i.due.status === 'overdue')
    const rest = dated.filter((i) => !overdue.includes(i) && (window === 'all' || i.due.days_remaining <= Number(window)))
    const months = []
    for (const i of rest) {
      const k = monthKey(i.due.next_due_on)
      const last = months.at(-1)
      last && last.key === k ? last.items.push(i) : months.push({ key: k, items: [i] })
    }
    const hoursOnly = live.filter((i) => !i.due.next_due_on && i.due.hours_remaining != null).sort((a, b) => a.due.hours_remaining - b.due.hours_remaining)
    const never = live.filter((i) => i.due.status === 'uncalibrated')
    return { overdue, months, hoursOnly, never }
  }, [items, window, dept])

  async function exportCsv() {
    try { await api.download('/api/reports/calibrations.csv', 'calibration-records.csv'); toast('Calibration records downloaded') } catch (e) { toast(e.message, 'err') }
  }

  const Row = ({ i }) => {
    const { day, mon } = i.due.next_due_on ? dateParts(i.due.next_due_on) : { day: '—', mon: i.due.hours_remaining != null ? 'hours' : 'n/a' }
    return (
      <li className="link" onClick={() => nav(`/instruments/${i.id}`)}>
        <div className="datebox"><b>{day}</b><span>{mon}</span></div>
        <div className="grow"><b>{i.name}</b><span><span className="mono">{i.asset_tag}</span> · {i.department_code} · {i.due.reason || i.category}</span></div>
        <span className="muted nowrap" style={{ fontSize: 12.5 }}>{dueText(i.due)}</span>
        <StatusPill status={i.due.status} />
      </li>
    )
  }

  return (
    <div className="page">
      <div className="page-head">
        <div><h1>Calibration schedule</h1><p>What falls due, and when — across every lab you can see.</p></div>
        <div className="page-actions">
          {depts.length > 1 && <select className="select" style={{ width: 'auto' }} value={dept} onChange={(e) => setDept(e.target.value)} aria-label="Department"><option value="">All departments</option>{depts.map((d) => <option key={d.id} value={d.id}>{d.code}</option>)}</select>}
          <div className="seg" role="group" aria-label="Time window">
            {[['30', '30 days'], ['90', '90 days'], ['all', 'All']].map(([v, l]) => <button key={v} className={window === v ? 'on' : ''} onClick={() => setWindow(v)}>{l}</button>)}
          </div>
          <button className="btn" onClick={exportCsv}><Download size={16} /> Calibration records</button>
        </div>
      </div>

      {error ? <ErrorBox error={error} retry={reload} /> : loading ? <Skeleton h={400} style={{ borderRadius: 14 }} /> : (
        <div className="stack">
          {overdue.length > 0 && (
            <div className="card" style={{ borderColor: '#f4bdb7' }}>
              <div className="card-head" style={{ background: 'var(--over-bg)', borderRadius: '14px 14px 0 0' }}><h3 style={{ color: 'var(--over)' }}>Overdue <span className="sub">{overdue.length}</span></h3></div>
              <ul className="list">{overdue.map((i) => <Row key={i.id} i={i} />)}</ul>
            </div>
          )}
          {never.length > 0 && (
            <div className="card">
              <div className="card-head"><h3>Never calibrated <span className="sub">{never.length}</span></h3></div>
              <ul className="list">{never.map((i) => <Row key={i.id} i={i} />)}</ul>
            </div>
          )}
          {months.map((m) => (
            <div className="card" key={m.key}>
              <div className="card-head"><h3>{m.key} <span className="sub">{m.items.length} due</span></h3></div>
              <ul className="list">{m.items.map((i) => <Row key={i.id} i={i} />)}</ul>
            </div>
          ))}
          {hoursOnly.length > 0 && window === 'all' && (
            <div className="card">
              <div className="card-head"><h3>Usage-based <span className="sub">no calendar date — calibrated by hours of use</span></h3></div>
              <ul className="list">{hoursOnly.map((i) => <Row key={i.id} i={i} />)}</ul>
            </div>
          )}
          {!overdue.length && !months.length && !never.length && !hoursOnly.length && <div className="card"><Empty icon={CalendarClock} title="Nothing due in this window">Widen the time window to see further ahead.</Empty></div>}
        </div>
      )}
    </div>
  )
}
