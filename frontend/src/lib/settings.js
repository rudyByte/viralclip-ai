const DEFAULTS_KEY = 'viralclip_defaults'

export const defaultSettings = {
  clipMinDuration: 30,
  clipMaxDuration: 60,
  captionStyle: 'hormozi',
  backgroundType: 'none',
  layoutTemplate: 'split_50_50',
  resolution: '720p',
  numClips: 3,
}

export function loadDefaults() {
  try {
    const saved = localStorage.getItem(DEFAULTS_KEY)
    return saved ? { ...defaultSettings, ...JSON.parse(saved) } : defaultSettings
  } catch {
    return defaultSettings
  }
}

export function saveDefaults(settings) {
  localStorage.setItem(DEFAULTS_KEY, JSON.stringify({ ...defaultSettings, ...settings }))
}

export function resetDefaults() {
  localStorage.removeItem(DEFAULTS_KEY)
}
