import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { 
  Settings as SettingsIcon, Shield, Server, FileText, Cpu, Check, 
  HelpCircle, AlertCircle, RefreshCw, FolderOpen, Info 
} from 'lucide-react'
import { getConfig, healthCheck } from '@/lib/api'
import toast from 'react-hot-toast'

export default function Settings() {
  const [config, setConfig] = useState(null)
  const [health, setHealth] = useState(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)

  const fetchSettingsData = async (silent = false) => {
    if (!silent) setLoading(true)
    else setRefreshing(true)

    try {
      const configData = await getConfig()
      setConfig(configData)
      
      const healthData = await healthCheck()
      setHealth(healthData)
    } catch (err) {
      console.error(err)
      toast.error('Failed to load system configurations')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  useEffect(() => {
    fetchSettingsData()
  }, [])

  return (
    <motion.div 
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -15 }}
      transition={{ duration: 0.35, ease: 'easeOut' }}
      className="p-8 max-w-4xl mx-auto space-y-8"
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-extrabold text-white flex items-center gap-2">
            <SettingsIcon className="w-8 h-8 text-brand-400" />
            <span>System Settings</span>
          </h1>
          <p className="text-slate-400 mt-1">
            View active model configurations, API keys integration, and system environment stats.
          </p>
        </div>

        <button
          onClick={() => fetchSettingsData(true)}
          disabled={refreshing}
          className="p-2.5 rounded-xl border border-white/10 hover:bg-white/5 active:scale-95 transition-all text-slate-400 hover:text-white"
        >
          <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {loading ? (
        <div className="space-y-6">
          {[1, 2].map(i => (
            <div key={i} className="glass rounded-2xl p-8 shimmer h-48" />
          ))}
        </div>
      ) : (
        <div className="space-y-6">
          
          {/* Section 1: API and Service Status */}
          <div className="glass rounded-2xl p-6 space-y-6">
            <h3 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2 border-b border-white/[0.06] pb-3">
              <Shield className="w-4.5 h-4.5 text-brand-400" />
              <span>Service Connections</span>
            </h3>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              
              {/* Groq Cloud Connection */}
              <div className="flex items-center justify-between p-4 rounded-xl bg-surface-900/50 border border-white/[0.04]">
                <div>
                  <h4 className="font-bold text-white text-sm">Groq AI API Integration</h4>
                  <p className="text-xs text-slate-400 mt-1">Powering virality analysis (LLaMA 3.3 70B)</p>
                </div>
                {health?.groq_configured ? (
                  <span className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 border border-emerald-500/30 text-emerald-400">
                    <Check className="w-3.5 h-3.5" />
                    <span>Configured</span>
                  </span>
                ) : (
                  <span className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-pink-500/10 border border-pink-500/30 text-pink-400">
                    <AlertCircle className="w-3.5 h-3.5" />
                    <span>Missing Key</span>
                  </span>
                )}
              </div>

              {/* Whisper Transcriber */}
              <div className="flex items-center justify-between p-4 rounded-xl bg-surface-900/50 border border-white/[0.04]">
                <div>
                  <h4 className="font-bold text-white text-sm">Whisper Model</h4>
                  <p className="text-xs text-slate-400 mt-1">Generating word-level speech transcriptions</p>
                </div>
                <span className="px-3 py-1 rounded-full text-xs font-semibold bg-indigo-500/10 border border-indigo-500/30 text-indigo-400">
                  {config?.whisper_model || health?.whisper_model || 'small'}
                </span>
              </div>

            </div>

            {!health?.groq_configured && (
              <div className="flex gap-2.5 items-start bg-pink-500/5 border border-pink-500/20 rounded-xl p-4 text-xs text-pink-300">
                <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                <p className="leading-relaxed">
                  <strong>Missing API Key:</strong> To detect viral moments, you must create a <code>.env</code> file in your <code>backend</code> directory and add your <code>GROQ_API_KEY</code>. You can obtain a free key from the Groq Console.
                </p>
              </div>
            )}
          </div>

          {/* Section 2: Pipeline Defaults */}
          <div className="glass rounded-2xl p-6 space-y-4">
            <h3 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2 border-b border-white/[0.06] pb-3">
              <Cpu className="w-4.5 h-4.5 text-brand-400" />
              <span>Pipeline Defaults & Limits</span>
            </h3>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              
              <div className="p-4 rounded-xl bg-surface-900/50 border border-white/[0.04]">
                <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">Concurrency</span>
                <span className="text-lg font-extrabold text-white mt-1 block">{config?.max_concurrent_jobs} jobs</span>
              </div>

              <div className="p-4 rounded-xl bg-surface-900/50 border border-white/[0.04]">
                <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">Target FPS</span>
                <span className="text-lg font-extrabold text-white mt-1 block">{config?.export_fps} fps</span>
              </div>

              <div className="p-4 rounded-xl bg-surface-900/50 border border-white/[0.04]">
                <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">Resolution</span>
                <span className="text-lg font-extrabold text-white mt-1 block">{config?.export_resolution}</span>
              </div>

              <div className="p-4 rounded-xl bg-surface-900/50 border border-white/[0.04]">
                <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">Default Clips</span>
                <span className="text-lg font-extrabold text-white mt-1 block">{config?.default_num_clips} per run</span>
              </div>

            </div>
          </div>

          {/* Section 3: Gameplay Assets Guide */}
          <div className="glass rounded-2xl p-6 space-y-4">
            <h3 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2 border-b border-white/[0.06] pb-3">
              <FolderOpen className="w-4.5 h-4.5 text-brand-400" />
              <span>Gameplay Overlay Asset Guide</span>
            </h3>

            <div className="space-y-3 text-xs leading-relaxed text-slate-400">
              <p>
                ViralClip AI stacks a gameplay video under the cropped camera view to boost engagement and watch time. The backend automatically looks for gameplay loop files in these locations:
              </p>
              
              <ul className="space-y-2 mt-2 bg-surface-900/50 border border-white/[0.04] p-4 rounded-xl font-mono text-slate-300">
                <li>🏄‍♂️ Subway Surfers: <code className="text-indigo-400">assets/gameplay/subway/</code></li>
                <li>🧱 Minecraft Parkour: <code className="text-indigo-400">assets/gameplay/minecraft/</code></li>
                <li>🚗 GTA V Stunts: <code className="text-indigo-400">assets/gameplay/gta/</code></li>
                <li>🏃‍♂️ Temple Run: <code className="text-indigo-400">assets/gameplay/templerun/</code></li>
              </ul>

              <div className="flex gap-2 items-start bg-indigo-500/5 border border-indigo-500/10 rounded-xl p-3 text-slate-400">
                <Info className="w-4 h-4 text-brand-400 flex-shrink-0 mt-0.5" />
                <p>
                  <strong>Tip:</strong> Drop high-quality portrait/landscape gameplay videos (mp4 format) inside those folders. If multiple files are placed in a folder, the mixer selects a random one during compilation.
                </p>
              </div>
            </div>
          </div>

          {/* Section 4: System Information */}
          <div className="glass rounded-2xl p-6 space-y-3 text-xs">
            <div className="flex justify-between border-b border-white/[0.04] pb-2 text-slate-400">
              <span>App Core Version</span>
              <span className="font-mono text-white font-bold">{health?.version || '1.0.0'}</span>
            </div>
            <div className="flex justify-between border-b border-white/[0.04] pb-2 text-slate-400">
              <span>Environment Mode</span>
              <span className="font-mono text-white font-bold">Local Development</span>
            </div>
            <div className="flex justify-between text-slate-400">
              <span>FastAPI Port</span>
              <span className="font-mono text-white font-bold">8000</span>
            </div>
          </div>

        </div>
      )}
    </motion.div>
  )
}
