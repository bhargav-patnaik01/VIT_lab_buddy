import { useState } from 'react'
import { CalendarClock, DoorOpen, Eye, EyeOff, Gauge, ShieldCheck } from 'lucide-react'
import { useAuth } from '../auth'

const DEMO = [
  ['Administrator', 'admin@vit.ac.in', 'Full access'],
  ['Department head', 'head@vit.ac.in', 'Read-only, all labs'],
  ['Electronics in-charge', 'electronics@vit.ac.in', 'Own lab only'],
  ['Mechanical in-charge', 'mechanical@vit.ac.in', 'Own lab only'],
]

export default function Login() {
  const { login, expired } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [show, setShow] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const showDemo = ['localhost', '127.0.0.1'].includes(window.location.hostname)

  async function submit(e) {
    e.preventDefault()
    setBusy(true); setError('')
    try { await login(email, password) } catch (err) { setError(err.message); setBusy(false) }
  }

  return (
    <div className="login">
      <section className="login-hero">
        <img className="logo" src="/vit-logo.png" alt="Vellore Institute of Technology" />
        <div>
          <h1>Every instrument calibrated. <em>Every record defensible.</em></h1>
          <p>One place for VIT’s laboratories to track calibration schedules, certificates, equipment usage and lab access — ready for NBA and NAAC audits.</p>
          <div className="feat">
            <div><CalendarClock size={20} /> Automatic due-date tracking, by date or by hours of use</div>
            <div><ShieldCheck size={20} /> Department-scoped access and a tamper-evident audit trail</div>
            <div><Gauge size={20} /> Usage logs that show how hard each instrument is worked</div>
            <div><DoorOpen size={20} /> Lab entry swipes linked to equipment activity</div>
          </div>
        </div>
        <small>Vellore Institute of Technology · Laboratory Management</small>
      </section>

      <section className="login-panel">
        <div className="login-card">
          <h2>Sign in</h2>
          <p className="lead">Use your institute account to continue.</p>
          <form onSubmit={submit} className="stack" style={{ gap: 16 }}>
            {expired && !error && <div className="alert">Your session expired. Please sign in again.</div>}
            {error && <div className="alert" role="alert">{error}</div>}
            <div className="field">
              <label htmlFor="email">Email</label>
              <input id="email" className="input" type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="name@vit.ac.in" autoFocus />
            </div>
            <div className="field">
              <label htmlFor="pw">Password</label>
              <div style={{ position: 'relative' }}>
                <input id="pw" className="input" type={show ? 'text' : 'password'} autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} style={{ paddingRight: 44 }} />
                <button type="button" className="icon-btn" onClick={() => setShow(!show)} aria-label={show ? 'Hide password' : 'Show password'} style={{ position: 'absolute', right: 2, top: 2 }}>
                  {show ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </div>
            <button className="btn primary" style={{ height: 44 }} disabled={busy}>{busy ? <span className="spinner" /> : 'Sign in'}</button>
          </form>

          {showDemo && (
            <div className="demo">
              <h4>Demo accounts · password Vit@2026</h4>
              <div className="demo-grid">
                {DEMO.map(([label, mail, note]) => (
                  <button key={mail} type="button" className="demo-btn" onClick={() => { setEmail(mail); setPassword('Vit@2026'); setError('') }}>
                    <b>{label}</b><span>{note}</span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </section>
    </div>
  )
}
