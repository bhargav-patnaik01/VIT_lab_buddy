export const STATUS = {
  ok: { label: 'Calibrated', color: '#19a35f' },
  due_soon: { label: 'Due soon', color: '#e8a317' },
  overdue: { label: 'Overdue', color: '#d92d20' },
  failed: { label: 'Failed', color: '#a3265f' },
  uncalibrated: { label: 'Not calibrated', color: '#8a97ad' },
  out_of_service: { label: 'Out of service', color: '#aab0bd' },
  retired: { label: 'Retired', color: '#aab0bd' },
}
export const STATUS_ORDER = ['ok', 'due_soon', 'overdue', 'failed', 'uncalibrated', 'out_of_service']

export const ROLE_LABEL = { admin: 'Administrator', head: 'Department head', incharge: 'Lab in-charge' }

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

// 'YYYY-MM-DD' -> '18 Oct 2026' (parsed manually: new Date('2026-10-18') would shift with the timezone)
export function fmtDate(d) {
  if (!d) return '—'
  const [y, m, day] = String(d).slice(0, 10).split('-').map(Number)
  return `${day} ${MONTHS[m - 1]} ${y}`
}
export const dateParts = (d) => { const [, m, day] = String(d).slice(0, 10).split('-').map(Number); return { day, mon: MONTHS[m - 1] } }
export const monthKey = (d) => { const [y, m] = String(d).slice(0, 10).split('-').map(Number); return `${MONTHS[m - 1]} ${y}` }

export function fmtDateTime(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', hour12: true })
}
export function fmtTime(iso) {
  return new Date(iso).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: true })
}
export function ago(iso) {
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000)
  if (s < 60) return 'just now'
  if (s < 3600) return `${Math.floor(s / 60)} min ago`
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`
  return `${Math.floor(s / 86400)} d ago`
}
export const fmtHours = (h) => (h == null ? '—' : `${Number(h).toLocaleString('en-IN', { maximumFractionDigits: 1 })} h`)
export const todayISO = () => { const d = new Date(); return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10) }
const TITLES = new Set(['prof.', 'dr.', 'mr.', 'ms.', 'mrs.'])
const nameWords = (name = '') => name.split(/\s+/).filter((w) => w && !TITLES.has(w.toLowerCase()))
export const initials = (name = '') => nameWords(name).slice(0, 2).map((w) => w[0].toUpperCase()).join('')
export const firstName = (name = '') => nameWords(name)[0] || name

export function dueText(due) {
  if (!due) return ''
  const parts = []
  if (due.days_remaining != null) parts.push(due.days_remaining < 0 ? `${-due.days_remaining} d overdue` : due.days_remaining === 0 ? 'due today' : `${due.days_remaining} d left`)
  if (due.hours_remaining != null) parts.push(due.hours_remaining <= 0 ? `${Math.abs(due.hours_remaining)} h over limit` : `${due.hours_remaining} h left`)
  return parts.join(' · ')
}

const ACTIONS = {
  login: 'Signed in', 'instrument.create': 'Added instrument', 'instrument.update': 'Edited instrument', 'calibration.record': 'Recorded calibration',
  'certificate.view': 'Viewed certificate', 'usage.start': 'Started usage session', 'usage.stop': 'Ended usage session', 'usage.log': 'Logged usage',
  'access.in': 'Lab entry', 'access.out': 'Lab exit', 'user.create': 'Created user', 'user.update': 'Updated user',
  'department.create': 'Created department', 'department.update': 'Updated department', 'scan.run': 'Ran due-date scan', 'report.export': 'Exported report',
}
export const actionLabel = (a) => ACTIONS[a] || a

// '{"asset_tag":"X","result":"pass"}' -> 'asset tag: X · result: pass'
export function detailText(raw) {
  if (!raw || raw === '{}') return ''
  try {
    return Object.entries(JSON.parse(raw)).map(([k, v]) => `${k.replace(/_/g, ' ')}: ${Array.isArray(v) ? v.join(', ') : typeof v === 'object' && v ? JSON.stringify(v) : v}`).join(' · ')
  } catch { return raw }
}

export function auditSummary(e) {
  let d = {}
  try { d = JSON.parse(e.detail || '{}') } catch { /* free text */ }
  return d.asset_tag || d.name || d.email || d.person || d.code || (typeof d.rows === 'number' ? `${d.rows} rows` : '') || ''
}
