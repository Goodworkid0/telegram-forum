import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import api from '../../lib/api'
import { getRoleStyle } from '../../components/RoleBadge'
import { displayName } from '../../lib/utils'
import { useT } from '../../lib/i18n'

export default function MentionTextarea({ value, onChange, placeholder, rows, className, textareaRef }) {
  const t = useT()
  const [mentionResults, setMentionResults] = useState([])
  const [mentionStart, setMentionStart] = useState(null) // char index of '@'
  const [selectedIdx, setSelectedIdx] = useState(0)
  const [showDropdown, setShowDropdown] = useState(false)
  const debounceRef = useRef(null)
  const containerRef = useRef(null)
  const internalRef = useRef(null)
  const ref = textareaRef || internalRef

  useEffect(() => () => clearTimeout(debounceRef.current), [])

  const handleChange = (e) => {
    const val = e.target.value
    const cursor = e.target.selectionStart
    onChange(val)

    // Extract word at cursor: find '@' before cursor with 2+ chars after it
    const before = val.slice(0, cursor)
    const match = before.match(/@(\w{2,})$/)

    if (match) {
      const query = match[1]
      setMentionStart(cursor - match[0].length)
      setSelectedIdx(0)

      clearTimeout(debounceRef.current)
      debounceRef.current = setTimeout(async () => {
        try {
          const res = await api.get('/api/users', { params: { q: query, per_page: 6 } })
          setMentionResults(res.data || [])
          setShowDropdown((res.data || []).length > 0)
        } catch {
          setShowDropdown(false)
        }
      }, 250)
    } else {
      setShowDropdown(false)
      setMentionStart(null)
      clearTimeout(debounceRef.current)
    }
  }

  // Insert the privacy-respecting mention: the handle when the user shows it,
  // their display name otherwise (the backend mention matcher accepts both).
  const selectMention = (u) => {
    if (mentionStart == null) return
    const cursor = ref.current.selectionStart
    const before = value.slice(0, mentionStart)
    const after = value.slice(cursor)
    const inserted = `@${displayName(u, false)} `
    const newVal = before + inserted + after
    onChange(newVal)
    setShowDropdown(false)
    setMentionStart(null)
    setMentionResults([])

    setTimeout(() => {
      const pos = mentionStart + inserted.length
      ref.current.focus()
      ref.current.selectionStart = pos
      ref.current.selectionEnd = pos
    }, 0)
  }

  const handleKeyDown = (e) => {
    if (!showDropdown || mentionResults.length === 0) return

    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setSelectedIdx(i => Math.min(i + 1, mentionResults.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setSelectedIdx(i => Math.max(i - 1, 0))
    } else if (e.key === 'Enter' || e.key === 'Tab') {
      e.preventDefault()
      selectMention(mentionResults[selectedIdx])
    } else if (e.key === 'Escape') {
      setShowDropdown(false)
    }
  }

  return (
    <div ref={containerRef} className="relative">
      <textarea
        ref={ref}
        value={value}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        rows={rows}
        className={className}
      />
      <AnimatePresence>
        {showDropdown && mentionResults.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 4 }}
            transition={{ duration: 0.12 }}
            className="absolute bottom-full left-0 mb-1 w-64 bg-dark-800 border border-dark-600 rounded-lg shadow-xl overflow-hidden z-50"
          >
            <div className="px-3 py-1.5 border-b border-dark-700/50 text-[10px] text-dark-500 uppercase tracking-wider font-semibold">
              {t('forum.mention_user')}
            </div>
            {mentionResults.map((u, i) => (
              <button
                key={u.id}
                type="button"
                onMouseDown={(e) => { e.preventDefault(); selectMention(u) }}
                className={`w-full flex items-center gap-2.5 px-3 py-2 text-left transition-colors ${
                  i === selectedIdx ? 'bg-primary-500/15 text-white' : 'text-dark-300 hover:bg-dark-700/50'
                }`}
              >
                <div className="w-7 h-7 rounded-full bg-dark-700 flex-shrink-0 overflow-hidden flex items-center justify-center">
                  {u.avatar_url ? (
                    <img src={u.avatar_url} alt="" className="w-full h-full object-cover" />
                  ) : (
                    <span className="text-xs font-bold text-dark-400">{displayName(u, false)[0].toUpperCase()}</span>
                  )}
                </div>
                <div className="min-w-0">
                  <div className="font-medium text-xs truncate">{displayName(u)}</div>
                    {u.role && (
                    <span className={`text-[9px] font-semibold uppercase ${getRoleStyle(u.role).text}`}>
                      {t(getRoleStyle(u.role).labelKey)}
                    </span>
                  )}
                </div>
              </button>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
