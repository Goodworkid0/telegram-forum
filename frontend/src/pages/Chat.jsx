import { useState, useEffect, useRef, useCallback } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import api from '../lib/api'
import { useAuthStore } from '../store/authStore'
import { timeAgo, displayName } from '../lib/utils'
import { useT } from '../lib/i18n'
import { useToast } from '../components/Toast'
import { globalConfirm } from '../components/ConfirmModal'
import { Card, Button, EmptyState, LoadingState, roleStyle } from '../components/ui'
import { Send, Trash2, MessagesSquare, X, User, MessageSquare, MicOff, Ban, ShieldAlert } from 'lucide-react'

const POLL_INTERVAL = 3000

// Render message text, highlighting @username mentions. Only exact @\w+ tokens
// are wrapped in styled spans; everything else is plain (React-escaped) text,
// so there is no HTML-injection surface.
function renderContent(text, selfUsername) {
  if (!text) return text
  return text.split(/(@\w+)/g).map((part, i) => {
    if (/^@\w+$/.test(part)) {
      const isMe = selfUsername && part.slice(1).toLowerCase() === selfUsername.toLowerCase()
      return (
        <span
          key={i}
          className={isMe
            ? 'bg-primary-500/30 text-primary-100 rounded px-0.5 font-semibold'
            : 'text-primary-400 font-medium'}
        >
          {part}
        </span>
      )
    }
    return part
  })
}

