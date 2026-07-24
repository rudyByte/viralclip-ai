const DEFAULTS_KEY = 'viralclip_defaults'

export const defaultSettings = {
  clipMinDuration: 30,
  clipMaxDuration: 60,
  captionStyle: 'hormozi',
  backgroundType: 'subway',
  layoutTemplate: 'split_50_50',
  resolution: '720p',
  numClips: 3,
  gameplayDefaultsVersion: 2,
}

export function loadDefaults() {
  try {
    const saved = localStorage.getItem(DEFAULTS_KEY)
    if (!saved) return defaultSettings
    const parsed = JSON.parse(saved)
    const merged = { ...defaultSettings, ...parsed }
    if ((parsed.gameplayDefaultsVersion || 1) < 2 && merged.backgroundType === 'none') {
      merged.backgroundType = 'subway'
      merged.layoutTemplate = 'split_50_50'
    }
    return merged
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
