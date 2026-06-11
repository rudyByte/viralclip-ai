import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { 
  Youtube, Sliders, Type, Gamepad2, Play, Sparkles, 
  ChevronRight, ArrowLeft, Loader2 
} from 'lucide-react'
import { processVideo } from '@/lib/api'
import { loadDefaults, saveDefaults } from '@/lib/settings'
import toast from 'react-hot-toast'

const CAPTION_STYLES = [
  { id: 'hormozi', name: 'Alex Hormozi', desc: 'Bold yellow/green uppercase words with emoji hooks.', badge: 'Popular' },
  { id: 'gadzhi', name: 'Iman Gadzhi', desc: 'Elegant, serif typeface captions with subtle fade-ins.', badge: 'Sleek' },
  { id: 'ali_abdaal', name: 'Ali Abdaal', desc: 'Minimalist clean san-serif text, easy-to-read.', badge: 'Clean' },
  { id: 'mrbeast', name: 'MrBeast Style', desc: 'High-energy, colorful scaling text with thick borders.', badge: 'Dynamic' },
  { id: 'minimal', name: 'Minimalist', desc: 'Classic white subtitles, centered, no distractions.', badge: 'Subtle' },
]

const BACKGROUND_TYPES = [
  { id: 'subway', name: 'Subway Surfers', desc: 'Infinite running gameplay, perfect for high retention.', image: '🏄‍♂️' },
  { id: 'minecraft', name: 'Minecraft Parkour', desc: 'Relaxing block-jumping gameplay, widely engaging.', image: '🧱' },
  { id: 'gta', name: 'GTA V Chaos', desc: 'Stunt tracks and high speed crashes from Los Santos.', image: '🚗' },
  { id: 'templerun', name: 'Temple Run', desc: 'Classic temple escapes, keeps viewers glued to screen.', image: '🏃‍♂️' },
  { id: 'none', name: 'No Gameplay Overlay', desc: 'Keep original video crop centered without gaming overlay.', image: '❌' },
]

const LAYOUT_TEMPLATES = [
  { id: 'split_50_50', name: 'Split Screen (50/50)', desc: 'Equal split, perfect for standard dual videos.', badge: 'Standard' },
  { id: 'split_60_40', name: 'Split Screen (60/40)', desc: 'Larger main video (60%), smaller gameplay (40%).', badge: 'Focus' },
  { id: 'split_70_30', name: 'Split Screen (70/30)', desc: 'Highly prominent main video (70%), tiny gameplay (30%).', badge: 'Speaker' },
  { id: 'no_gameplay', name: 'Full Portrait 9:16', desc: 'Full screen crop of the main video, no gameplay background.', badge: 'Classic' },
]

const MAX_BATCH_URLS = 20
const MAX_CLIPS = 20

