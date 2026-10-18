import { STATUS, STATUS_ORDER } from '../util'

export function ComplianceRing({ counts, total, pct }) {
  const r = 62, c = 2 * Math.PI * r
  const segs = []
  let offset = 0
  for (const k of STATUS_ORDER) {
    const n = counts[k] || 0
    if (!n || !total) continue
    const len = (n / total) * c
    segs.push(<circle key={k} cx="74" cy="74" r={r} fill="none" stroke={STATUS[k].color} strokeWidth="16" strokeDasharray={`${Math.max(len - 2, 0)} ${c}`} strokeDashoffset={-offset} />)
    offset += len
  }
  return (
    <div className="ring">
      <svg viewBox="0 0 148 148" width="148" height="148" role="img" aria-label={`${pct}% of instruments within calibration`}>
        <circle cx="74" cy="74" r={r} fill="none" stroke="#eef1f7" strokeWidth="16" />
        <g transform="rotate(-90 74 74)">{segs}</g>
      </svg>
      <div className="center"><b>{pct}%</b><span>in calibration</span></div>
    </div>
  )
}

export function StackedBar({ row }) {
  const segs = STATUS_ORDER.filter((k) => row[k] > 0)
  return (
    <div className="sbar" role="img" aria-label={segs.map((k) => `${row[k]} ${STATUS[k].label}`).join(', ') || 'No instruments'}>
      {segs.map((k) => <i key={k} title={`${STATUS[k].label}: ${row[k]}`} style={{ flex: row[k], background: STATUS[k].color }} />)}
    </div>
  )
}

export function UsageBars({ daily }) {
  const max = Math.max(1, ...daily.map((d) => d.hours))
  return (
    <>
      <div className="bars" role="img" aria-label="Hours of use per day">
        {daily.map((d) => (
          <div key={d.date} className={`b ${d.hours ? '' : 'zero'}`} style={{ height: `${d.hours ? Math.max(6, (d.hours / max) * 100) : 3}%` }} title={`${d.date}: ${d.hours} h`} />
        ))}
      </div>
      <div className="bars-axis"><span>{daily[0]?.date.slice(5)}</span><span>peak {max.toFixed(1)} h/day</span><span>{daily.at(-1)?.date.slice(5)}</span></div>
    </>
  )
}
