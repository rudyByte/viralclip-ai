import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { Settings as SettingsIcon, Cookie, CheckCircle2, Trash2, Save, Loader2, AlertTriangle, Wifi } from 'lucide-react'
import { getCookiesStatus, saveCookies, deleteCookies, getPoTokenStatus, savePoToken, deletePoToken, healthCheck, API_BASE } from '@/lib/api'
import { loadDefaults, saveDefaults, resetDefaults, defaultSettings } from '@/lib/settings'
import toast from 'react-hot-toast'

export default function Settings() {
  const [cookiesText, setCookiesText] = useState('')
  const [poTokenText, setPoTokenText] = useState('')
  const [status, setStatus] = useState(null)  // {saved: bool}
  const [poTokenStatus, setPoTokenStatus] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [savingPoToken, setSavingPoToken] = useState(false)
  const [health, setHealth] = useState(null)
  const [defaults, setDefaults] = useState(loadDefaults())

  useEffect(() => {
    getCookiesStatus()
      .then(setStatus)
      .catch(() => setStatus({ saved: false }))
      .finally(() => setLoading(false))
    getPoTokenStatus()
      .then(setPoTokenStatus)
      .catch(() => setPoTokenStatus({ saved: false }))
  }, [])

  const checkHealth = async () => {
    setHealth({ loading: true })
    try {
      const data = await healthCheck()
      setHealth({ ok: true, data })
    } catch {
      setHealth({ ok: false })
    }
  }

  const handleSave = async () => {
    if (!cookiesText.trim()) return toast.error('Paste your cookies text first')
    setSaving(true)
    try {
      const res = await saveCookies(cookiesText)
      if (res.success) {
        toast.success('Cookies saved! All future jobs will use them.')
        setStatus({ saved: true })
        setCookiesText('')
      } else {
        toast.error(res.error || 'Failed to save cookies')
      }
    } catch {
      toast.error('Failed to reach backend')
    } finally {
      setSaving(false)
    }
  }

  const updateDefault = (key, value) => {
    setDefaults(prev => ({ ...prev, [key]: value }))
  }

  const handleSaveDefaults = () => {
    saveDefaults(defaults)
    toast.success('Default job settings saved')
  }

  const handleResetDefaults = () => {
    resetDefaults()
    setDefaults(defaultSettings)
    toast.success('Factory defaults restored')
  }

  const handleDelete = async () => {
    try {
      await deleteCookies()
      setStatus({ saved: false })
      toast.success('Cookies removed')
    } catch {
      toast.error('Failed to delete cookies')
    }
  }

  const handleSavePoToken = async () => {
    if (!poTokenText.trim()) return toast.error('Paste your PO Token first')
    setSavingPoToken(true)
    try {
      const res = await savePoToken(poTokenText)
      if (res.success) {
        toast.success('PO Token saved')
        setPoTokenStatus({ saved: true })
        setPoTokenText('')
      } else {
        toast.error(res.error || 'Failed to save PO Token')
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to save PO Token')
    } finally {
      setSavingPoToken(false)
    }
  }

  const handleDeletePoToken = async () => {
    try {
      await deletePoToken()
      setPoTokenStatus({ saved: false })
      toast.success('PO Token removed')
    } catch {
      toast.error('Failed to delete PO Token')
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -15 }}
      transition={{ duration: 0.3 }}
      className="p-4 md:p-8 max-w-3xl mx-auto space-y-8"
    >
      <div>
        <h1 className="text-3xl font-extrabold text-white flex items-center gap-2">
          <SettingsIcon className="w-8 h-8 text-brand-400" />
          Settings
        </h1>
        <p className="text-slate-400 mt-1">Configure global backend settings for all jobs.</p>
      </div>

      <div className="glass rounded-2xl p-6 space-y-4">
        <div className="flex items-center gap-2">
          <Wifi className="w-5 h-5 text-brand-400" />
          <h2 className="text-white font-bold text-lg">Backend Connection</h2>
        </div>
        <div className="rounded-xl bg-surface-900 border border-white/10 p-3 text-xs font-mono text-slate-300 break-all">
          {API_BASE}
        </div>
        <div className="flex flex-col sm:flex-row gap-3 sm:items-center">
          <button onClick={checkHealth} className="btn-primary flex items-center justify-center gap-2 px-5 py-3">
            {health?.loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Wifi className="w-4 h-4" />}
            Check Health
          </button>
          {health?.ok && (
            <span className="text-green-400 text-sm font-semibold">
              Online - Groq {health.data?.groq_configured ? 'configured' : 'missing'}
            </span>
          )}
          {health && !health.loading && !health.ok && (
            <span className="text-yellow-400 text-sm font-semibold">Server may be waking up. Try again in 30-90s.</span>
          )}
        </div>
      </div>

      {/* YouTube Cookies Card */}
      <div className="glass rounded-2xl p-6 space-y-5">
        <div className="flex items-center gap-2">
          <Cookie className="w-5 h-5 text-brand-400" />
          <h2 className="text-white font-bold text-lg">YouTube Cookies</h2>
        </div>

        {/* Status badge */}
        {loading ? (
          <div className="flex items-center gap-2 text-slate-400 text-sm"><Loader2 className="w-4 h-4 animate-spin" /> Checking...</div>
        ) : status?.saved ? (
          <div className="flex items-center justify-between p-3 rounded-xl bg-green-500/10 border border-green-500/30">
            <div className="flex items-center gap-2 text-green-400 text-sm font-semibold">
              <CheckCircle2 className="w-4 h-4" />
              Cookies are saved on the server — all jobs will use them automatically.
            </div>
            <button
              onClick={handleDelete}
              className="flex items-center gap-1 text-xs text-red-400 hover:text-red-300 transition-colors ml-4"
            >
              <Trash2 className="w-3.5 h-3.5" /> Remove
            </button>
          </div>
        ) : (
          <div className="flex items-center gap-2 p-3 rounded-xl bg-yellow-500/10 border border-yellow-500/30 text-yellow-400 text-sm">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            No cookies saved. YouTube may block downloads from cloud servers without them.
          </div>
        )}

        {/* Instructions */}
        <div className="space-y-2 text-sm text-slate-400">
          <p className="font-semibold text-white text-sm">How to get your cookies (do this on your PC):</p>
          <ol className="list-decimal list-inside space-y-1 ml-1">
            <li>Open <strong className="text-white">Chrome</strong> on your PC and go to <strong className="text-white">youtube.com</strong> while logged in</li>
            <li>Install the <strong className="text-white">"Get cookies.txt LOCALLY"</strong> extension from Chrome Web Store</li>
            <li>Click the extension icon → <strong className="text-white">Export</strong> → copy all the text</li>
            <li>Paste it in the box below and click <strong className="text-white">Save to Server</strong></li>
          </ol>
          <p className="text-xs text-slate-500 pt-1">✓ Saved cookies persist across all future jobs including from your phone. You only need to do this once.</p>
        </div>

        {/* Textarea */}
        <div className="space-y-2">
          <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider block">
            Paste Netscape cookies.txt content
          </label>
          <textarea
            placeholder={`# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tFALSE\t...\n...`}
            value={cookiesText}
            onChange={(e) => setCookiesText(e.target.value)}
            rows={7}
            className="w-full px-3 py-2 rounded-xl bg-surface-900 border border-white/10 text-white placeholder-slate-600 focus:outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 transition-all font-mono text-xs resize-y"
          />
        </div>

        <button
          onClick={handleSave}
          disabled={saving || !cookiesText.trim()}
          className="btn-primary flex items-center gap-2 px-6 py-3 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
          {saving ? 'Saving...' : 'Save to Server'}
        </button>
      </div>

      <div className="glass rounded-2xl p-6 space-y-5">
        <div className="flex items-center gap-2">
          <Cookie className="w-5 h-5 text-brand-400" />
          <h2 className="text-white font-bold text-lg">YouTube PO Token</h2>
        </div>

        {poTokenStatus?.saved ? (
          <div className="flex items-center justify-between p-3 rounded-xl bg-green-500/10 border border-green-500/30">
            <div className="flex items-center gap-2 text-green-400 text-sm font-semibold">
              <CheckCircle2 className="w-4 h-4" />
              PO Token saved on server. HF downloads will try mweb + PO Token fallback.
            </div>
            <button
              onClick={handleDeletePoToken}
              className="flex items-center gap-1 text-xs text-red-400 hover:text-red-300 transition-colors ml-4"
            >
              <Trash2 className="w-3.5 h-3.5" /> Remove
            </button>
          </div>
        ) : (
          <div className="flex items-center gap-2 p-3 rounded-xl bg-yellow-500/10 border border-yellow-500/30 text-yellow-400 text-sm">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            No PO Token saved. HF may still hit YouTube datacenter bot blocks.
          </div>
        )}

        <div className="space-y-2 text-sm text-slate-400">
          <p className="font-semibold text-white text-sm">How to get a PO Token:</p>
          <ol className="list-decimal list-inside space-y-1 ml-1">
            <li>Open youtube.com in your desktop browser.</li>
            <li>Open DevTools Console.</li>
            <li>Run: <code className="text-xs bg-surface-900 px-1 py-0.5 rounded text-slate-200">(await (await fetch('/youtubei/v1/visitor_id')).json())</code></li>
            <li>Paste the token value below. Prefixes like <code className="text-xs bg-surface-900 px-1 py-0.5 rounded text-slate-200">mweb.gvs+</code> are accepted.</li>
          </ol>
          <a
            href="https://github.com/Brainicism/bgutil-ytdlp-pot-provider"
            target="_blank"
            rel="noreferrer"
            className="text-brand-400 hover:text-brand-300 text-xs font-semibold"
          >
            bgutil-ytdlp-pot-provider
          </a>
        </div>

        <div className="space-y-2">
          <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider block">
            Paste PO Token
          </label>
          <textarea
            placeholder="mweb.gvs+TOKEN or raw TOKEN"
            value={poTokenText}
            onChange={(e) => setPoTokenText(e.target.value)}
            rows={4}
            className="w-full px-3 py-2 rounded-xl bg-surface-900 border border-white/10 text-white placeholder-slate-600 focus:outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 transition-all font-mono text-xs resize-y"
          />
        </div>

        <button
          onClick={handleSavePoToken}
          disabled={savingPoToken || !poTokenText.trim()}
          className="btn-primary flex items-center gap-2 px-6 py-3 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {savingPoToken ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
          {savingPoToken ? 'Saving...' : 'Save PO Token'}
        </button>
      </div>

      <div className="glass rounded-2xl p-6 space-y-5">
        <div className="flex items-center gap-2">
          <SettingsIcon className="w-5 h-5 text-brand-400" />
          <h2 className="text-white font-bold text-lg">Default Job Settings</h2>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <label className="space-y-1">
            <span className="text-xs font-semibold text-slate-400 uppercase">Min Duration</span>
            <input type="number" min="15" max="60" value={defaults.clipMinDuration}
              onChange={e => updateDefault('clipMinDuration', Number(e.target.value))}
              className="w-full px-3 py-2 rounded-xl bg-surface-900 border border-white/10 text-white" />
          </label>
          <label className="space-y-1">
            <span className="text-xs font-semibold text-slate-400 uppercase">Max Duration</span>
            <input type="number" min="30" max="90" value={defaults.clipMaxDuration}
              onChange={e => updateDefault('clipMaxDuration', Number(e.target.value))}
              className="w-full px-3 py-2 rounded-xl bg-surface-900 border border-white/10 text-white" />
          </label>
          <label className="space-y-1">
            <span className="text-xs font-semibold text-slate-400 uppercase">Clips</span>
            <input type="number" min="1" max="20" value={defaults.numClips}
              onChange={e => updateDefault('numClips', Number(e.target.value))}
              className="w-full px-3 py-2 rounded-xl bg-surface-900 border border-white/10 text-white" />
          </label>
          <label className="space-y-1">
            <span className="text-xs font-semibold text-slate-400 uppercase">Default Layout</span>
            <select value={defaults.layoutTemplate} onChange={e => updateDefault('layoutTemplate', e.target.value)}
              className="w-full px-3 py-2 rounded-xl bg-surface-900 border border-white/10 text-white">
              <option value="split_50_50">Split Screen (50/50)</option>
              <option value="split_60_40">Split Screen (60/40)</option>
              <option value="split_70_30">Split Screen (70/30)</option>
              <option value="no_gameplay">Full Portrait 9:16</option>
            </select>
          </label>
          <label className="space-y-1">
            <span className="text-xs font-semibold text-slate-400 uppercase">Resolution</span>
            <select value={defaults.resolution} onChange={e => updateDefault('resolution', e.target.value)}
              className="w-full px-3 py-2 rounded-xl bg-surface-900 border border-white/10 text-white">
              <option value="720p">720p</option>
              <option value="1080p">1080p</option>
              <option value="480p">480p</option>
              <option value="best">Best</option>
            </select>
          </label>
          <label className="space-y-1">
            <span className="text-xs font-semibold text-slate-400 uppercase">Caption Style</span>
            <select value={defaults.captionStyle} onChange={e => updateDefault('captionStyle', e.target.value)}
              className="w-full px-3 py-2 rounded-xl bg-surface-900 border border-white/10 text-white">
              <option value="hormozi">Hormozi</option>
              <option value="gadzhi">Gadzhi</option>
              <option value="ali_abdaal">Ali Abdaal</option>
              <option value="mrbeast">MrBeast</option>
              <option value="minimal">Minimal</option>
            </select>
          </label>
          <label className="space-y-1">
            <span className="text-xs font-semibold text-slate-400 uppercase">Background</span>
            <select value={defaults.backgroundType} onChange={e => updateDefault('backgroundType', e.target.value)}
              className="w-full px-3 py-2 rounded-xl bg-surface-900 border border-white/10 text-white">
              <option value="none">None</option>
              <option value="subway">Subway</option>
              <option value="minecraft">Minecraft</option>
              <option value="gta">GTA</option>
              <option value="templerun">Temple Run</option>
            </select>
          </label>
        </div>

        <div className="flex flex-col sm:flex-row gap-3">
          <button onClick={handleSaveDefaults} className="btn-primary flex items-center justify-center gap-2 px-6 py-3">
            <Save className="w-4 h-4" /> Save Defaults
          </button>
          <button onClick={handleResetDefaults} className="btn-ghost flex items-center justify-center gap-2 px-6 py-3">
            <Trash2 className="w-4 h-4" /> Reset to Factory Defaults
          </button>
        </div>
      </div>
    </motion.div>
  )
}
