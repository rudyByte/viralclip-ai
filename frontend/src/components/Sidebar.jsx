import { NavLink, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  LayoutDashboard, Scissors, Settings, Zap,
  Sparkles, Github, ExternalLink
} from 'lucide-react'

const navItems = [
  { to: '/',        icon: LayoutDashboard, label: 'Dashboard'    },
  { to: '/create',  icon: Scissors,        label: 'Create'       },
  { to: '/settings',icon: Settings,        label: 'Settings'     },
]

export default function Sidebar() {
  const navigate = useNavigate()

  return (
    <>
      {/* ── Desktop Sidebar (hidden on mobile) ─────────────────── */}
      <aside className="hidden md:flex fixed left-0 top-0 h-full w-64 z-40 flex-col
                        border-r border-white/[0.06] bg-surface-800/80 backdrop-blur-xl">
        {/* Logo */}
        <div className="p-6 border-b border-white/[0.06]">
          <motion.button
            onClick={() => navigate('/')}
            className="flex items-center gap-3 w-full"
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
          >
            <div className="relative">
              <div className="w-10 h-10 rounded-xl bg-gradient-brand flex items-center justify-center glow-brand">
                <Zap className="w-5 h-5 text-white" fill="currentColor" />
              </div>
              <span className="absolute -top-1 -right-1 w-3 h-3 bg-neon-green rounded-full border-2 border-surface-800 animate-pulse-slow" />
            </div>
            <div className="text-left">
              <p className="font-display font-bold text-white text-lg leading-none">ViralClip</p>
              <p className="text-xs text-brand-400 font-medium mt-0.5">AI ✦ Free Forever</p>
            </div>
          </motion.button>
        </div>

        {/* Nav */}
        <nav className="flex-1 p-4 space-y-1">
          {navItems.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                `sidebar-link ${isActive ? 'active' : ''}`
              }
            >
              {({ isActive }) => (
                <>
                  <Icon className={`w-5 h-5 flex-shrink-0 ${isActive ? 'text-brand-400' : ''}`} />
                  <span>{label}</span>
                  {isActive && (
                    <motion.div
                      layoutId="nav-indicator"
                      className="ml-auto w-1.5 h-1.5 rounded-full bg-brand-400"
                    />
                  )}
                </>
              )}
            </NavLink>
          ))}
        </nav>

        {/* Stack badge */}
        <div className="p-4 space-y-2">
          <div className="glass rounded-xl p-3 text-xs space-y-1.5">
            <p className="text-slate-500 font-medium uppercase tracking-wider text-[10px]">Powered by</p>
            {['Groq LLaMA 3.3 70B', 'faster-whisper', 'FFmpeg', 'OpenCV'].map(t => (
              <div key={t} className="flex items-center gap-2">
                <Sparkles className="w-3 h-3 text-brand-400 flex-shrink-0" />
                <span className="text-slate-400">{t}</span>
              </div>
            ))}
          </div>

          <a
            href="https://github.com"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 px-3 py-2 rounded-lg text-slate-500 hover:text-slate-300
                       text-xs transition-colors hover:bg-white/5"
          >
            <Github className="w-4 h-4" />
            <span>Open Source</span>
            <ExternalLink className="w-3 h-3 ml-auto" />
          </a>
        </div>
      </aside>

      {/* ── Mobile Top Bar ──────────────────────────────────────── */}
      <header className="md:hidden fixed top-0 left-0 right-0 z-40 h-14 flex items-center justify-between px-4
                         border-b border-white/[0.06] bg-surface-800/90 backdrop-blur-xl">
        <button onClick={() => navigate('/')} className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-gradient-brand flex items-center justify-center">
            <Zap className="w-4 h-4 text-white" fill="currentColor" />
          </div>
          <span className="font-bold text-white text-base">ViralClip AI</span>
        </button>
        <span className="text-[10px] text-brand-400 font-semibold uppercase tracking-wider">Free Forever</span>
      </header>

      {/* ── Mobile Bottom Navigation Bar ───────────────────────── */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 z-40 h-16
                      border-t border-white/[0.06] bg-surface-800/95 backdrop-blur-xl
                      flex items-center justify-around px-2 safe-bottom">
        {navItems.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `flex flex-col items-center gap-0.5 px-4 py-2 rounded-xl transition-all
               ${isActive
                 ? 'text-brand-400 bg-brand-500/10'
                 : 'text-slate-500 hover:text-slate-300'
               }`
            }
          >
            {({ isActive }) => (
              <>
                <Icon className={`w-5 h-5 ${isActive ? 'text-brand-400' : ''}`} />
                <span className="text-[10px] font-semibold">{label}</span>
              </>
            )}
          </NavLink>
        ))}
      </nav>
    </>
  )
}
