import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { api, setUnauthorizedHandler, tokenStore } from './api'

const AuthCtx = createContext(null)
export const useAuth = () => useContext(AuthCtx)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [booting, setBooting] = useState(!!tokenStore.get())
  const [expired, setExpired] = useState(false)

  const logout = useCallback(() => { tokenStore.clear(); setUser(null) }, [])

  useEffect(() => {
    setUnauthorizedHandler(() => { tokenStore.clear(); setUser(null); setExpired(true) })
    if (!tokenStore.get()) return
    api.get('/api/auth/me').then(setUser).catch(() => tokenStore.clear()).finally(() => setBooting(false))
  }, [])

  const login = useCallback(async (email, password) => {
    const res = await api.post('/api/auth/login', { email, password })
    tokenStore.set(res.token); setExpired(false); setUser(res.user)
  }, [])

  const value = useMemo(() => ({
    user, booting, expired, login, logout,
    canWrite: (deptId) => !!user && (user.role === 'admin' || (user.role === 'incharge' && user.department_id === deptId)),
    isAdmin: user?.role === 'admin',
    readOnly: user?.role === 'head',
  }), [user, booting, expired, login, logout])

  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>
}
