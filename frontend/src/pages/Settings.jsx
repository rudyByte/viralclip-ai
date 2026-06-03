import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { Settings as SettingsIcon, Cookie, CheckCircle2, Trash2, Save, Loader2, AlertTriangle } from 'lucide-react'
import { getCookiesStatus, saveCookies, deleteCookies } from '@/lib/api'
import toast from 'react-hot-toast'

export default function Settings() {
  const [cookiesText, setCookiesText] = useState('')
  const [status, setStatus] = useState(null)  // {saved: bool}
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    getCookiesStatus()
      .then(setStatus)
      .catch(() => setStatus({ saved: false }))
      .finally(() => setLoading(false))
  }, [])

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

  const handleDelete = async () => {
    try {
      await deleteCookies()
      setStatus({ saved: false })
      toast.success('Cookies removed')
    } catch {
      toast.error('Failed to delete cookies')
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
    </motion.div>
  )
}
