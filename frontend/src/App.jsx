import { Routes, Route, Navigate } from 'react-router-dom'
import { AnimatePresence } from 'framer-motion'
import Sidebar from '@/components/Sidebar'
import Dashboard from '@/pages/Dashboard'
import CreateShort from '@/pages/CreateShort'
import Results from '@/pages/Results'
import Settings from '@/pages/Settings'

export default function App() {
  return (
    <div className="flex min-h-screen bg-surface-900">
      {/* Mesh animated background */}
      <div className="mesh-bg" />

      {/* Sidebar */}
      <Sidebar />

      {/* Main content */}
      <main className="flex-1 ml-64 min-h-screen overflow-y-auto">
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
