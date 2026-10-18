import { Link, useNavigate } from 'react-router-dom'
import { Activity, AlertTriangle, ArrowRight, CalendarClock, CheckCircle2, DoorOpen, Download, Gauge, Hourglass, PlayCircle } from 'lucide-react'
import { api } from '../api'
import { useAuth } from '../auth'
import { ComplianceRing, StackedBar } from '../components/charts'
import { Empty, ErrorBox, Skeleton, StatusPill, useAsync, useToast } from '../components/ui'
import { STATUS, STATUS_ORDER, actionLabel, ago, auditSummary, dateParts, dueText, firstName } from '../util'

export default function Dashboard() {
  const { user } = useAuth()
  const nav = useNavigate()
  const toast = useToast()
  const { data, error, loading, reload } = useAsync(() => api.get('/api/dashboard'))

  const greeting = (() => { const h = new Date().getHours(); return h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening' })()
  const scope = user.role === 'incharge' ? `${user.department_code} laboratory` : 'all laboratories'

  async function exportCsv() {
    try { await api.download('/api/reports/instruments.csv', 'instrument-calibration-status.csv'); toast('Report downloaded') } catch (e) { toast(e.message, 'err') }
  }

  if (error) return <div className="page"><ErrorBox error={error} retry={reload} /></div>

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>{greeting}, {firstName(user.name)}</h1>
          <p>Calibration and usage overview for {scope}.</p>
        </div>
        <div className="page-actions">
          <button className="btn" onClick={exportCsv}><Download size={16} /> Export status report</button>
        </div>
      </div>

      {loading || !data ? <DashSkeleton /> : (
        <div className="stack" style={{ gap: 20 }}>
          <div className="kpis">
            <Kpi to="/instruments" icon={CheckCircle2} tone="ok" label="Within calibration" value={data.counts.ok + data.counts.due_soon} note={`of ${data.total} active instruments`} />
            <Kpi to="/instruments?status=due_soon" icon={Hourglass} tone="soon" label="Due soon" value={data.counts.due_soon} note="inside the 30-day window" />
            <Kpi to="/instruments?status=overdue,failed" icon={AlertTriangle} tone="over" label="Overdue or failed" value={data.counts.overdue + data.counts.failed} note={data.counts.uncalibrated ? `+ ${data.counts.uncalibrated} never calibrated` : 'need action now'} />
            <Kpi to="/access" icon={Activity} tone="blue" label="In use right now" value={data.in_use_now} note={`${data.usage_hours_30d} h used in 30 days`} />
          </div>

          <div className="grid cols-main">
            <div className="stack">
              <div className="card">
                <div className="card-head">
                  <h3>Needs attention <span className="sub">{data.attention_total} instrument{data.attention_total === 1 ? '' : 's'}</span></h3>
                  <Link to="/instruments?status=overdue,failed,uncalibrated,due_soon" className="row" style={{ fontWeight: 600, fontSize: 13 }}>View all <ArrowRight size={15} /></Link>
                </div>
                {data.attention.length === 0 ? (
                  <Empty icon={CheckCircle2} title="All clear">Every instrument is comfortably within its calibration window.</Empty>
                ) : (
                  <ul className="list">
                    {data.attention.map((i) => (
                      <li key={i.id} className="link" onClick={() => nav(`/instruments/${i.id}`)}>
                        <div className="grow">
                          <b>{i.name}</b>
                          <span><span className="mono">{i.asset_tag}</span> · {i.reason || dueText(i)}</span>
                        </div>
                        <StatusPill status={i.status} />
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              <div className="card">
                <div className="card-head"><h3>Calibrations due in the next 60 days</h3><CalendarClock size={18} className="faint" /></div>
                {data.upcoming.length === 0 ? (
                  <Empty icon={CalendarClock} title="Nothing scheduled">No calibration falls due in the next 60 days.</Empty>
                ) : (
                  <ul className="list">
                    {data.upcoming.map((i) => {
                      const { day, mon } = dateParts(i.next_due_on)
                      return (
                        <li key={i.id} className="link" onClick={() => nav(`/instruments/${i.id}`)}>
                          <div className="datebox"><b>{day}</b><span>{mon}</span></div>
                          <div className="grow"><b>{i.name}</b><span><span className="mono">{i.asset_tag}</span> · {i.department_code}</span></div>
                          <span className="muted nowrap">{dueText(i)}</span>
                        </li>
                      )
                    })}
                  </ul>
                )}
              </div>
            </div>

            <div className="stack">
              <div className="card">
                <div className="card-head"><h3>Calibration health</h3></div>
                <div className="ring-wrap">
                  <ComplianceRing counts={data.counts} total={data.total} pct={data.compliance_pct} />
                  <div className="legend">
                    {STATUS_ORDER.map((k) => (
                      <div key={k} className="li"><i style={{ background: STATUS[k].color }} />{STATUS[k].label}<b>{data.counts[k] || 0}</b></div>
                    ))}
                  </div>
                </div>
              </div>

              {data.departments.length > 1 && (
                <div className="card">
                  <div className="card-head"><h3>By department</h3><span className="sub">cross-department view</span></div>
                  <div style={{ padding: '8px 0 10px' }}>
                    {data.departments.map((d) => (
                      <div className="dept-row" key={d.department_id}>
                        <div><span className="code">{d.code}</span></div>
                        <StackedBar row={d} />
                        <b className="right">{d.total}</b>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="card">
                <div className="card-head"><h3>Labs right now</h3><DoorOpen size={18} className="faint" /></div>
                <ul className="list">
                  {data.labs.map((l) => (
                    <li key={l.department_id}>
                      <div className="grow"><b>{l.code}</b><span>{l.entries_today} entries today</span></div>
                      <span className="tag live"><span className="dot-live" />{l.inside.length} inside</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>

          <div className="card">
            <div className="card-head"><h3>Recent activity</h3><Link to="/audit" className="row" style={{ fontWeight: 600, fontSize: 13 }}>Full audit trail <ArrowRight size={15} /></Link></div>
            {data.recent_activity.length === 0 ? <Empty icon={Gauge} title="No activity yet" /> : (
              <ul className="list">
                {data.recent_activity.map((e) => (
                  <li key={e.id}>
                    <PlayCircle size={18} className="faint" />
                    <div className="grow"><b>{actionLabel(e.action)}{auditSummary(e) ? ` · ${auditSummary(e)}` : ''}</b><span>{e.actor}</span></div>
                    <span className="faint nowrap">{ago(e.ts)}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

function Kpi({ to, icon: Icon, tone, label, value, note }) {
  return (
    <Link to={to} className="card kpi link">
      <div className="label"><span className={`ico ${tone}`}><Icon size={17} /></span>{label}</div>
      <div className="value">{value}</div>
      <div className="note">{note}</div>
    </Link>
  )
}

function DashSkeleton() {
  return (
    <div className="stack">
      <div className="kpis">{[0, 1, 2, 3].map((i) => <Skeleton key={i} h={118} style={{ borderRadius: 14 }} />)}</div>
      <div className="grid cols-main"><Skeleton h={420} style={{ borderRadius: 14 }} /><Skeleton h={420} style={{ borderRadius: 14 }} /></div>
    </div>
  )
}