export default function CreateShort() {
  const navigate = useNavigate()
  const defaults = loadDefaults()
  const [url, setUrl] = useState('')
  const [minDuration, setMinDuration] = useState(defaults.clipMinDuration)
  const [maxDuration, setMaxDuration] = useState(defaults.clipMaxDuration)
  const [numClips, setNumClips] = useState(defaults.numClips)
  const [captionStyle, setCaptionStyle] = useState(defaults.captionStyle)
  const [backgroundType, setBackgroundType] = useState(defaults.backgroundType)
  const [layoutTemplate, setLayoutTemplate] = useState(defaults.layoutTemplate)
  const [resolution, setResolution] = useState(defaults.resolution)
  const [cookies, setCookies] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const urlCount = url.split(/[\n,]+/).map(u => u.trim()).filter(Boolean).length

  const currentDefaults = () => ({
    clipMinDuration: parseInt(minDuration),
    clipMaxDuration: parseInt(maxDuration),
    numClips: parseInt(numClips),
    captionStyle,
    backgroundType,
    layoutTemplate,
    resolution,
  })

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!url) return toast.error('Please enter at least one YouTube URL')
    
    const urls = url.split(/[\n,]+/).map(u => u.trim()).filter(Boolean)
    if (urls.length === 0) return toast.error('Please enter at least one YouTube URL')

    // Simple YouTube URL Regex check
    const ytRegex = /^(https?:\/\/)?(www\.)?(youtube\.com|youtu\.be)\/.+$/
    for (const u of urls) {
      if (!ytRegex.test(u)) {
        return toast.error(`Invalid YouTube URL: "${u}"`)
      }
    }

    if (minDuration >= maxDuration) {
      return toast.error('Minimum duration must be less than maximum duration')
    }

    setSubmitting(true)
    try {
      const response = await processVideo({
        youtube_urls: urls.slice(0, MAX_BATCH_URLS),
        clip_min_duration: parseInt(minDuration),
        clip_max_duration: parseInt(maxDuration),
        num_clips: parseInt(numClips),
        caption_style: captionStyle,
        background_type: backgroundType,
        layout_template: layoutTemplate,
        resolution: resolution,
        cookies: cookies || null
      })
      
      toast.success(response.message || 'Job(s) queued successfully!')
      // Save to localStorage so user can return later from any device
      saveToHistory(response.job_id, urls[0])
      navigate(`/results/${response.job_id}`)
    } catch (err) {
      console.error(err)
      toast.error(err.response?.data?.detail || 'Failed to start video processing')
    } finally {
      setSubmitting(false)
    }
  }

  // Save to localStorage for fire-and-forget history
  const saveToHistory = (jobId, jobUrl) => {
    try {
      const history = JSON.parse(localStorage.getItem('viralclip_jobs') || '[]')
      const filtered = history.filter(j => j.id !== jobId)
      filtered.unshift({ id: jobId, title: jobUrl, savedAt: Date.now() })
      localStorage.setItem('viralclip_jobs', JSON.stringify(filtered.slice(0, 20)))
    } catch (_) {}
  }

  return (
    <motion.div 
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -15 }}
      transition={{ duration: 0.35, ease: 'easeOut' }}
      className="p-4 md:p-8 max-w-4xl mx-auto space-y-6 md:space-y-8"
    >
      {/* Back link */}
      <button
        onClick={() => navigate('/')}
        className="flex items-center gap-2 text-slate-400 hover:text-white transition-colors group text-sm"
      >
        <ArrowLeft className="w-4 h-4 group-hover:-translate-x-0.5 transition-transform" />
        <span>Back to Dashboard</span>
      </button>

      {/* Header */}
      <div>
        <h1 className="text-3xl font-extrabold text-white flex items-center gap-2">
          <Sparkles className="w-8 h-8 text-brand-400" />
          <span>Create Viral Short</span>
        </h1>
        <p className="text-slate-400 mt-1">
          Configure your pipeline settings and let LLaMA + Whisper perform their magic.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-8">
        
        {/* Step 1: Input URL */}
        <div className="glass rounded-2xl p-6 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <label className="block text-sm font-bold text-white uppercase tracking-wider">
              1. Paste YouTube URL(s)
            </label>
            <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">
              {urlCount} URL(s) detected - max {MAX_BATCH_URLS}
            </span>
          </div>
          <div className="relative">
            <div className="absolute left-4 top-5 text-pink-500">
              <Youtube className="w-6 h-6" />
            </div>
            <textarea
              placeholder="e.g.&#10;https://www.youtube.com/watch?v=dQw4w9WgXcQ&#10;https://www.youtube.com/watch?v=another_video_url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              disabled={submitting}
              rows={4}
              className="w-full pl-12 pr-4 py-3 rounded-xl bg-surface-900 border border-white/10 text-white placeholder-slate-500 focus:outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 transition-all font-medium text-base font-mono resize-y"
            />
          </div>
        </div>

        {/* Step 2: Duration and Clip count */}
        <div className="glass rounded-2xl p-6 space-y-6">
          <div className="flex items-center gap-2 text-sm font-bold text-white uppercase tracking-wider">
            <Sliders className="w-5 h-5 text-brand-400" />
            <span>2. Video Settings</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="space-y-2">
              <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider block">
                Min Duration ({minDuration}s)
              </label>
              <input
                type="range"
                min="15"
                max="60"
                step="5"
                value={minDuration}
                onChange={(e) => setMinDuration(e.target.value)}
                disabled={submitting}
                className="w-full accent-brand-500 bg-surface-900 rounded-lg cursor-pointer h-2"
              />
            </div>

            <div className="space-y-2">
              <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider block">
                Max Duration ({maxDuration}s)
              </label>
              <input
                type="range"
                min="30"
                max="90"
                step="5"
                value={maxDuration}
                onChange={(e) => setMaxDuration(e.target.value)}
                disabled={submitting}
                className="w-full accent-brand-500 bg-surface-900 rounded-lg cursor-pointer h-2"
              />
            </div>

            <div className="space-y-2">
              <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider block">
                Max Clips ({numClips})
              </label>
              <input
                type="number"
                min="1"
                max={MAX_CLIPS}
                value={numClips}
                onChange={(e) => setNumClips(e.target.value)}
                disabled={submitting}
                className="w-full px-3 py-2 rounded-xl bg-surface-900 border border-white/10 text-white placeholder-slate-500 focus:outline-none focus:border-brand-500 transition-all font-semibold"
              />
            </div>
          </div>
        </div>

        {/* Step 3: Captions */}
        <div className="glass rounded-2xl p-6 space-y-4">
          <div className="flex items-center gap-2 text-sm font-bold text-white uppercase tracking-wider">
            <Type className="w-5 h-5 text-brand-400" />
            <span>3. Subtitle Font & Animation Style</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 md:gap-4">
            {CAPTION_STYLES.map(style => (
              <div
                key={style.id}
                onClick={() => !submitting && setCaptionStyle(style.id)}
                className={`p-4 rounded-xl border cursor-pointer flex flex-col justify-between h-32 transition-all ${
                  captionStyle === style.id
                    ? 'bg-brand-600/10 border-brand-500 shadow-[0_0_15px_rgba(99,102,241,0.15)]'
                    : 'bg-surface-900/50 border-white/[0.06] hover:border-white/20'
                }`}
              >
                <div>
                  <div className="flex items-center justify-between">
                    <h4 className="font-bold text-white text-sm">{style.name}</h4>
                    <span className="text-[10px] uppercase font-bold bg-white/10 px-2 py-0.5 rounded-full text-brand-400">
                      {style.badge}
                    </span>
                  </div>
                  <p className="text-slate-400 text-xs mt-2 leading-relaxed">{style.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Step 4: Backgrounds */}
        <div className="glass rounded-2xl p-6 space-y-4">
          <div className="flex items-center gap-2 text-sm font-bold text-white uppercase tracking-wider">
            <Gamepad2 className="w-5 h-5 text-brand-400" />
            <span>4. Gaming Background Overlay</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 md:gap-4">
            {BACKGROUND_TYPES.map(bg => (
              <div
                key={bg.id}
                onClick={() => !submitting && setBackgroundType(bg.id)}
                className={`p-4 rounded-xl border cursor-pointer flex items-center gap-4 transition-all ${
                  backgroundType === bg.id
                    ? 'bg-brand-600/10 border-brand-500 shadow-[0_0_15px_rgba(99,102,241,0.15)]'
                    : 'bg-surface-900/50 border-white/[0.06] hover:border-white/20'
                }`}
              >
                <div className="w-12 h-12 rounded-xl bg-surface-900 flex items-center justify-center text-2xl border border-white/10">
                  {bg.image}
                </div>
                <div className="min-w-0">
                  <h4 className="font-bold text-white text-sm truncate">{bg.name}</h4>
                  <p className="text-slate-400 text-xs truncate leading-normal mt-0.5">{bg.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Step 5: Layout Templates */}
        <div className="glass rounded-2xl p-6 space-y-4">
          <div className="flex items-center gap-2 text-sm font-bold text-white uppercase tracking-wider">
            <Sliders className="w-5 h-5 text-brand-400" />
            <span>5. Layout Aspect Ratio & Template</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 md:gap-4">
            {LAYOUT_TEMPLATES.map(tmpl => (
              <div
                key={tmpl.id}
                onClick={() => !submitting && setLayoutTemplate(tmpl.id)}
                className={`p-4 rounded-xl border cursor-pointer flex flex-col justify-between h-28 transition-all ${
                  layoutTemplate === tmpl.id
                    ? 'bg-brand-600/10 border-brand-500 shadow-[0_0_15px_rgba(99,102,241,0.15)]'
                    : 'bg-surface-900/50 border-white/[0.06] hover:border-white/20'
                }`}
              >
                <div>
                  <div className="flex items-center justify-between">
                    <h4 className="font-bold text-white text-sm">{tmpl.name}</h4>
                    <span className="text-[10px] uppercase font-bold bg-white/10 px-2 py-0.5 rounded-full text-brand-400">
                      {tmpl.badge}
                    </span>
                  </div>
                  <p className="text-slate-400 text-xs mt-2 leading-relaxed">{tmpl.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Step 6: Advanced Settings */}
        <div className="glass rounded-2xl p-6 space-y-6">
          <div className="flex items-center gap-2 text-sm font-bold text-white uppercase tracking-wider">
            <Sliders className="w-5 h-5 text-brand-400" />
            <span>6. Quality & Cloud Bypass Settings (Optional)</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="md:col-span-1 space-y-2">
              <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider block">
                Video Resolution
              </label>
              <select
                value={resolution}
                onChange={(e) => setResolution(e.target.value)}
                disabled={submitting}
                className="w-full px-3 py-3 rounded-xl bg-surface-900 border border-white/10 text-white placeholder-slate-500 focus:outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 transition-all font-semibold"
              >
                <option value="best">Highest (Unrestricted 4K/2K/1080p)</option>
                <option value="1080p">1080p Full HD (Default)</option>
                <option value="720p">720p HD</option>
                <option value="480p">480p SD</option>
              </select>
              <p className="text-[10px] text-slate-400 mt-1">
                Lower resolutions download and process significantly faster.
              </p>
            </div>

            <div className="md:col-span-2 space-y-2">
              <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider block flex justify-between">
                <span>YouTube Cookies (Netscape format)</span>
                <span className="text-[10px] text-brand-400 lowercase italic">Optional</span>
              </label>
              <textarea
                placeholder="Paste your Netscape cookies text here to bypass 'Sign in to confirm you're not a bot' blocks when running on the hosted/production server."
                value={cookies}
                onChange={(e) => setCookies(e.target.value)}
                disabled={submitting}
                rows={3}
                className="w-full px-3 py-2 rounded-xl bg-surface-900 border border-white/10 text-white placeholder-slate-500 focus:outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 transition-all font-medium text-xs font-mono resize-y"
              />
              <p className="text-[10px] text-slate-400 mt-1">
                Use a browser extension like "Get cookies.txt" to copy cookies from YouTube.
              </p>
            </div>
          </div>
        </div>

        {/* Submit */}
        <div className="flex items-center justify-stretch sm:justify-end">
          <button
            type="button"
            onClick={() => {
              saveDefaults(currentDefaults())
              toast.success('Defaults saved')
            }}
            disabled={submitting}
            className="btn-ghost w-full sm:w-auto px-6 py-4 mr-0 sm:mr-3 mb-3 sm:mb-0"
          >
            Save as Default
          </button>
          <button
            type="submit"
            disabled={submitting}
            className="btn-primary w-full sm:w-auto px-8 py-4 flex items-center justify-center gap-2 text-lg disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {submitting ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                <span>Queueing Clip Job...</span>
              </>
            ) : (
              <>
                <span>Generate Clips</span>
                <Play className="w-4 h-4" fill="currentColor" />
              </>
            )}
          </button>
        </div>

      </form>
    </motion.div>
  )
}
