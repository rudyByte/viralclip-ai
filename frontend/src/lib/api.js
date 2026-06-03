import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: `${API_BASE_URL}/api`,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

// ── Video / Jobs ─────────────────────────────────────────────────
export const processVideo = (data) =>
  api.post('/video/process', data).then((r) => r.data)

export const getJobStatus = (jobId) =>
  api.get(`/video/status/${jobId}`).then((r) => r.data)

export const listJobs = (limit = 20, offset = 0) =>
  api.get(`/video/jobs?limit=${limit}&offset=${offset}`).then((r) => r.data)

export const deleteJob = (jobId) =>
  api.delete(`/video/${jobId}`).then((r) => r.data)

// ── Clips ─────────────────────────────────────────────────────────
export const getClips = (jobId) =>
  api.get(`/clips/${jobId}`).then((r) => r.data)

export const getClip = (clipId) =>
  api.get(`/clips/detail/${clipId}`).then((r) => r.data)

export const getClipHooks = (clipId) =>
  api.get(`/clips/${clipId}/hooks`).then((r) => r.data)

export const regenerateClip = (clipId, data) =>
  api.post(`/clips/${clipId}/regenerate`, data).then((r) => r.data)

export const getDownloadUrl = (clipId) =>
  `${API_BASE_URL}/api/clips/${clipId}/download`

export const getPreviewUrl = (clipId) =>
  `${API_BASE_URL}/api/clips/${clipId}/preview`


// ── Config ────────────────────────────────────────────────────────
export const getConfig = () =>
  api.get('/config').then((r) => r.data)

export const healthCheck = () =>
  api.get('/health', { baseURL: API_BASE_URL }).then((r) => r.data)

// ── Settings / Cookies ───────────────────────────────────────────
export const getCookiesStatus = () =>
  api.get('/settings/cookies').then((r) => r.data)

export const saveCookies = (cookies) =>
  api.post('/settings/cookies', { cookies }).then((r) => r.data)

export const deleteCookies = () =>
  api.delete('/settings/cookies').then((r) => r.data)

// ── WebSocket helper ──────────────────────────────────────────────
export const createJobSocket = (jobId, onMessage, onClose) => {
  const wsBase = API_BASE_URL.replace(/^http/, 'ws')
  const url = `${wsBase}/ws/job/${jobId}`
  const ws = new WebSocket(url)
  ws.onmessage = (e) => onMessage(JSON.parse(e.data))
  ws.onclose = onClose
  ws.onerror = (e) => console.error('WS error:', e)
  return ws
}

export default api