export default function Chat() {
  const t = useT()
  const { user, isModerator, isAdmin } = useAuthStore()
  const navigate = useNavigate()
  const { showToast } = useToast()
  const isStaff = isModerator()
  const canBan = isAdmin()
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(true)
  const [hasMore, setHasMore] = useState(false)
  const [sending, setSending] = useState(false)
  const [lastSeenId, setLastSeenId] = useState(0)
  const [popupUser, setPopupUser] = useState(null)
  // Moderation modal: { userId, username, action: 'mute' | 'ban' } or null
  const [modTarget, setModTarget] = useState(null)
  const [modReason, setModReason] = useState('')
  const [modBusy, setModBusy] = useState(false)
  // @-mention autocomplete: mentionQuery is the partial after '@' (null = closed)
  const [mentionQuery, setMentionQuery] = useState(null)
  const [mentionItems, setMentionItems] = useState([])
  const [mentionIndex, setMentionIndex] = useState(0)
  const popupRef = useRef(null)
  const bottomRef = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => {
    if (!popupUser) return
    const handler = (e) => { if (popupRef.current && !popupRef.current.contains(e.target)) setPopupUser(null) }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [popupUser])


  // Build @-mention suggestions: instant local matches from people already in
  // the loaded chat, plus a debounced /api/users search once 2+ chars are typed.
  useEffect(() => {
    if (mentionQuery === null) { setMentionItems([]); return }
    const q = mentionQuery.toLowerCase()
    const seen = new Map()
    for (const m of messages) {
      if (m.user_id && (m.username || m.first_name) && m.user_id !== user?.id && !seen.has(m.user_id)) {
        seen.set(m.user_id, { id: m.user_id, username: m.username, first_name: m.first_name, show_telegram: m.show_telegram, avatar_url: m.avatar_url, role: m.role })
      }
    }
    // Match against the privacy-respecting display name (never a hidden handle).
    const local = [...seen.values()].filter(u =>
      !q || displayName(u, false).toLowerCase().includes(q) || (u.first_name || '').toLowerCase().includes(q)
    )
    setMentionItems(local.slice(0, 6))
    setMentionIndex(0)

    if (mentionQuery.length < 2) return
    const t = setTimeout(async () => {
      try {
        const { data } = await api.get('/api/users', { params: { q: mentionQuery, per_page: 8 } })
        const byId = new Map(local.map(u => [u.id, u]))
        for (const u of data) {
          if (u.id !== user?.id && !byId.has(u.id)) byId.set(u.id, u)
        }
        setMentionItems([...byId.values()].slice(0, 6))
      } catch {}
    }, 220)
    return () => clearTimeout(t)
  }, [mentionQuery, messages, user?.id])

  const handleStartDM = async (targetId) => {
    try {
      const { data } = await api.post('/api/dm/start', { user_id: targetId, message: 'Hey!' })
      setPopupUser(null)
      navigate(`/messages/${data.conversation_id}`)
    } catch (err) {
      showToast(err.response?.data?.detail || t('chat.toast_start_failed'), 'error')
    }
  }

  const scrollToBottom = useCallback((smooth = false) => {
    bottomRef.current?.scrollIntoView({ behavior: smooth ? 'smooth' : 'instant' })
  }, [])

  const loadMessages = useCallback(async (beforeId = null) => {
    try {
      const params = { limit: 50 }
      if (beforeId) params.before_id = beforeId
      const { data } = await api.get('/api/chat/messages', { params })
      if (beforeId) {
        setMessages(prev => [...data.messages, ...prev])
      } else {
        setMessages(data.messages)
        setTimeout(() => scrollToBottom(), 50)
      }
      setHasMore(data.has_more)
      if (data.messages.length > 0 && !beforeId) {
        setLastSeenId(data.messages[data.messages.length - 1].id)
      }
    } catch (err) {
      console.error('Failed to load chat:', err)
    } finally {
      setLoading(false)
    }
  }, [scrollToBottom])

  useEffect(() => {
    loadMessages()
  }, [loadMessages])

  // Poll for new messages
  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const { data } = await api.get('/api/chat/messages', { params: { limit: 10 } })
        setMessages(prev => {
          const newIds = new Set(prev.map(m => m.id))
          const fresh = data.messages.filter(m => !newIds.has(m.id))
          return fresh.length > 0 ? [...prev, ...fresh] : prev
        })
      } catch {}
    }, POLL_INTERVAL)
    return () => clearInterval(interval)
  }, [])

  // Auto-scroll when new messages come in
  useEffect(() => {
    if (messages.length > 0) {
      const lastMsg = messages[messages.length - 1]
      if (lastMsg.user_id === user?.id || lastMsg.id > lastSeenId) {
        scrollToBottom(true)
      }
    }
  }, [messages.length])

  // Load older messages on scroll to top
  const handleScroll = useCallback((e) => {
    if (e.target.scrollTop < 50 && hasMore && !loading) {
      const oldestId = messages[0]?.id
      if (oldestId) loadMessages(oldestId)
    }
  }, [hasMore, loading, messages, loadMessages])

  const handleSend = async (e) => {
    e?.preventDefault()
    const trimmed = input.trim()
    if (!trimmed || sending) return
    try {
      setSending(true)
      const { data } = await api.post('/api/chat/messages', { content: trimmed })
      setMessages(prev => [...prev, data])
      setInput('')
      setMentionQuery(null)
      setLastSeenId(data.id)
      scrollToBottom(true)
      inputRef.current?.focus()
    } catch (err) {
      showToast(err.response?.data?.detail || t('chat.toast_send_failed'), 'error')
    } finally {
      setSending(false)
    }
  }

  const handleDelete = async (msgId) => {
    if (!(await globalConfirm(t('chat.delete_confirm')))) return
    try {
      await api.delete(`/api/chat/messages/${msgId}`)
      setMessages(prev => prev.map(m => m.id === msgId ? { ...m, is_deleted: true, content: '[deleted]' } : m))
    } catch (err) {
      showToast(err.response?.data?.detail || t('chat.toast_delete_failed'), 'error')
    }
  }

  const openMod = (action, msg) => {
    setModTarget({ userId: msg.user_id, username: displayName(msg, false), action })
    setModReason('')
    setPopupUser(null)
  }

  const closeMod = () => { setModTarget(null); setModReason('') }

  // duration: minutes for mute, days for ban; null = permanent
  const submitMod = async (duration) => {
    if (!modTarget) return
    if (!modReason.trim()) { showToast(t('chat.reason_required'), 'error'); return }
    const { userId, action } = modTarget
    try {
      setModBusy(true)
      if (action === 'mute') {
        await api.post(`/api/mod/mute/${userId}`, null, {
          params: { reason: modReason.trim(), ...(duration ? { duration_minutes: duration } : {}) },
        })
        showToast(t('chat.user_muted'), 'success')
      } else {
        // Ban is admin-only (matches the Profile page), so use the admin endpoint
        // which is server-side gated by get_current_admin.
        await api.post(`/api/admin/users/${userId}/ban`, null, {
          params: { reason: modReason.trim(), ...(duration ? { duration_days: duration } : {}) },
        })
        showToast(t('chat.user_banned'), 'success')
      }
      closeMod()
    } catch (err) {
      showToast(err.response?.data?.detail || t('chat.action_failed'), 'error')
    } finally {
      setModBusy(false)
    }
  }

  // Detect an in-progress @mention at the caret and open/close the dropdown.
  const handleInputChange = (e) => {
    const value = e.target.value
    setInput(value)
    const caret = e.target.selectionStart ?? value.length
    const m = value.slice(0, caret).match(/(?:^|\s)@(\w*)$/)
    setMentionQuery(m ? m[1] : null)
  }

  // Replace the active "@partial" token at the caret with "@username ".
  const applyMention = (u) => {
    const el = inputRef.current
    const caret = el?.selectionStart ?? input.length
    const before = input.slice(0, caret)
    const m = before.match(/(?:^|\s)@(\w*)$/)
    if (!m) return
    // Insert the privacy-respecting mention: the handle when visible, the
    // display name when hidden (the backend mention matcher accepts both).
    const at = caret - m[1].length - 1
    const newBefore = input.slice(0, at) + '@' + displayName(u, false) + ' '
    setInput(newBefore + input.slice(caret))
    setMentionQuery(null)
    setTimeout(() => {
      el?.focus()
      el?.setSelectionRange(newBefore.length, newBefore.length)
    }, 0)
  }

  const mentionOpen = mentionQuery !== null && mentionItems.length > 0

  const handleKeyDown = (e) => {
    if (mentionOpen) {
      if (e.key === 'ArrowDown') { e.preventDefault(); setMentionIndex(i => (i + 1) % mentionItems.length); return }
      if (e.key === 'ArrowUp') { e.preventDefault(); setMentionIndex(i => (i - 1 + mentionItems.length) % mentionItems.length); return }
      if (e.key === 'Enter' || e.key === 'Tab') { e.preventDefault(); applyMention(mentionItems[mentionIndex]); return }
      if (e.key === 'Escape') { e.preventDefault(); setMentionQuery(null); return }
    }
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  if (loading) {
    return <LoadingState label={t('chat.loading')} className="min-h-[40vh] flex flex-col items-center justify-center" />
  }

  return (
    <div className="flex flex-col h-[calc(100vh-10rem)]">
      {/* Header — minimal bar */}
      <div className="flex items-center justify-between mb-3 flex-shrink-0 px-1">
        <div className="flex items-center gap-2">
          <MessagesSquare size={16} className="text-primary-400" />
          <h1 className="text-sm font-semibold text-dark-100">{t('nav.chatbox')}</h1>
        </div>
        <button
          onClick={() => navigate(-1)}
          className="p-1.5 hover:bg-dark-700 rounded-lg transition-colors text-dark-400 hover:text-white"
          title={t('chat.close')}
        >
          <X size={18} />
        </button>
      </div>

      {/* Messages */}
      <div
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto space-y-1.5 bg-dark-900/40 rounded-xl border border-primary-500/10 p-3"
      >
        {hasMore && (
          <div className="text-center py-2">
            <button
              onClick={() => loadMessages(messages[0]?.id)}
              className="text-xs text-primary-400 hover:underline"
            >
              {t('chat.load_older')}
            </button>
          </div>
        )}

        {messages.length === 0 && (
          <EmptyState icon={MessagesSquare} className="h-full flex flex-col items-center justify-center">
            {t('chat.empty')}
          </EmptyState>
        )}

        {messages.map((msg, idx) => {
          const isOwn = msg.user_id === user?.id
          const showHeader = idx === 0 || messages[idx - 1]?.user_id !== msg.user_id

          return (
            <div key={msg.id} className={`${showHeader ? 'mt-2' : 'mt-0.5'} relative`}>
              {showHeader && (
                <div className={`flex items-center gap-2 mb-0.5 relative ${isOwn ? 'flex-row-reverse' : ''}`}>
                  <button
                    onClick={() => setPopupUser(popupUser?.user_id === msg.user_id ? null : msg)}
                    className="flex-shrink-0 w-6 h-6 rounded-full bg-dark-700 flex items-center justify-center overflow-hidden hover:ring-1 hover:ring-primary-500 ring-1 ring-dark-600"
                    style={(() => {
                      try {
                        const t = typeof msg.profile_theme === 'string' ? JSON.parse(msg.profile_theme) : msg.profile_theme
                        if (t?.avatar_border) {
                          const ring = `0 0 0 1px ${t.avatar_border}`
                          const glow = t.avatar_glow ? `0 0 6px ${t.avatar_border}` : ''
                          return { boxShadow: [ring, glow].filter(Boolean).join(', ') }
                        }
                      } catch { }
                      return {}
                    })()}
                  >
                    {msg.avatar_url ? (
                      <img src={msg.avatar_url} alt="" className="w-full h-full object-cover" />
                    ) : (
                      <span className="text-[10px] font-bold text-dark-300">
                        {displayName(msg, false)[0]?.toUpperCase()}
                      </span>
                    )}
                  </button>
                  <button
                    onClick={() => setPopupUser(popupUser?.user_id === msg.user_id ? null : msg)}
                    className={`text-xs font-semibold hover:underline ${roleStyle(msg.role).text}`}
                    style={(() => {
                      try {
                        const t = typeof msg.profile_theme === 'string' ? JSON.parse(msg.profile_theme) : msg.profile_theme
                        if (t?.name_color) return { color: t.name_color }
                      } catch { }
                      return {}
                    })()}
                  >
                    {displayName(msg)}
                  </button>
                  <span className="text-[10px] text-dark-500">{timeAgo(msg.created_at)}</span>
                  {/* User popup */}
                  <AnimatePresence>
                    {popupUser?.user_id === msg.user_id && (
                      <motion.div
                        ref={popupRef}
                        initial={{ opacity: 0, scale: 0.95, y: -4 }}
                        animate={{ opacity: 1, scale: 1, y: 0 }}
                        exit={{ opacity: 0, scale: 0.95, y: -4 }}
                        className={`absolute z-30 ${isOwn ? 'right-0' : 'left-0'} top-8`}
                      >
                        <Card className="!p-0 !py-1.5 min-w-[150px] shadow-xl">
                          <div className="px-3 py-1 text-[10px] text-dark-500 uppercase tracking-wider font-semibold border-b border-primary-500/10">
                            {displayName(msg)}
                          </div>
                          <Link to={`/profile/${msg.user_id}`} onClick={() => setPopupUser(null)}
                            className="flex items-center gap-2.5 w-full text-left px-3 py-2 text-xs text-dark-200 hover:text-white hover:bg-dark-700/50 transition-colors">
                            <User className="w-3.5 h-3.5 text-dark-400" />{t('chat.view_profile')}
                          </Link>
                          {msg.user_id !== user?.id && (
                            <button onClick={() => handleStartDM(msg.user_id)}
                              className="flex items-center gap-2.5 w-full text-left px-3 py-2 text-xs text-dark-200 hover:text-white hover:bg-dark-700/50 transition-colors">
                              <MessageSquare className="w-3.5 h-3.5 text-dark-400" />{t('chat.send_message')}
                            </button>
                          )}
                          {isStaff && msg.user_id !== user?.id && (
                            <div className="border-t border-primary-500/10 mt-1 pt-1">
                              <div className="px-3 py-1 text-[10px] text-amber-500/70 uppercase tracking-wider font-semibold flex items-center gap-1.5">
                                <ShieldAlert className="w-3 h-3" /> {t('chat.moderation')}
                              </div>
                              <button onClick={() => openMod('mute', msg)}
                                className="flex items-center gap-2.5 w-full text-left px-3 py-2 text-xs text-amber-300 hover:text-amber-200 hover:bg-amber-500/10 transition-colors">
                                <MicOff className="w-3.5 h-3.5" />{t('chat.mute_user')}
                              </button>
                              {canBan && (
                                <button onClick={() => openMod('ban', msg)}
                                  className="flex items-center gap-2.5 w-full text-left px-3 py-2 text-xs text-red-400 hover:text-red-300 hover:bg-red-500/10 transition-colors">
                                  <Ban className="w-3.5 h-3.5" />{t('chat.ban_user')}
                                </button>
                              )}
                            </div>
                          )}
                        </Card>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              )}
              <div className={`group flex items-center gap-1.5 ${isOwn ? 'justify-end' : 'justify-start'}`}>
                {!msg.is_deleted && isOwn && (
                  <button
                    onClick={() => handleDelete(msg.id)}
                    className="opacity-100 md:opacity-0 md:group-hover:opacity-100 text-dark-600 hover:text-red-400 transition-opacity flex-shrink-0"
                    title={t('chat.delete_message')}
                  >
                    <Trash2 size={13} />
                  </button>
                )}
                <div
                  style={{ fontVariantEmoji: 'text' }}
                  className={`max-w-[80%] rounded-xl px-3 py-1.5 text-sm break-words ${
                    msg.is_deleted
                      ? 'bg-dark-700/50 text-dark-500 italic'
                      : isOwn
                        ? 'bg-primary-500/20 text-white rounded-br-md'
                        : 'bg-dark-700/80 text-dark-200 rounded-bl-md'
                  }`}
                >
                  {msg.is_deleted ? msg.content : renderContent(msg.content, user ? displayName(user, false) : null)}
                </div>
                {!msg.is_deleted && isStaff && !isOwn && (
                  <button
                    onClick={() => handleDelete(msg.id)}
                    className="opacity-100 md:opacity-0 md:group-hover:opacity-100 text-dark-600 hover:text-red-400 transition-opacity flex-shrink-0"
                    title={t('chat.delete_message_mod')}
                  >
                    <Trash2 size={13} />
                  </button>
                )}
              </div>
            </div>
          )
        })}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <form onSubmit={handleSend} className="flex-shrink-0 mt-2 relative">
        {/* @-mention autocomplete */}
        {mentionOpen && (
          <div className="absolute bottom-full mb-2 left-0 sm:left-12 right-0 sm:right-auto sm:min-w-[240px] max-h-56 overflow-y-auto bg-dark-800 border border-primary-500/20 rounded-xl shadow-xl z-30">
            {mentionItems.map((u, i) => (
              <button
                type="button"
                key={u.id}
                onMouseDown={(e) => { e.preventDefault(); applyMention(u) }}
                onMouseEnter={() => setMentionIndex(i)}
                className={`flex items-center gap-2 w-full text-left px-3 py-2 transition-colors ${
                  i === mentionIndex ? 'bg-primary-500/15' : 'hover:bg-dark-700/50'
                }`}
              >
                <span className="flex-shrink-0 w-6 h-6 rounded-full bg-dark-700 flex items-center justify-center overflow-hidden ring-1 ring-dark-600">
                  {u.avatar_url
                    ? <img src={u.avatar_url} alt="" className="w-full h-full object-cover" />
                    : <span className="text-[10px] font-bold text-dark-300">{displayName(u, false)[0]?.toUpperCase()}</span>}
                </span>
                <span className="text-sm font-medium text-primary-400">{displayName(u)}</span>
                {u.first_name && u.first_name !== displayName(u, false) && <span className="text-xs text-dark-500 truncate">{u.first_name}</span>}
              </button>
            ))}
          </div>
        )}

        <div className="flex gap-2">
          {/* Emoji input is handled by Telegram's native keyboard. A custom
              in-app picker bulk-rendered native color-emoji glyphs, which crashed
              the (older-Chromium) Telegram WebView renderer on open. */}
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            placeholder={t('chat.type_placeholder')}
            maxLength={1000}
            className="flex-1 min-w-0 bg-dark-900/60 border border-primary-500/15 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-primary-500/50 focus:shadow-[0_0_0_1px_rgba(0,200,230,0.35)] transition-all placeholder-dark-500"
          />
          <Button
            type="submit"
            variant="primary"
            icon={Send}
            disabled={!input.trim() || sending}
            className="!rounded-xl px-4 py-2.5"
          >
            <span className="hidden sm:inline">{t('chat.send')}</span>
          </Button>
        </div>
      </form>

      {/* Moderation modal (mute / ban) */}
      <AnimatePresence>
        {modTarget && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
            onMouseDown={(e) => { if (e.target === e.currentTarget) closeMod() }}
          >
            <motion.div
              initial={{ scale: 0.95, y: 8 }}
              animate={{ scale: 1, y: 0 }}
              exit={{ scale: 0.95, y: 8 }}
            >
              <Card className="w-[320px] max-w-full">
                <div className="flex items-center gap-2 mb-3">
                  {modTarget.action === 'ban'
                    ? <Ban className="w-4 h-4 text-red-400" />
                    : <MicOff className="w-4 h-4 text-amber-400" />}
                  <h3 className="font-semibold text-white text-sm">
                    {t(modTarget.action === 'ban' ? 'chat.ban_title' : 'chat.mute_title', { username: modTarget.username })}
                  </h3>
                  <button onClick={closeMod} className="ml-auto text-dark-500 hover:text-white">
                    <X size={16} />
                  </button>
                </div>

                <input
                  autoFocus
                  type="text"
                  value={modReason}
                  onChange={e => setModReason(e.target.value)}
                  placeholder={t('chat.reason_placeholder')}
                  maxLength={200}
                  className="w-full bg-dark-900/60 border border-primary-500/15 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary-500/50 placeholder-dark-500 mb-3"
                />

                <p className="text-[11px] text-dark-500 mb-1.5 uppercase tracking-wider font-semibold">
                  {t('chat.duration')}
                </p>
                <div className="grid grid-cols-3 gap-1.5">
                  {(modTarget.action === 'ban'
                    ? [{ label: t('chat.duration_1d'), v: 1 }, { label: t('chat.duration_7d'), v: 7 }, { label: t('chat.duration_30d'), v: 30 }, { label: t('chat.duration_permanent'), v: null }]
                    : [{ label: t('chat.duration_10m'), v: 10 }, { label: t('chat.duration_1h'), v: 60 }, { label: t('chat.duration_6h'), v: 360 }, { label: t('chat.duration_1d'), v: 1440 }, { label: t('chat.duration_permanent'), v: null }]
                  ).map(opt => (
                    <button
                      key={opt.label}
                      disabled={modBusy}
                      onClick={() => submitMod(opt.v)}
                      className={`px-2 py-1.5 rounded-lg text-xs font-medium border transition-colors disabled:opacity-50 ${
                        modTarget.action === 'ban'
                          ? 'border-red-500/30 text-red-300 hover:bg-red-500/15'
                          : 'border-amber-500/30 text-amber-300 hover:bg-amber-500/15'
                      }`}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
              </Card>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
