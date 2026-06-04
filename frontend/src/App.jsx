import { Routes, Route, Navigate } from 'react-router-dom'
import { useEffect } from 'react'
import { AnimatePresence } from 'framer-motion'
import Sidebar from '@/components/Sidebar'
import Dashboard from '@/pages/Dashboard'
import CreateShort from '@/pages/CreateShort'
import Results from '@/pages/Results'
import Settings from '@/pages/Settings'

export default function App() {
  useEffect(() => {
    const apiUrl = import.meta.env.VITE_API_URL
    if (apiUrl) fetch(`${apiUrl}/health`).catch(() => {})
  }, [])

  return (
    <div className="flex min-h-screen bg-surface-900">
      {/* Mesh animated background */}
      <div className="mesh-bg" />

      {/* Sidebar (desktop left rail + mobile top/bottom nav) */}
      <Sidebar />

      {/* Main content — shifts right on desktop, has top/bottom padding on mobile */}
      <main className="flex-1 md:ml-64 min-h-screen overflow-y-auto pt-14 pb-16 md:pt-0 md:pb-0">
        <AnimatePresence mode="wait">
          <Routes>
            <Route path="/"          element={<Dashboard />} />
            <Route path="/create"    element={<CreateShort />} />
            <Route path="/results/:jobId" element={<Results />} />
            <Route path="/settings"  element={<Settings />} />
            <Route path="*"          element={<Navigate to="/" replace />} />
          </Routes>
        </AnimatePresence>
      </main>
    </div>
  )
}
