import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { 
  Play, Video, Cpu, Activity, AlertTriangle, 
  Trash2, ArrowRight, RefreshCw, Film, TrendingUp
} from 'lucide-react'
import { listJobs, deleteJob, healthCheck } from '@/lib/api'
import toast from 'react-hot-toast'

export default function Dashboard() {
  const navigate = useNavigate()
  const [jobs, setJobs] = useState([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [systemStatus, setSystemStatus] = useState('unknown')

  const fetchDashboardData = async (silent = false) => {
    if (!silent) setLoading(true)
    else setRefreshing(true)

    try {
      const jobsData = await listJobs()
      setJobs(jobsData.jobs || [])
      
      const health = await healthCheck()
      setSystemStatus(health.status === 'ok' ? 'online' : 'degraded')
    } catch (err) {
      console.error(err)
      toast.error('Failed to load dashboard data')
      setSystemStatus('offline')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  useEffect(() => {
    fetchDashboardData()
    // Poll every 10s to keep statuses updated
    const interval = setInterval(() => fetchDashboardData(true), 10000)
    return () => clearInterval(interval)
  }, [])

  const handleDeleteJob = async (jobId, e) => {
    e.stopPropagation()
    if (!confirm('Are you sure you want to delete this job and all its clips?')) return

    try {
      await deleteJob(jobId)
      toast.success('Job deleted successfully')
      setJobs(prev => prev.filter(j => j.id !== jobId))
    } catch (err) {
      console.error(err)
      toast.error(err.response?.data?.detail || 'Failed to delete job')
    }
  }

  // Calculate statistics
  const totalVideos = jobs.length
  const activeJobs = jobs.filter(j => !['done', 'error'].includes(j.status)).length
  const totalClips = jobs.reduce((sum, j) => sum + (j.clip_count || 0), 0)

  return (
    <motion.div 
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -15 }}
      transition={{ duration: 0.35, ease: 'easeOut' }}
      className="p-8 max-w-6xl mx-auto space-y-8"
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-4xl font-extrabold tracking-tight text-white">
            Welcome to <span className="text-gradient">ViralClip AI</span>
          </h1>
          <p className="text-slate-400 mt-1">
            Turn long videos into high-retention short clips, instantly and for free.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium bg-white/5 border border-white/10">
            <span className={`w-2 h-2 rounded-full ${
              systemStatus === 'online' ? 'bg-green-500 animate-pulse' : 
              systemStatus === 'degraded' ? 'bg-yellow-500' : 'bg-red-500'
            }`} />
            <span className="text-slate-300 capitalize">{systemStatus} System</span>
          </div>

          <button
            onClick={() => fetchDashboardData(true)}
            disabled={refreshing}
            className="p-2.5 rounded-xl border border-white/10 hover:bg-white/5 active:scale-95 transition-all text-slate-400 hover:text-white"
          >
            <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="stat-card glass flex items-center justify-between">
          <div className="space-y-1">
            <p className="text-slate-500 text-xs font-semibold uppercase tracking-wider">Total Videos</p>
            <h3 className="text-3xl font-extrabold text-white">{totalVideos}</h3>
          </div>
          <div className="w-12 h-12 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
            <Video className="w-6 h-6" />
          </div>
        </div>

        <div className="stat-card glass flex items-center justify-between">
          <div className="space-y-1">
            <p className="text-slate-500 text-xs font-semibold uppercase tracking-wider">Active Tasks</p>
            <h3 className="text-3xl font-extrabold text-white">{activeJobs}</h3>
          </div>
          <div className="w-12 h-12 rounded-xl bg-violet-500/10 border border-violet-500/20 flex items-center justify-center text-violet-400">
            <Cpu className={`w-6 h-6 ${activeJobs > 0 ? 'animate-spin-slow' : ''}`} />
          </div>
        </div>

        <div className="stat-card glass flex items-center justify-between">
          <div className="space-y-1">
            <p className="text-slate-500 text-xs font-semibold uppercase tracking-wider">Clips Generated</p>
            <h3 className="text-3xl font-extrabold text-white">{totalClips}</h3>
          </div>
          <div className="w-12 h-12 rounded-xl bg-pink-500/10 border border-pink-500/20 flex items-center justify-center text-pink-400">
            <Film className="w-6 h-6" />
          </div>
        </div>
      </div>

      {/* Main Grid: Create CTA + Job List */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        
        {/* Left Column: Create New CTA */}
        <div className="lg:col-span-4 space-y-6">
          <div className="glass-brand glow-brand rounded-3xl p-6 relative overflow-hidden flex flex-col justify-between min-h-[300px]">
            {/* Background mesh glow */}
            <div className="absolute -top-12 -right-12 w-32 h-32 bg-indigo-500/30 rounded-full blur-3xl pointer-events-none" />
            <div className="absolute -bottom-12 -left-12 w-32 h-32 bg-purple-500/30 rounded-full blur-3xl pointer-events-none" />

            <div className="space-y-4 relative z-10">
              <div className="w-12 h-12 rounded-2xl bg-white/10 flex items-center justify-center text-white">
                <TrendingUp className="w-6 h-6 text-brand-400" />
              </div>
              <h2 className="text-2xl font-bold text-white leading-tight">Ready to go viral?</h2>
              <p className="text-indigo-200/80 text-sm">
                Paste any YouTube URL, configure your favorite subtitle templates, and mix it with engaging background gameplay to explode your views on shorts.
              </p>
            </div>

            <button
              onClick={() => navigate('/create')}
              className="mt-8 w-full py-3.5 px-6 rounded-xl font-bold bg-white text-indigo-950 hover:bg-indigo-50 transition-all flex items-center justify-center gap-2 group shadow-lg active:scale-98"
            >
              <span>Create New Short</span>
              <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
            </button>
          </div>
        </div>

        {/* Right Column: Recent Jobs */}
        <div className="lg:col-span-8 space-y-4">
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <Activity className="w-5 h-5 text-indigo-400" />
            <span>Recent Projects</span>
          </h2>

          {loading ? (
            <div className="space-y-4">
              {[1, 2, 3].map(i => (
                <div key={i} className="glass rounded-2xl p-5 flex items-center gap-4 shimmer h-24" />
              ))}
            </div>
          ) : jobs.length === 0 ? (
            <div className="glass rounded-3xl p-12 text-center flex flex-col items-center justify-center space-y-4 border-dashed border-white/10">
              <div className="w-16 h-16 rounded-full bg-white/5 flex items-center justify-center border border-white/10 text-slate-500 mb-2">
                <Video className="w-8 h-8" />
              </div>
              <h3 className="text-lg font-bold text-white">No projects yet</h3>
              <p className="text-slate-400 max-w-sm text-sm">
                Get started by converting your first YouTube video into viral shorts now.
              </p>
              <button
                onClick={() => navigate('/create')}
                className="btn-ghost text-xs px-4 py-2 mt-2"
              >
                Start Scraping & Clipping
              </button>
            </div>
          ) : (
            <div className="space-y-4 max-h-[600px] overflow-y-auto pr-2">
              {jobs.map(job => (
                <div
                  key={job.id}
                  onClick={() => navigate(`/results/${job.id}`)}
                  className="glass card-hover rounded-2xl p-5 flex items-center gap-4 cursor-pointer relative group"
                >
                  {/* Thumbnail / Placeholder */}
                  <div className="w-24 aspect-video rounded-xl bg-surface-900 border border-white/10 overflow-hidden flex-shrink-0 relative flex items-center justify-center">
                    {job.thumbnail_url ? (
                      <img 
                        src={job.thumbnail_url} 
                        alt={job.title} 
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      <Video className="w-6 h-6 text-slate-500" />
                    )}
                    
                    {/* Small overlay play button for done videos */}
                    {job.status === 'done' && (
                      <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity">
                        <Play className="w-6 h-6 text-white" fill="currentColor" />
                      </div>
                    )}
                  </div>

                  {/* Title & Info */}
                  <div className="flex-1 min-w-0 space-y-1">
                    <h4 className="font-bold text-white truncate text-base leading-tight pr-4">
                      {job.title || 'Processing long-form video...'}
                    </h4>
                    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-400">
                      {job.channel && <span className="font-medium text-slate-300">{job.channel}</span>}
                      <span>{new Date(job.created_at).toLocaleDateString(undefined, {
                        month: 'short',
                        day: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit'
                      })}</span>
                      {job.clip_count > 0 && (
                        <span className="text-brand-400 font-semibold">{job.clip_count} clips ready</span>
                      )}
                    </div>

                    {/* Progress Bar for active jobs */}
                    {!['done', 'error'].includes(job.status) && (
                      <div className="space-y-1 mt-2">
                        <div className="flex items-center justify-between text-[10px]">
                          <span className="text-brand-400 capitalize animate-pulse font-medium">
                            {job.current_step || job.status}...
                          </span>
                          <span className="text-slate-400">{job.progress}%</span>
                        </div>
                        <div className="w-full h-1 bg-surface-900 rounded-full overflow-hidden">
                          <div 
                            className="h-full progress-bar" 
                            style={{ width: `${job.progress}%` }}
                          />
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Action Badges / Controls */}
                  <div className="flex items-center gap-3" onClick={e => e.stopPropagation()}>
                    {job.status === 'done' && (
                      <span className="hidden sm:inline-flex px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 shadow-[0_0_15px_rgba(16,185,129,0.1)]">
                        Ready
                      </span>
                    )}
                    {job.status === 'error' && (
                      <div 
                        className="flex items-center gap-1 text-pink-400 bg-pink-500/10 border border-pink-500/20 px-2.5 py-1 rounded-full text-xs font-medium"
                        title={job.error_message}
                      >
                        <AlertTriangle className="w-3.5 h-3.5" />
                        <span>Failed</span>
                      </div>
                    )}

                    <button
                      onClick={(e) => handleDeleteJob(job.id, e)}
                      className="p-2 rounded-xl text-slate-500 hover:text-pink-400 hover:bg-pink-500/10 transition-colors"
                      title="Delete project"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </motion.div>
  )
}
