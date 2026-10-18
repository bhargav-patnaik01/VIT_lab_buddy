import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import { AlertCircle, CheckCircle2, X } from 'lucide-react'
import { STATUS } from '../util'

export function StatusPill({ status }) {
  const s = STATUS[status] || { label: status }
  return <span className={`pill ${status}`}>{s.label}</span>
}

// ---- data loading hook
export function useAsync(fn, deps = []) {
  const [state, set] = useState({ data: null, error: null, loading: true })
  const alive = useRef(true)
  const run = useCallback(() => {
    set((s) => ({ ...s, loading: true, error: null }))
    return fn().then(
      (data) => alive.current && set({ data, error: null, loading: false }),
      (error) => alive.current && set({ data: null, error, loading: false }),
    )
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)
  useEffect(() => { alive.current = true; run(); return () => { alive.current = false } }, [run])
  return { ...state, reload: run }
}

export function Skeleton({ h = 20, w = '100%', style }) {
  return <div className="skeleton" style={{ height: h, width: w, ...style }} />
}

export function Empty({ icon: Icon, title, children }) {
  return (
    <div className="empty">
      {Icon && <Icon size={40} strokeWidth={1.5} />}
      <b>{title}</b>
      <div>{children}</div>
    </div>
  )
}

export function ErrorBox({ error, retry }) {
  return (
    <div className="alert row" role="alert" style={{ justifyContent: 'space-between' }}>
      <span className="row"><AlertCircle size={18} /> {error?.message || 'Failed to load'}</span>
      {retry && <button className="btn sm" onClick={retry}>Retry</button>}
    </div>
  )
}

export function Field({ label, hint, children, className = '' }) {
  return (
    <div className={`field ${className}`}>
      <label>{label}</label>
      {children}
      {hint && <span className="hint">{hint}</span>}
    </div>
  )
}

// ---- modal / drawer
function useEscape(onClose) {
  useEffect(() => {
    const h = (e) => e.key === 'Escape' && onClose()
    document.addEventListener('keydown', h)
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => { document.removeEventListener('keydown', h); document.body.style.overflow = prev }
  }, [onClose])
}

export function Modal({ title, onClose, children, footer, drawer = false }) {
  useEscape(onClose)
  const Box = drawer ? 'drawer' : 'dialog'
  return (
    <div className={`overlay ${drawer ? '' : 'center'}`} onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className={Box} role="dialog" aria-modal="true" aria-label={title}>
        <div className="modal-head">
          <h3>{title}</h3>
          <button className="icon-btn" onClick={onClose} aria-label="Close"><X size={20} /></button>
        </div>
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-foot">{footer}</div>}
      </div>
    </div>
  )
}

// ---- toasts
const ToastCtx = createContext(() => {})
export const useToast = () => useContext(ToastCtx)

export function ToastProvider({ children }) {
  const [items, setItems] = useState([])
  const push = useCallback((message, kind = 'ok') => {
    const id = Math.random()
    setItems((x) => [...x, { id, message, kind }])
    setTimeout(() => setItems((x) => x.filter((i) => i.id !== id)), 4200)
  }, [])
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="toasts" aria-live="polite">
        {items.map((t) => (
          <div key={t.id} className={`toast ${t.kind === 'err' ? 'err' : ''}`}>
            {t.kind === 'err' ? <AlertCircle size={18} /> : <CheckCircle2 size={18} />} {t.message}
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  )
}
