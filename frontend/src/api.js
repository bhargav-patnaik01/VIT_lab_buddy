// Thin fetch wrapper. All calls are relative (/api/...): Vite proxies them in dev, CloudFront routes them to API Gateway on AWS.
const BASE = import.meta.env.VITE_API_BASE || ''
const KEY = 'cad.token'

export const tokenStore = {
  get: () => { try { return localStorage.getItem(KEY) } catch { return null } },
  set: (t) => { try { localStorage.setItem(KEY, t) } catch { /* private mode */ } },
  clear: () => { try { localStorage.removeItem(KEY) } catch { /* ignore */ } },
}

let onUnauthorized = () => {}
export const setUnauthorizedHandler = (fn) => { onUnauthorized = fn }

export class ApiError extends Error {
  constructor(message, status) { super(message); this.status = status }
}

function describe(detail) {
  if (!detail) return 'Something went wrong'
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail.map((d) => {
      const field = Array.isArray(d.loc) ? d.loc.filter((x) => x !== 'body').join(' › ') : ''
      return field ? `${field}: ${d.msg}` : d.msg
    }).join('; ')
  }
  return 'Something went wrong'
}

async function request(method, path, body, opts = {}) {
  const headers = {}
  const token = tokenStore.get()
  if (token) headers.Authorization = `Bearer ${token}`
  let payload
  if (body instanceof FormData) payload = body
  else if (body !== undefined) { headers['Content-Type'] = 'application/json'; payload = JSON.stringify(body) }

  let res
  try {
    res = await fetch(BASE + path, { method, headers, body: payload })
  } catch {
    throw new ApiError('Cannot reach the server. Check your connection and try again.', 0)
  }
  if (opts.raw && res.ok) return res
  let data = null
  try { data = await res.json() } catch { /* empty body */ }
  if (!res.ok) {
    if (res.status === 401 && !path.startsWith('/api/auth/login')) onUnauthorized()
    throw new ApiError(describe(data?.detail), res.status)
  }
  return data
}

export const api = {
  get: (p) => request('GET', p),
  post: (p, b) => request('POST', p, b ?? {}),
  put: (p, b) => request('PUT', p, b),
  form: (p, fd) => request('POST', p, fd),
  async download(path, filename) {
    const res = await request('GET', path, undefined, { raw: true })
    const url = URL.createObjectURL(await res.blob())
    const a = document.createElement('a')
    a.href = url; a.download = filename; document.body.appendChild(a); a.click(); a.remove()
    setTimeout(() => URL.revokeObjectURL(url), 2000)
  },
}
