import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { 
  ArrowLeft, Download, RefreshCw, Copy, Check, Info, AlertTriangle,
  Play, Pause, Volume2, VolumeX, Sparkles, Youtube, CheckCircle2,
  ListRestart, Loader2, Gauge, Flame, Terminal, HelpCircle, Sliders, RefreshCw as LoopIcon
} from 'lucide-react'
import { 
  getJobStatus, getClips, getClipHooks, 
  regenerateClip, getPreviewUrl, getDownloadUrl 
} from '@/lib/api'
import toast from 'react-hot-toast'

// Mock terminal messages based on job status to make the processing screen feel detailed
const TERMINAL_LOGS = {
  queued: [
    '[SYSTEM] Job successfully queued.',
    '[SYSTEM] Allocating container space...',
    '[SYSTEM] Awaiting worker assignment...'
  ],
  downloading: [
    '[SYSTEM] Worker assigned.',
    '[DOWNLOAD] Parsing YouTube video metadata...',
    '[DOWNLOAD] Extracting audio streams (AAC)...',
    '[DOWNLOAD] Downloading video stream (1080p)...',
    '[DOWNLOAD] Running yt-dlp binary...'
  ],
  transcribing: [
    '[WHISPER] Loading faster-whisper small model (int8/CPU)...',
    '[WHISPER] Audio normalization complete.',
    '[WHISPER] Running VAD filter to remove silence...',
    '[WHISPER] Generating word-level transcript timestamps...',
    '[WHISPER] Detecting speaker segments and language details...'
  ],
  analyzing: [
    '[GROQ] Connecting to Groq Cloud endpoint...',
    '[GROQ] Dispatching transcript to LLaMA 3.3 70B model...',
    '[GROQ] Running viral moment classification heuristics...',
    '[GROQ] Scoring curiosity hook, controversy, and retention metrics...',
    '[GROQ] Generating short titles, hooks, and hashtags...'
  ],
  clipping: [
    '[FFMPEG] Extracting moments based on AI timestamps...',
    '[OPENCV] Detecting faces and speakers for smart vertical cropping...',
    '[FFMPEG] Rescaling cropped feed to 1080x1920...',
    '[CAPTIONS] Generating ASS subtitle file with style overlays...',
    '[FFMPEG] Burning captions onto vertical video layer...',
    '[MIXER] Overlaying gameplay backgrounds on bottom half...',
    '[EXPORTER] Finalizing audio/video codec rendering (h264)...'
  ]
}

