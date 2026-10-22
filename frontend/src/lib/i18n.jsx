/**
 * Lightweight i18n. Flat string dictionaries per language, key fallback chain
 * ru -> en -> key. `{name}` placeholders are interpolated from `vars`.
 *
 * Usage in components:
 *   const t = useT()               // re-renders on language change
 *   <h1>{t('settings.title')}</h1>
 *
 * Outside React (rare): import { t } from '../lib/i18n'
 *
 * Adding strings: put the key in BOTH locales/en/<domain>.js and
 * locales/ru/<domain>.js. Domain files exist so parallel work on different
 * pages never touches the same file.
 */
import { useMemo } from 'react'
import { create } from 'zustand'
import en from './locales/en'
import ru from './locales/ru'
import es from './locales/es'
import zh from './locales/zh'

const DICTS = { en, ru, es, zh }
export const LANGUAGES = [
  { code: 'en', label: 'English' },
  { code: 'ru', label: 'Русский' },
  { code: 'es', label: 'Español' },
  { code: 'zh', label: '中文' },
]

// BCP-47 locales for date formatting, keyed by UI language.
const DATE_LOCALES = { en: 'en-US', ru: 'ru-RU', es: 'es-ES', zh: 'zh-CN' }

/** Date-formatting locale for the current UI language. */
export function getDateLocale() {
  return DATE_LOCALES[useLangStore.getState().lang] || 'en-US'
}

const storedLang = typeof localStorage !== 'undefined' ? localStorage.getItem('lang') : null

export const useLangStore = create((set) => ({
  lang: DICTS[storedLang] ? storedLang : 'en',
  setLang: (lang) => {
    if (!DICTS[lang]) return
    try { localStorage.setItem('lang', lang) } catch { /* storage unavailable */ }
    set({ lang })
  },
}))

function translate(lang, key, vars) {
  let s = DICTS[lang]?.[key] ?? DICTS.en[key] ?? key
  if (vars) {
    for (const [k, v] of Object.entries(vars)) {
      s = s.replaceAll(`{${k}}`, String(v))
    }
  }
  return s
}

/** Non-reactive translate — for code outside components. */
export function t(key, vars) {
  return translate(useLangStore.getState().lang, key, vars)
}

/** Reactive translate hook — re-renders the component when language changes. */
export function useT() {
  const lang = useLangStore(s => s.lang)
  return useMemo(() => (key, vars) => translate(lang, key, vars), [lang])
}
