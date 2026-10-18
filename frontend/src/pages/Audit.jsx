import { useEffect, useState } from 'react'
import { Fingerprint, Loader2, Search, ShieldAlert, ShieldCheck } from 'lucide-react'
import { api } from '../api'
import { useAuth } from '../auth'
import { Empty, ErrorBox, Skeleton, useAsync } from '../components/ui'
import { actionLabel, detailText, fmtDateTime } from '../util'

const PAGE = 25
const ENTITIES = [['', 'All activity'], ['instrument', 'Instruments'], ['calibration', 'Calibrations'], ['lab', 'Lab access'], ['user', 'Users'], ['report', 'Exports']]

export default function Audit() {
  const { user } = useAuth()
  const [q, setQ] = useState('')
  const [dq, setDq] = useState('')
  const [entity, setEntity] = useState('')
  const [page, setPage] = useState(0)
  const [verify, setVerify] = useState(null) // null | 'running' | result
  const canVerify = user.role !== 'incharge'

  useEffect(() => { const t = setTimeout(() => { setDq(q); setPage(0) }, 300); return () => clearTimeout(t) }, [q])
  const { data, error, loading, reload } = useAsync(
    () => api.get(`/api/audit?limit=${PAGE}&offset=${page * PAGE}&entity=${entity}&q=${encodeURIComponent(dq)}`), [page, entity, dq])

  async function runVerify() {
    setVerify('running')
    try { await new Promise((r) => setTimeout(r, 500)); setVerify(await api.get('/api/audit/verify')) } catch (e) { setVerify({ error: e.message }) }
  }
  const pages = data ? Math.max(1, Math.ceil(data.total / PAGE)) : 1

  return (
    <div className="page">
      <div className="page-head">
        <div><h1>Audit trail</h1><p>Every change and access event, chained with SHA-256 so past entries can’t be edited unnoticed.</p></div>
        {canVerify && <div className="page-actions"><button className="btn primary" onClick={runVerify} disabled={verify === 'running'}>{verify === 'running' ? <Loader2 size={16} className="spin" style={{ animation: 'spin .8s linear infinite' }} /> : <Fingerprint size={17} />} Verify integrity</button></div>}
      </div>

      {verify && verify !== 'running' && (
        <div className={`banner ${verify.ok ? 'ok' : 'overdue'}`} role="status">
          {verify.ok ? <ShieldCheck size={26} /> : <ShieldAlert size={26} />}
          <div className="grow">
            {verify.error ? <b>{verify.error}</b> : verify.ok
              ? <><b>Chain intact</b><div>All {verify.checked} entries verified — no record has been altered or removed.</div></>
              : <><b>Tampering detected</b><div>The chain breaks at entry #{verify.broken_at}. {verify.checked} earlier entries verified.</div></>}
          </div>
        </div>
      )}

      <div className="card">
        <div className="filters">
          <div className="searchbox"><Search size={16} /><input className="input" placeholder="Search actor, asset tag, details…" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search audit trail" /></div>
          <select className="select" value={entity} onChange={(e) => { setEntity(e.target.value); setPage(0) }} aria-label="Filter by type">{ENTITIES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
        </div>
        {error ? <div style={{ padding: 20 }}><ErrorBox error={error} retry={reload} /></div> : !data ? <div style={{ padding: 20 }}><Skeleton h={300} /></div> : data.items.length === 0 ? (
          <Empty icon={ShieldCheck} title="No matching entries" />
        ) : (
          <>
            <div className="table-wrap" style={{ opacity: loading ? 0.6 : 1, transition: 'opacity .15s' }}><table className="t">
              <thead><tr><th>#</th><th>When</th><th>Who</th><th>Event</th><th>Details</th><th>Hash</th></tr></thead>
              <tbody>{data.items.map((e) => (
                <tr key={e.id}>
                  <td className="faint">{e.id}</td>
                  <td className="nowrap">{fmtDateTime(e.ts)}</td>
                  <td>{e.actor}</td>
                  <td><b style={{ fontWeight: 600 }}>{actionLabel(e.action)}</b></td>
                  <td className="muted" style={{ maxWidth: 360, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={detailText(e.detail)}>{detailText(e.detail)}</td>
                  <td className="hashline" title={e.hash}>{e.hash.slice(0, 10)}…</td>
                </tr>
              ))}</tbody>
            </table></div>
            <div className="t-foot">
              <span>{data.total} entries · page {page + 1} of {pages}</span>
              <span className="row"><button className="btn sm" disabled={page === 0} onClick={() => setPage(page - 1)}>Previous</button><button className="btn sm" disabled={page + 1 >= pages} onClick={() => setPage(page + 1)}>Next</button></span>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
