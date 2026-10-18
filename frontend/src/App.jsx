import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuth } from './auth'
import Layout from './components/Layout'
import { Skeleton } from './components/ui'
import Access from './pages/Access'
import Admin from './pages/Admin'
import Audit from './pages/Audit'
import Dashboard from './pages/Dashboard'
import InstrumentDetail from './pages/InstrumentDetail'
import Instruments from './pages/Instruments'
import Login from './pages/Login'
import Schedule from './pages/Schedule'

export default function App() {
  const { user, booting, isAdmin } = useAuth()
  if (booting) return <div style={{ padding: 40 }}><Skeleton h={30} w={260} /></div>
  if (!user) return <Login />
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="instruments" element={<Instruments />} />
        <Route path="instruments/:id" element={<InstrumentDetail />} />
        <Route path="schedule" element={<Schedule />} />
        <Route path="access" element={<Access />} />
        <Route path="audit" element={<Audit />} />
        {isAdmin && <Route path="admin" element={<Admin />} />}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