export default function Results() {
  const { jobId } = useParams()
  const navigate = useNavigate()

  // States
  const [job, setJob] = useState(null)
  const [clips, setClips] = useState([])
  const [activeClip, setActiveClip] = useState(null)
  const [hooks, setHooks] = useState(null)
  const [loading, setLoading] = useState(true)
  const [hooksLoading, setHooksLoading] = useState(false)
  const [logs, setLogs] = useState([])
  const [copiedText, setCopiedText] = useState('')
  
  // Custom video player states
  const [playing, setPlaying] = useState(false)
  const [volume, setVolume] = useState(1)
  const [muted, setMuted] = useState(false)
  const videoRef = useRef(null)

  // Regeneration states
  const [regenStyle, setRegenStyle] = useState('hormozi')
  const [regenBg, setRegenBg] = useState('subway')
  const [isRegenerating, setIsRegenerating] = useState(false)

  // WebSockets / Polling reference
  const wsRef = useRef(null)

  useEffect(() => {
    fetchJobDetails()

    return () => {
      if (wsRef.current) wsRef.current.close()
    }
  }, [jobId])

  // Automatically update logs when job status changes
  useEffect(() => {
    if (!job) return
    const status = job.status
    if (TERMINAL_LOGS[status]) {
      // Build a progressive log list
      const baseLogs = TERMINAL_LOGS[status]
      const finalLogs = []
      baseLogs.forEach((log, index) => {
        setTimeout(() => {
          setLogs(prev => {
            if (prev.includes(log)) return prev
            return [...prev, `${new Date().toLocaleTimeString()} ${log}`]
          })
        }, index * 400)
      })
    }
  }, [job?.status])

  const fetchJobDetails = async () => {
    try {
      const jobData = await getJobStatus(jobId)
      setJob(jobData)

      if (jobData.status === 'done') {
        const clipsData = await getClips(jobId)
        setClips(clipsData.clips || [])
        if (clipsData.clips?.length > 0) {
          handleSelectClip(clipsData.clips[0])
        }
        setLoading(false)
      } else if (jobData.status === 'error') {
        setLoading(false)
      } else {
        // In progress: setup websocket or poll
        setupProgressTracker()
      }
    } catch (err) {
      console.error(err)
      toast.error('Failed to load project details')
      setLoading(false)
    }
  }

  const setupProgressTracker = () => {
    setLoading(false)
    // WS creation protocol
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const host = window.location.host
    const wsUrl = `${protocol}://${host}/ws/job/${jobId}`

    try {
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data)
        setJob(prev => ({
          ...prev,
          status: data.status,
          progress: data.progress,
          current_step: data.current_step,
          error_message: data.error
        }))

        if (data.status === 'done') {
          ws.close()
          fetchJobDetails()
        } else if (data.status === 'error') {
          ws.close()
          setJob(prev => ({ ...prev, status: 'error', error_message: data.error }))
        }
      }

      ws.onclose = () => {
        // If closed prematurely and not done/error, fallback to polling
        if (job?.status && !['done', 'error'].includes(job.status)) {
          setTimeout(pollJobStatus, 2000)
        }
      }

      ws.onerror = () => {
        setTimeout(pollJobStatus, 2000)
      }
    } catch (e) {
      pollJobStatus()
    }
  }

  const pollJobStatus = async () => {
    try {
      const jobData = await getJobStatus(jobId)
      setJob(jobData)

      if (jobData.status === 'done') {
        fetchJobDetails()
      } else if (jobData.status === 'error') {
        // Handled
      } else {
        setTimeout(pollJobStatus, 2000)
      }
    } catch (err) {
      console.error(err)
    }
  }

  const handleSelectClip = async (clip) => {
    setActiveClip(clip)
    setHooks(null)
    setHooksLoading(true)
    setPlaying(false)

    // Set initial values for regeneration widget
    setRegenStyle(clip.caption_style)
    setRegenBg(clip.background_type)

    try {
      const hookData = await getClipHooks(clip.id)
      setHooks(hookData)
    } catch (err) {
      console.error(err)
    } finally {
      setHooksLoading(false)
    }
  }

  const handleCopy = (text, type) => {
    navigator.clipboard.writeText(text)
    setCopiedText(type)
    toast.success('Copied to clipboard!')
    setTimeout(() => setCopiedText(''), 2000)
  }

  const handleRegenerate = async () => {
    if (!activeClip) return
    setIsRegenerating(true)

    try {
      await regenerateClip(activeClip.id, {
        caption_style: regenStyle,
        background_type: regenBg
      })
      toast.success('Regeneration queued! Refreshing status...')
      
      // Update local clip status
      setClips(prev => prev.map(c => c.id === activeClip.id ? { ...c, status: 'pending' } : c))
      setActiveClip(prev => ({ ...prev, status: 'pending' }))
      
      // Poll this specific clip until completed
      pollClipRegen(activeClip.id)
    } catch (err) {
      console.error(err)
      toast.error('Failed to trigger clip regeneration')
      setIsRegenerating(false)
    }
  }

  const pollClipRegen = async (clipId) => {
    try {
      const response = await fetch(`/api/clips/detail/${clipId}`)
      const clip = await response.json()
      
      if (clip.status === 'done') {
        toast.success('Clip regenerated successfully!')
        // Reload all clips to get the new metadata
        const clipsData = await getClips(jobId)
        setClips(clipsData.clips || [])
        const updatedClip = clipsData.clips.find(c => c.id === clipId)
        if (updatedClip) handleSelectClip(updatedClip)
        setIsRegenerating(false)
      } else if (clip.status === 'error') {
        toast.error('Clip regeneration failed')
        setIsRegenerating(false)
      } else {
        setTimeout(() => pollClipRegen(clipId), 3000)
      }
    } catch (err) {
      console.error(err)
      setIsRegenerating(false)
    }
  }

  // Score badge coloring
  const getScoreColorClass = (score) => {
    if (score >= 90) return 'text-green-400 border-green-500/30 bg-green-500/5'
    if (score >= 75) return 'text-violet-400 border-violet-500/30 bg-violet-500/5'
    if (score >= 60) return 'text-sky-400 border-sky-500/30 bg-sky-500/5'
    if (score >= 45) return 'text-orange-400 border-orange-500/30 bg-orange-500/5'
    return 'text-slate-400 border-slate-500/30 bg-slate-500/5'
  }

  // Circular gauge component
  const ScoreGauge = ({ score }) => {
    const radius = 22
    const circumference = 2 * Math.PI * radius
    const offset = circumference - (score / 100) * circumference
    const color = 
      score >= 90 ? '#4ade80' : 
      score >= 75 ? '#8b5cf6' : 
      score >= 60 ? '#38bdf8' : 
      score >= 45 ? '#fb923c' : '#6b7280'

    return (
      <div className="relative flex items-center justify-center w-14 h-14">
        <svg className="w-full h-full transform -rotate-90">
          <circle 
            cx="28" cy="28" r={radius} 
            className="stroke-surface-900 fill-none" 
            strokeWidth="4"
          />
          <circle 
            cx="28" cy="28" r={radius} 
            className="fill-none transition-all duration-1000 ease-out" 
            strokeWidth="4"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            strokeLinecap="round"
            stroke={color}
          />
        </svg>
        <span className="absolute text-sm font-extrabold text-white">{score}</span>
      </div>
    )
  }

  // Custom Video Player Controls
  const togglePlay = () => {
    if (videoRef.current) {
      if (playing) videoRef.current.pause()
      else videoRef.current.play().catch(() => {})
      setPlaying(!playing)
    }
  }

  const handleVolumeChange = (e) => {
    const vol = parseFloat(e.target.value)
    setVolume(vol)
    setMuted(vol === 0)
    if (videoRef.current) {
      videoRef.current.volume = vol
      videoRef.current.muted = vol === 0
    }
  }

  const toggleMute = () => {
    const newMuted = !muted
    setMuted(newMuted)
    if (videoRef.current) {
      videoRef.current.muted = newMuted
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center flex-col space-y-4">
        <Loader2 className="w-12 h-12 text-brand-500 animate-spin" />
        <p className="text-slate-400 text-sm">Loading project information...</p>
      </div>
    )
  }

  const isProcessing = job && !['done', 'error'].includes(job.status)

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8 min-h-screen">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-white/[0.06] pb-5">
        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate('/')}
            className="p-2.5 rounded-xl border border-white/10 hover:bg-white/5 active:scale-95 transition-all text-slate-400 hover:text-white"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <h1 className="text-2xl font-extrabold text-white truncate max-w-xl">
              {job?.title || 'Processing pipeline...'}
            </h1>
            <p className="text-slate-400 text-xs mt-0.5 flex items-center gap-1.5">
              <Youtube className="w-3.5 h-3.5 text-pink-500" />
              <a href={job?.youtube_url} target="_blank" rel="noopener noreferrer" className="hover:underline hover:text-indigo-400 truncate max-w-md">
                {job?.youtube_url}
              </a>
            </p>
          </div>
        </div>
        
        {job?.status === 'done' && (
          <span className="px-3 py-1.5 rounded-full text-xs font-semibold bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 shadow-[0_0_15px_rgba(16,185,129,0.1)]">
            Job Complete
          </span>
        )}
      </div>

      <AnimatePresence mode="wait">
        {/* State 1: Active Processing Screen */}
        {isProcessing && (
          <motion.div 
            initial={{ opacity: 0, scale: 0.98 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.98 }}
            className="grid grid-cols-1 lg:grid-cols-12 gap-8"
          >
            {/* Left Box: Progress Loader */}
            <div className="lg:col-span-5 glass rounded-3xl p-8 flex flex-col justify-center items-center text-center space-y-6 min-h-[450px]">
              <div className="relative flex items-center justify-center">
                {/* Glowing ring animation */}
                <div className="w-40 h-40 rounded-full border border-indigo-500/20 flex items-center justify-center">
                  <div className="absolute inset-0 rounded-full border-t-2 border-indigo-500 animate-spin" />
                  <div className="w-32 h-32 rounded-full bg-surface-900 border border-white/10 flex flex-col items-center justify-center">
                    <span className="text-3xl font-black text-white">{job.progress}%</span>
                    <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider mt-1">Processed</span>
                  </div>
                </div>
              </div>

              <div className="space-y-2">
                <h3 className="text-xl font-bold text-white capitalize">{job.current_step || job.status}</h3>
                <p className="text-slate-400 text-sm max-w-xs">
                  LLaMA and Whisper are parsing, cutting and overlaying gameplay onto your video.
                </p>
              </div>

              <div className="w-full max-w-xs h-1.5 bg-surface-900 rounded-full overflow-hidden">
                <div className="h-full progress-bar" style={{ width: `${job.progress}%` }} />
              </div>
            </div>

            {/* Right Box: Terminal Simulator */}
            <div className="lg:col-span-7 glass rounded-3xl p-6 flex flex-col h-[450px]">
              <div className="flex items-center gap-2 border-b border-white/[0.06] pb-3 mb-4 text-slate-400">
                <Terminal className="w-4 h-4 text-indigo-400" />
                <span className="text-xs font-bold uppercase tracking-wider font-mono">Job Orchestrator Terminal</span>
                <span className="w-2 h-2 rounded-full bg-green-500 animate-ping ml-auto" />
              </div>
              
              <div className="flex-1 font-mono text-xs text-slate-300 overflow-y-auto space-y-2 pr-2 scrollbar-thin">
                {logs.length === 0 ? (
                  <p className="text-slate-600 italic">Initializing orchestration sequence...</p>
                ) : (
                  logs.map((log, idx) => (
                    <div key={idx} className="whitespace-pre-wrap leading-relaxed text-indigo-300/90">
                      {log}
                    </div>
                  ))
                )}
                {/* Auto-scroll anchor */}
                <div ref={(el) => el?.scrollIntoView({ behavior: 'smooth' })} />
              </div>
            </div>
          </motion.div>
        )}

        {/* State 2: Error Screen */}
        {job?.status === 'error' && (
          <motion.div 
            initial={{ opacity: 0, scale: 0.98 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.98 }}
            className="glass rounded-3xl p-12 text-center max-w-xl mx-auto space-y-6 flex flex-col items-center"
          >
            <div className="w-16 h-16 rounded-full bg-pink-500/10 border border-pink-500/20 flex items-center justify-center text-pink-400">
              <AlertTriangle className="w-8 h-8" />
            </div>
            <div className="space-y-2">
              <h3 className="text-xl font-bold text-white">Pipeline Execution Failed</h3>
              <p className="text-slate-400 text-sm leading-relaxed max-w-md">
                We encountered an unexpected error while executing the video rendering scripts:
              </p>
              <div className="bg-surface-900 border border-white/10 rounded-xl p-4 text-xs font-mono text-pink-300 mt-4 text-left max-h-40 overflow-y-auto">
                {job.error_message || 'Unknown server execution error.'}
              </div>
            </div>

            <div className="flex gap-4">
              <button onClick={() => navigate('/create')} className="btn-primary">
                Try Another Video
              </button>
              <button onClick={() => navigate('/')} className="btn-ghost">
                Back to Dashboard
              </button>
            </div>
          </motion.div>
        )}

        {/* State 3: Done / Success Dashboard */}
        {job?.status === 'done' && clips.length > 0 && (
          <motion.div 
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start"
          >
            {/* Left Panel: Clips List */}
            <div className="lg:col-span-5 space-y-4 max-h-[750px] overflow-y-auto pr-2 scrollbar-thin">
              <h3 className="font-bold text-white text-sm uppercase tracking-wider flex items-center gap-2">
                <Flame className="w-4 h-4 text-orange-500" />
                <span>Detected Clips ({clips.length})</span>
              </h3>

              <div className="space-y-3">
                {clips.map((clip, index) => {
                  const isActive = activeClip && activeClip.id === clip.id
                  return (
                    <div
                      key={clip.id}
                      onClick={() => handleSelectClip(clip)}
                      className={`glass p-4 rounded-2xl cursor-pointer flex items-center gap-4 transition-all border ${
                        isActive 
                          ? 'border-brand-500 bg-brand-600/10 shadow-[0_0_15px_rgba(99,102,241,0.15)]' 
                          : 'border-white/[0.06] hover:border-white/10'
                      }`}
                    >
                      {/* circular score meter */}
                      <ScoreGauge score={clip.virality_score} />

                      {/* Content */}
                      <div className="flex-1 min-w-0 space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-white text-sm">Clip #{index + 1}</span>
                          <span className={`text-[10px] font-extrabold uppercase border px-2 py-0.5 rounded-full ${
                            getScoreColorClass(clip.virality_score)
                          }`}>
                            {clip.virality_label}
                          </span>
                        </div>
                        <p className="text-slate-400 text-xs truncate">
                          {clip.reason || 'AI virality explanation placeholder'}
                        </p>
                        <p className="text-slate-500 text-[10px] font-semibold">
                          Duration: {Math.round(clip.duration)}s ({Math.round(clip.start_time)}s - {Math.round(clip.end_time)}s)
                        </p>
                      </div>

                      {clip.status !== 'done' && (
                        <div className="text-brand-400">
                          <Loader2 className="w-4 h-4 animate-spin" />
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>

            {/* Right Panel: Detailed Active Clip Preview */}
            <div className="lg:col-span-7 space-y-6">
              {activeClip && (
                <div className="grid grid-cols-1 md:grid-cols-12 gap-6">
                  
                  {/* Aspect Ratio 9:16 Video Player Container */}
                  <div className="md:col-span-6 flex flex-col items-center">
                    <div className="w-full aspect-[9/16] bg-surface-900 border border-white/[0.06] rounded-2xl overflow-hidden relative group">
                      
                      {activeClip.status === 'done' ? (
                        <>
                          <video
                            ref={videoRef}
                            src={getPreviewUrl(activeClip.id)}
                            loop
                            className="w-full h-full object-cover"
                            onClick={togglePlay}
                            onPlay={() => setPlaying(true)}
                            onPause={() => setPlaying(false)}
                          />
                          
                          {/* Play/Pause center overlay */}
                          {!playing && (
                            <button
                              onClick={togglePlay}
                              className="absolute inset-0 m-auto w-16 h-16 rounded-full bg-black/60 backdrop-blur-md flex items-center justify-center text-white scale-100 hover:scale-105 active:scale-95 transition-transform"
                            >
                              <Play className="w-6 h-6 ml-1" fill="currentColor" />
                            </button>
                          )}

                          {/* Custom Controls Bar */}
                          <div className="absolute bottom-0 inset-x-0 p-4 bg-gradient-to-t from-black/80 via-black/40 to-transparent flex items-center gap-3 opacity-0 group-hover:opacity-100 transition-opacity">
                            <button onClick={togglePlay} className="text-white hover:text-brand-400">
                              {playing ? <Pause className="w-5 h-5" fill="currentColor" /> : <Play className="w-5 h-5" fill="currentColor" />}
                            </button>

                            <button onClick={toggleMute} className="text-white hover:text-brand-400">
                              {muted ? <VolumeX className="w-5 h-5" /> : <Volume2 className="w-5 h-5" />}
                            </button>
                            
                            <input
                              type="range" min="0" max="1" step="0.05"
                              value={muted ? 0 : volume}
                              onChange={handleVolumeChange}
                              className="w-16 accent-brand-500 h-1 rounded cursor-pointer bg-white/20"
                            />
                          </div>
                        </>
                      ) : (
                        <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/80 text-center p-6 space-y-3">
                          <Loader2 className="w-8 h-8 text-brand-500 animate-spin" />
                          <p className="text-slate-400 text-sm font-medium">Regenerating clip parameters...</p>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Metadata and AI Tabs */}
                  <div className="md:col-span-6 space-y-6">
                    
                    {/* Header Action Row */}
                    <div className="flex items-center gap-3">
                      <a
                        href={getDownloadUrl(activeClip.id)}
                        className="flex-1 py-3 px-4 rounded-xl font-bold bg-white text-indigo-950 hover:bg-indigo-50 transition-all flex items-center justify-center gap-2 shadow-lg active:scale-98 text-sm"
                      >
                        <Download className="w-4 h-4" />
                        <span>Download Clip</span>
                      </a>
                    </div>

                    {/* Virality score breakdown panel */}
                    <div className="glass rounded-2xl p-5 space-y-4">
                      <h4 className="font-bold text-white text-sm uppercase tracking-wider flex items-center gap-2">
                        <Gauge className="w-4 h-4 text-violet-400" />
                        <span>Virality Breakdown</span>
                      </h4>

                      <div className="space-y-3">
                        {activeClip.score_breakdown && Object.entries(activeClip.score_breakdown).map(([key, data]) => (
                          <div key={key} className="space-y-1">
                            <div className="flex justify-between text-xs">
                              <span className="text-slate-400 font-medium capitalize">
                                {key.replace('_', ' ')}
                              </span>
                              <span className="text-slate-300 font-bold">{data.raw}/10</span>
                            </div>
                            <div className="w-full h-1 bg-surface-900 rounded-full overflow-hidden">
                              <div 
                                className="h-full bg-brand-500" 
                                style={{ width: `${data.raw * 10}%` }}
                              />
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Clip Settings Modifier */}
                    <div className="glass rounded-2xl p-5 space-y-4">
                      <h4 className="font-bold text-white text-sm uppercase tracking-wider flex items-center gap-2">
                        <Sliders className="w-4 h-4 text-pink-400" />
                        <span>Tweak Style & Overlay</span>
                      </h4>

                      <div className="space-y-3">
                        <div className="space-y-1">
                          <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">Caption Preset</label>
                          <select
                            value={regenStyle}
                            onChange={(e) => setRegenStyle(e.target.value)}
                            disabled={isRegenerating || activeClip.status !== 'done'}
                            className="w-full bg-surface-900 border border-white/10 text-white rounded-lg px-2.5 py-1.5 text-xs focus:outline-none focus:border-brand-500"
                          >
                            <option value="hormozi">Alex Hormozi</option>
                            <option value="gadzhi">Iman Gadzhi</option>
                            <option value="ali_abdaal">Ali Abdaal</option>
                            <option value="mrbeast">MrBeast Style</option>
                            <option value="minimal">Minimalist</option>
                          </select>
                        </div>

                        <div className="space-y-1">
                          <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">Gameplay Video</label>
                          <select
                            value={regenBg}
                            onChange={(e) => setRegenBg(e.target.value)}
                            disabled={isRegenerating || activeClip.status !== 'done'}
                            className="w-full bg-surface-900 border border-white/10 text-white rounded-lg px-2.5 py-1.5 text-xs focus:outline-none focus:border-brand-500"
                          >
                            <option value="subway">Subway Surfers</option>
                            <option value="minecraft">Minecraft Parkour</option>
                            <option value="gta">GTA V Stunts</option>
                            <option value="templerun">Temple Run</option>
                            <option value="none">No Overlay (Crop only)</option>
                          </select>
                        </div>

                        <button
                          onClick={handleRegenerate}
                          disabled={isRegenerating || activeClip.status !== 'done'}
                          className="w-full py-2 bg-indigo-500/10 hover:bg-indigo-500/20 text-indigo-400 border border-indigo-500/30 rounded-xl text-xs font-bold transition-colors flex items-center justify-center gap-1.5"
                        >
                          <RefreshCw className={`w-3.5 h-3.5 ${isRegenerating ? 'animate-spin' : ''}`} />
                          <span>Regenerate Single Clip</span>
                        </button>
                      </div>
                    </div>

                  </div>

                  {/* AI Copier Section: Titles, Hooks, Hashtags */}
                  <div className="col-span-12 border-t border-white/[0.06] pt-6 space-y-4">
                    <h3 className="font-bold text-white text-base flex items-center gap-2">
                      <Sparkles className="w-5 h-5 text-indigo-400 animate-pulse" />
                      <span>AI Virality Assistant Suggestions</span>
                    </h3>

                    {hooksLoading ? (
                      <div className="glass rounded-2xl p-6 text-center space-y-2">
                        <Loader2 className="w-6 h-6 animate-spin text-brand-500 mx-auto" />
                        <p className="text-slate-400 text-xs">Querying AI metadata models...</p>
                      </div>
                    ) : hooks ? (
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        
                        {/* Title Suggestions */}
                        <div className="glass rounded-2xl p-5 space-y-2 relative group/card">
                          <h4 className="text-xs font-extrabold uppercase text-slate-500 tracking-wider">Suggested Title</h4>
                          <p className="text-sm font-semibold text-white pr-8 leading-snug">{hooks.title}</p>
                          <button
                            onClick={() => handleCopy(hooks.title, 'title')}
                            className="absolute top-4 right-4 p-2 rounded-lg bg-surface-900 border border-white/5 opacity-0 group-hover/card:opacity-100 transition-opacity hover:text-white"
                          >
                            {copiedText === 'title' ? <Check className="w-3.5 h-3.5 text-green-400" /> : <Copy className="w-3.5 h-3.5 text-slate-400" />}
                          </button>
                        </div>

                        {/* Hooks Suggestions */}
                        <div className="glass rounded-2xl p-5 space-y-2 relative group/card">
                          <h4 className="text-xs font-extrabold uppercase text-slate-500 tracking-wider">Opening Hook Line</h4>
                          <p className="text-sm font-semibold text-white pr-8 leading-snug">{hooks.hook}</p>
                          <button
                            onClick={() => handleCopy(hooks.hook, 'hook')}
                            className="absolute top-4 right-4 p-2 rounded-lg bg-surface-900 border border-white/5 opacity-0 group-hover/card:opacity-100 transition-opacity hover:text-white"
                          >
                            {copiedText === 'hook' ? <Check className="w-3.5 h-3.5 text-green-400" /> : <Copy className="w-3.5 h-3.5 text-slate-400" />}
                          </button>
                        </div>

                        {/* Description / Caption */}
                        <div className="glass rounded-2xl p-5 space-y-2 relative group/card md:col-span-2">
                          <h4 className="text-xs font-extrabold uppercase text-slate-500 tracking-wider">Social Subtitle Caption</h4>
                          <p className="text-sm text-slate-300 pr-8 leading-relaxed whitespace-pre-line">{hooks.caption}</p>
                          
                          {/* Render hashtags inside tags */}
                          {hooks.hashtags && hooks.hashtags.length > 0 && (
                            <div className="flex flex-wrap gap-2 mt-4 border-t border-white/[0.04] pt-3">
                              {hooks.hashtags.map((tag, idx) => (
                                <span key={idx} className="text-[10px] font-bold text-indigo-400 bg-indigo-500/10 px-2 py-0.5 rounded-full border border-indigo-500/20">
                                  #{tag}
                                </span>
                              ))}
                            </div>
                          )}

                          <button
                            onClick={() => handleCopy(`${hooks.caption}\n\n${hooks.hashtags?.map(t => `#${t}`).join(' ')}`, 'caption')}
                            className="absolute top-4 right-4 p-2 rounded-lg bg-surface-900 border border-white/5 opacity-0 group-hover/card:opacity-100 transition-opacity hover:text-white"
                          >
                            {copiedText === 'caption' ? <Check className="w-3.5 h-3.5 text-green-400" /> : <Copy className="w-3.5 h-3.5 text-slate-400" />}
                          </button>
                        </div>

                        {/* Suggested Thumbnail Text overlay */}
                        <div className="glass rounded-2xl p-5 space-y-2 relative group/card md:col-span-2">
                          <h4 className="text-xs font-extrabold uppercase text-slate-500 tracking-wider">Thumbnail Text Suggestion</h4>
                          <p className="text-sm text-pink-400 font-bold uppercase tracking-wider">{hooks.thumbnail_text || 'No thumbnail texts generated'}</p>
                        </div>

                      </div>
                    ) : (
                      <p className="text-xs text-slate-500 italic">No AI assistance metadata generated for this clip.</p>
                    )}
                  </div>

                </div>
              )}
            </div>

          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
