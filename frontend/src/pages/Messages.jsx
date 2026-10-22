import { useState, useEffect, useRef, useCallback } from 'react'
import { Link, useParams, useNavigate } from 'react-router-dom'
// framer-motion removed for WebView compat
import {
  MessageCircle, Search, X, PenSquare, Send, Check, CheckCheck,
  User, Tag as TagIcon, ArrowLeft, MoreVertical, Pencil, Trash2,
  AlertCircle, RefreshCw
} from 'lucide-react'
import api from '../lib/api'
import { useAuthStore } from '../store/authStore'
import { useToast } from '../components/Toast'
import { timeAgo, formatDate, parseDate, nameColorStyle, displayName } from '../lib/utils'
import { useT } from '../lib/i18n'
import { Button, EmptyState, LoadingState } from '../components/ui'

/* ------------------------------------------------------------------ helpers */
const formatTime = (dateStr) => {
  const date = parseDate(dateStr)
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

const cx = (...parts) => parts.filter(Boolean).join(' ')

/* ------------------------------------------------------------- MessageBubble */
function MessageBubble({ msg, isOwn, onEdit, onDelete }) {
  const t = useT()
  const [menuOpen, setMenuOpen] = useState(false)
  const menuRef = useRef(null)
  const canEdit = isOwn && !msg.is_deleted && (Date.now() - parseDate(msg.created_at).getTime()) < 900000
  const canDelete = isOwn && !msg.is_deleted

  useEffect(() => {
    if (!menuOpen) return
    const close = (e) => { if (menuRef.current && !menuRef.current.contains(e.target)) setMenuOpen(false) }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [menuOpen])

  if (msg.is_deleted) {
    return (
      <div className={`flex ${isOwn ? 'justify-end' : 'justify-start'}`}>
        <div className="max-w-[75%] px-4 py-2 rounded-xl bg-dark-800/30 border border-primary-500/10 italic text-dark-500 text-xs">
          {t('messages.message_deleted')}
        </div>
      </div>
    )
  }

  return (
    <div className={`flex ${isOwn ? 'justify-end' : 'justify-start'} group`}>
      {!isOwn && (
        <div className="w-7 h-7 rounded-full bg-dark-700 overflow-hidden flex-shrink-0 mr-2 mt-auto">
          {msg.sender_avatar ? (
            <img src={msg.sender_avatar} alt="" className="w-full h-full object-cover" />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-[10px] font-bold text-dark-400">
              {(msg.sender_username || '?')[0].toUpperCase()}
            </div>
          )}
        </div>
      )}

      <div className="relative max-w-[75%]">
        {(canEdit || canDelete) && (
          <div ref={menuRef} className={`absolute top-1 ${isOwn ? '-left-8' : '-right-8'} opacity-100 md:opacity-0 md:group-hover:opacity-100 transition-opacity`}>
            <button
              onClick={() => setMenuOpen(!menuOpen)}
              className="w-6 h-6 flex items-center justify-center rounded-full hover:bg-dark-700/50 text-dark-500 hover:text-dark-300"
            >
              <MoreVertical size={14} />
            </button>
              {menuOpen && (
                <div
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.9 }}
                  className={`absolute ${isOwn ? 'left-0' : 'right-0'} top-7 bg-dark-900/95 border border-primary-500/20 rounded-lg shadow-xl overflow-hidden z-50 min-w-[120px]`}
                >
                  {canEdit && (
                    <button
                      onClick={() => { setMenuOpen(false); onEdit(msg) }}
                      className="w-full flex items-center gap-2 px-3 py-2 text-xs text-dark-300 hover:bg-dark-800/70 hover:text-white transition-colors"
                    >
                      <Pencil size={12} /> {t('common.edit')}
                    </button>
                  )}
                  {canDelete && (
                    <button
                      onClick={() => { setMenuOpen(false); onDelete(msg) }}
                      className="w-full flex items-center gap-2 px-3 py-2 text-xs text-red-400 hover:bg-red-500/10 transition-colors"
                    >
                      <Trash2 size={12} /> {t('common.delete')}
                    </button>
                  )}
                </div>
              )}
          </div>
        )}

        <div
          className={`px-4 py-2.5 rounded-xl ${
            isOwn
              ? 'bg-primary-500/20 text-dark-100 border border-primary-500/30 rounded-br-md'
              : 'bg-dark-800/70 text-dark-100 rounded-bl-md border border-primary-500/10'
          }`}
        >
          <p className="text-sm whitespace-pre-wrap break-words leading-relaxed" style={{ fontVariantEmoji: 'text' }}>{msg.content}</p>
          <div className={`flex items-center justify-end gap-1.5 mt-1 ${isOwn ? 'text-primary-300/70' : 'text-dark-500'}`}>
            {msg.is_edited && <span className="text-[9px] italic">{t('messages.edited')}</span>}
            <span className="text-[10px]">{formatTime(msg.created_at)}</span>
            {isOwn && (
              msg.is_read
                ? <CheckCheck size={13} className="text-primary-300" />
                : <Check size={12} />
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

/* ----------------------------------------------------------- ConversationRow */
function ConversationRow({ conv, active, onClick }) {
  const t = useT()
  const other = conv.other_user
  const hasUnread = conv.unread_count > 0

  return (
    <button
      onClick={onClick}
      className={cx(
        'w-full flex items-center gap-3 p-3 rounded-xl border transition-all text-left',
        active
          ? 'bg-primary-500/10 border-primary-500/40 shadow-[0_0_15px_rgba(0,200,230,0.1)]'
          : hasUnread
            ? 'bg-dark-800/70 border-primary-500/30 hover:border-primary-500/50'
            : 'bg-dark-800/30 border-primary-500/10 hover:bg-dark-800/50 hover:border-primary-500/25'
      )}
    >
      <div className="relative flex-shrink-0">
        {other?.avatar_url ? (
          <img src={other.avatar_url} className="w-11 h-11 rounded-full object-cover" alt="" />
        ) : (
          <div className="w-11 h-11 rounded-full bg-dark-700 flex items-center justify-center">
            <User size={18} className="text-dark-400" />
          </div>
        )}
        {other?.is_online && (
          <div className="absolute -bottom-0.5 -right-0.5 w-3 h-3 bg-green-500 rounded-full ring-2 ring-dark-900" />
        )}
      </div>

      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between mb-0.5">
          <span className={cx('text-sm font-medium truncate', (active || hasUnread) ? 'text-white' : 'text-dark-200')} style={nameColorStyle(other)}>
            {other ? displayName(other) : t('messages.user_fallback')}
          </span>
          <span className={cx('text-[10px] flex-shrink-0 ml-2', hasUnread ? 'text-primary-400 font-medium' : 'text-dark-500')}>
            {timeAgo(conv.last_message_at)}
          </span>
        </div>
        <div className="flex items-center justify-between">
          <p className={cx('text-xs truncate flex-1', hasUnread ? 'text-dark-200 font-medium' : 'text-dark-500')}>
            {conv.last_message || t('messages.no_messages_yet')}
          </p>
          {hasUnread && (
            <span className="ml-2 flex-shrink-0 min-w-[20px] h-5 px-1.5 bg-primary-500/20 border border-primary-500/40 rounded-full flex items-center justify-center">
              <span className="text-[9px] font-bold text-primary-300">{conv.unread_count > 9 ? '9+' : conv.unread_count}</span>
            </span>
          )}
        </div>
        {conv.context_label && (
          <div className="flex items-center gap-1 mt-1">
            <TagIcon size={9} className="text-dark-600" />
            <span className="text-[10px] text-dark-600 truncate">{conv.context_label}</span>
          </div>
        )}
      </div>
    </button>
  )
}

/* ---------------------------------------------------------------- ChatView */
function ChatView({ convId, onBack }) {
  const t = useT()
  const { user } = useAuthStore()
  const { showToast } = useToast()
  const [conv, setConv] = useState(null)
  const [messages, setMessages] = useState([])
  const [newMessage, setNewMessage] = useState('')
  const [loading, setLoading] = useState(true)
  const [sending, setSending] = useState(false)
  const [page, setPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [loadingMore, setLoadingMore] = useState(false)
  const [editingMsg, setEditingMsg] = useState(null)
  const [editContent, setEditContent] = useState('')
  const [deleteTarget, setDeleteTarget] = useState(null)

  const messagesEndRef = useRef(null)
  const messagesContainerRef = useRef(null)
  const inputRef = useRef(null)
  const initialLoad = useRef(true)
  const pollRef = useRef(null)
  const mountedRef = useRef(true)
  const prevConvId = useRef(convId)

  useEffect(() => {
    mountedRef.current = true
    return () => { mountedRef.current = false }
  }, [])

  // Reset state when conversation changes
  useEffect(() => {
    if (prevConvId.current !== convId) {
      prevConvId.current = convId
      setMessages([])
      setPage(1)
      setTotalPages(1)
      setNewMessage('')
      setEditingMsg(null)
      setEditContent('')
      setDeleteTarget(null)
      initialLoad.current = true
    }
  }, [convId])

  const scrollToBottom = useCallback((behavior = 'smooth') => {
    messagesEndRef.current?.scrollIntoView({ behavior })
  }, [])

  const loadConversation = useCallback(async (silent = false) => {
    if (!convId) return
    try {
      if (!silent) setLoading(true)
      const { data } = await api.get(`/api/dm/${convId}`)
      if (!mountedRef.current) return
      setConv(data)
      setMessages(data.messages || [])
      setTotalPages(data.total_pages || 1)
      if (initialLoad.current) {
        initialLoad.current = false
        setTimeout(() => { if (mountedRef.current) scrollToBottom('instant') }, 50)
      }
    } catch {
      if (mountedRef.current) setConv(null)
    } finally {
      if (mountedRef.current) setLoading(false)
    }
  }, [convId, scrollToBottom])

  useEffect(() => {
    if (!convId) return
    loadConversation()
    const startPoll = () => {
      clearInterval(pollRef.current)
      pollRef.current = setInterval(() => loadConversation(true), document.hasFocus() ? 3000 : 15000)
    }
    startPoll()
    const onFocus = () => startPoll()
    const onBlur = () => startPoll()
    window.addEventListener('focus', onFocus)
    window.addEventListener('blur', onBlur)
    return () => {
      clearInterval(pollRef.current)
      window.removeEventListener('focus', onFocus)
      window.removeEventListener('blur', onBlur)
    }
  }, [convId, loadConversation])

  useEffect(() => {
    if (!messagesContainerRef.current || initialLoad.current) return
    const el = messagesContainerRef.current
    const isNearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 150
    if (isNearBottom) scrollToBottom()
  }, [messages.length, scrollToBottom])

  const loadMore = async () => {
    if (loadingMore || page >= totalPages || !convId) return
    setLoadingMore(true)
    const container = messagesContainerRef.current
    const prevHeight = container?.scrollHeight || 0
    try {
      const nextPage = page + 1
      const { data } = await api.get(`/api/dm/${convId}`, { params: { page: nextPage } })
      if (!mountedRef.current) return
      setMessages(prev => [...(data.messages || []), ...prev])
      setPage(nextPage)
      setTotalPages(data.total_pages || 1)
      requestAnimationFrame(() => {
        if (container) container.scrollTop = container.scrollHeight - prevHeight
      })
    } catch {
      // silent
    } finally {
      if (mountedRef.current) setLoadingMore(false)
    }
  }

  const handleSend = async (e) => {
    e.preventDefault()
    if (!newMessage.trim() || sending || !convId) return
    setSending(true)
    try {
      const { data } = await api.post(`/api/dm/${convId}/messages`, { content: newMessage.trim() })
      setMessages(prev => [...prev, data])
      setNewMessage('')
      inputRef.current?.focus()
      setTimeout(() => scrollToBottom(), 50)
    } catch (err) {
      showToast(t('messages.toast_send_failed'), 'error')
    } finally {
      setSending(false)
    }
  }

  const handleEdit = async () => {
    if (!editingMsg || !editContent.trim()) return
    try {
      const { data } = await api.put(`/api/dm/messages/${editingMsg.id}`, { content: editContent.trim() })
      setMessages(prev => prev.map(m => m.id === editingMsg.id ? { ...m, content: data.content, is_edited: true } : m))
      setEditingMsg(null)
      setEditContent('')
      showToast(t('messages.toast_edited'), 'success')
    } catch (err) {
      showToast(err.response?.data?.detail || t('messages.toast_edit_failed'), 'error')
    }
  }

  const handleDelete = async () => {
    if (!deleteTarget) return
    try {
      await api.delete(`/api/dm/messages/${deleteTarget.id}`)
      setMessages(prev => prev.map(m => m.id === deleteTarget.id ? { ...m, is_deleted: true, content: '' } : m))
      setDeleteTarget(null)
      showToast(t('messages.toast_deleted'), 'success')
    } catch (err) {
      showToast(err.response?.data?.detail || t('messages.toast_delete_failed'), 'error')
    }
  }

  const startEdit = (msg) => {
    setEditingMsg(msg)
    setEditContent(msg.content)
  }

  const groupedMessages = messages.reduce((groups, msg) => {
    const date = formatDate(msg.created_at, { relative: true })
    if (!groups[date]) groups[date] = []
    groups[date].push(msg)
    return groups
  }, {})

  // --- Loading state ---
  if (loading) {
    return (
      <div className="flex-1 flex flex-col h-full">
        <LoadingState label={t('messages.loading_conversation')} className="flex-1 flex flex-col items-center justify-center" />
      </div>
    )
  }

  // --- Not found ---
  if (!conv) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center h-full p-6">
        <AlertCircle size={40} className="mx-auto text-red-400 mb-4" />
        <div className="text-dark-400 mb-4">{t('messages.conversation_not_found')}</div>
        {onBack && (
          <Button variant="primary" icon={ArrowLeft} onClick={onBack}>
            {t('messages.back_to_messages')}
          </Button>
        )}
      </div>
    )
  }

  const other = conv.other_user

  return (
    <div className="flex-1 flex flex-col h-full min-h-0">
      {/* Header */}
      <div className="flex items-center gap-3 pb-3 border-b border-primary-500/15 mb-2 flex-shrink-0">
        {onBack && (
          <button onClick={onBack} className="md:hidden p-1 -ml-1 hover:bg-dark-800/70 rounded-lg transition-colors" title={t('common.back')}>
            <ArrowLeft size={20} className="text-dark-400" />
          </button>
        )}
        <div className="flex items-center gap-3 flex-1 min-w-0">
          <div className="relative flex-shrink-0">
            <div className="w-10 h-10 rounded-xl bg-primary-500/15 border border-primary-500/25 overflow-hidden">
              {other?.avatar_url ? (
                <img
                  src={other.avatar_url.startsWith('http') ? other.avatar_url : `${import.meta.env.VITE_API_URL || ''}${other.avatar_url}`}
                  alt={displayName(other, false)}
                  className="w-full h-full object-cover"
                />
              ) : (
                <div className="w-full h-full flex items-center justify-center">
                  <User size={18} className="text-primary-400" />
                </div>
              )}
            </div>
            {other?.is_online && (
              <div className="absolute -bottom-0.5 -right-0.5 w-3.5 h-3.5 bg-green-500 rounded-full ring-2 ring-dark-900" />
            )}
          </div>
          <div className="min-w-0">
            <Link to={`/profile/${other?.id}`} className={cx('font-display text-xl font-bold leading-tight truncate block hover:opacity-80 transition-opacity', nameColorStyle(other) ? '' : 'gradient-text')} style={nameColorStyle(other)}>
              {other ? displayName(other) : t('messages.user_fallback')}
            </Link>
            <div className="flex items-center gap-2 text-xs text-dark-400 mt-0.5">
              {other?.is_online ? (
                <span className="text-green-400 font-medium">{t('messages.online')}</span>
              ) : (
                <span>{t('messages.offline')}</span>
              )}
              {conv.context_label && (
                <>
                  <span className="text-dark-600">·</span>
                  <span className="flex items-center gap-1 truncate">
                    <TagIcon size={9} /> {conv.context_label}
                  </span>
                </>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Messages area */}
      <div ref={messagesContainerRef} className="flex-1 overflow-y-auto pr-1 space-y-1 min-h-0">
        {page < totalPages && (
          <div className="flex justify-center py-2">
            <Button variant="secondary" size="sm" onClick={loadMore} disabled={loadingMore} className="!rounded-full">
              {loadingMore ? t('messages.loading') : t('messages.load_older')}
            </Button>
          </div>
        )}

        {Object.entries(groupedMessages).map(([date, msgs]) => (
          <div key={date}>
            <div className="flex items-center justify-center my-3">
              <div className="h-px flex-1 bg-primary-500/15" />
              <span className="px-3 py-0.5 text-[10px] text-dark-500 font-mono uppercase tracking-wider">{date}</span>
              <div className="h-px flex-1 bg-primary-500/15" />
            </div>
            <div className="space-y-1.5">
              {msgs.map((msg) => (
                <MessageBubble key={msg.id} msg={msg} isOwn={msg.sender_id === user?.id} onEdit={startEdit} onDelete={setDeleteTarget} />
              ))}
            </div>
          </div>
        ))}

        {messages.length === 0 && (
          <EmptyState icon={MessageCircle} className="py-16">
            {t('messages.empty_conversation')}
          </EmptyState>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Edit bar */}
        {editingMsg && (
          <div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden flex-shrink-0">
            <div className="flex items-center gap-2 px-3 py-2 bg-primary-500/10 border-t border-primary-500/20 rounded-t-lg">
              <Pencil size={14} className="text-primary-400 flex-shrink-0" />
              <div className="flex-1 min-w-0">
                <span className="text-xs text-primary-400 font-medium">{t('messages.editing_message')}</span>
                <p className="text-[11px] text-dark-400 truncate">{editingMsg.content}</p>
              </div>
              <button onClick={() => { setEditingMsg(null); setEditContent('') }} className="p-1 hover:bg-dark-700/50 rounded transition-colors">
                <X size={14} className="text-dark-400" />
              </button>
            </div>
          </div>
        )}

      {/* Input */}
      <form onSubmit={editingMsg ? (e) => { e.preventDefault(); handleEdit() } : handleSend} className="flex items-center gap-2 pt-2 flex-shrink-0">
        <input
          type="text"
          ref={inputRef}
          value={editingMsg ? editContent : newMessage}
          onChange={e => editingMsg ? setEditContent(e.target.value) : setNewMessage(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault()
              if (editingMsg) handleEdit()
              else if (newMessage.trim()) handleSend(e)
            }
            if (e.key === 'Escape' && editingMsg) { setEditingMsg(null); setEditContent('') }
          }}
          placeholder={editingMsg ? t('messages.edit_placeholder') : t('messages.type_placeholder')}
          autoComplete="off"
          autoCorrect="off"
          className="flex-1 bg-dark-950/60 border border-primary-500/15 rounded-xl px-4 py-3 text-white text-sm placeholder:text-dark-500 focus:outline-none focus:border-primary-500/50 transition-colors h-[44px]"
          style={{ fontVariantEmoji: 'text' }}
          disabled={sending}
        />
        <Button
          type="submit"
          variant="primary"
          disabled={sending || !(editingMsg ? editContent.trim() : newMessage.trim())}
          className="!p-3 flex-shrink-0"
          style={{ minHeight: '44px', minWidth: '44px' }}
        >
          {editingMsg ? <Check size={20} /> : <Send size={20} />}
        </Button>
      </form>

      {/* Delete confirmation modal */}
        {deleteTarget && (
          <div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4" onClick={() => setDeleteTarget(null)}>
            <div initial={{ scale: 0.95, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.95, opacity: 0 }} onClick={e => e.stopPropagation()} className="relative bg-dark-900/95 border border-primary-500/20 rounded-xl p-5 max-w-sm w-full backdrop-blur-xl">
              <span className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-primary-500/50 to-transparent" />
              <h3 className="font-semibold text-base mb-2">{t('messages.delete_confirm_title')}</h3>
              <p className="text-dark-400 text-sm mb-4">{t('messages.delete_confirm_body')}</p>
              <div className="flex justify-end gap-2">
                <Button variant="ghost" size="sm" onClick={() => setDeleteTarget(null)}>{t('common.cancel')}</Button>
                <Button variant="danger" size="sm" onClick={handleDelete}>{t('common.delete')}</Button>
              </div>
            </div>
          </div>
        )}
    </div>
  )
}

/* ------------------------------------------------------ Empty chat placeholder */
function EmptyChat() {
  const t = useT()
  return (
    <div className="flex-1 flex flex-col items-center justify-center h-full p-6">
      <div className="w-16 h-16 rounded-2xl bg-primary-500/10 border border-primary-500/20 flex items-center justify-center mb-4">
        <MessageCircle size={28} className="text-primary-400/60" />
      </div>
      <p className="font-display text-lg font-semibold gradient-text mb-1">{t('messages.select_conversation')}</p>
      <p className="text-sm text-dark-400 text-center max-w-xs">
        {t('messages.select_conversation_hint')}
      </p>
    </div>
  )
}

/* ================================================================= Messages */
export default function Messages() {
  const t = useT()
  const { user } = useAuthStore()
  const { showToast } = useToast()
  const { id: convIdParam } = useParams()
  const navigate = useNavigate()
  const [conversations, setConversations] = useState([])
  const [loading, setLoading] = useState(true)
  const [selectedConvId, setSelectedConvId] = useState(null)
  const [mobileView, setMobileView] = useState('list') // 'list' | 'chat'
  const [searchQuery, setSearchQuery] = useState('')
  const [showNewDM, setShowNewDM] = useState(false)
  const [newDMQuery, setNewDMQuery] = useState('')
  const [userResults, setUserResults] = useState([])
  const [searchingUsers, setSearchingUsers] = useState(false)
  const newDMDebounceRef = useRef(null)
  const [messageResults, setMessageResults] = useState(null)
  const msgSearchDebounceRef = useRef(null)

  const loadConversations = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await api.get('/api/dm')
      setConversations(data)
    } catch {
      setConversations([])
    } finally {
      setLoading(false)
    }
    try {
      const dmRes = await api.get('/api/dm/unread-count')
      const total = dmRes.data.count || 0
      window.dispatchEvent(new CustomEvent('messages-unread-updated', { detail: { count: total } }))
    } catch {}
  }, [])

  useEffect(() => {
    loadConversations()
  }, [loadConversations])

  // Sync selection with the /messages/:id URL (deep-links from profiles, posts, chat)
  useEffect(() => {
    if (convIdParam) {
      setSelectedConvId(Number(convIdParam))
      setMobileView('chat')
    } else {
      setMobileView('list')
    }
  }, [convIdParam])

  // Refresh list on focus
  useEffect(() => {
    const onFocus = () => loadConversations()
    window.addEventListener('focus', onFocus)
    return () => window.removeEventListener('focus', onFocus)
  }, [loadConversations])

  const handleNewDMSearch = (q) => {
    setNewDMQuery(q)
    clearTimeout(newDMDebounceRef.current)
    if (!q.trim() || q.trim().length < 2) {
      setUserResults([])
      return
    }
    newDMDebounceRef.current = setTimeout(async () => {
      setSearchingUsers(true)
      try {
        const { data } = await api.get('/api/users', { params: { q: q.trim(), per_page: 8 } })
        setUserResults(data.filter(u => u.id !== user?.id))
      } catch {
        setUserResults([])
      } finally {
        setSearchingUsers(false)
      }
    }, 250)
  }

  const startConversation = async (targetUserId) => {
    try {
      const { data } = await api.post('/api/dm/start', {
        user_id: targetUserId,
        message: 'Hey!'
      })
      await loadConversations()
      setShowNewDM(false)
      setNewDMQuery('')
      setUserResults([])
      navigate(`/messages/${data.conversation_id}`)
    } catch (err) {
      showToast(err.response?.data?.detail || t('messages.toast_start_failed'), 'error')
    }
  }

  // Full-text search across the user's messages (server-side), debounced.
  // Runs alongside the local conversation-name filter.
  const handleSearchChange = (q) => {
    setSearchQuery(q)
    clearTimeout(msgSearchDebounceRef.current)
    if (!q.trim() || q.trim().length < 2) {
      setMessageResults(null)
      return
    }
    msgSearchDebounceRef.current = setTimeout(async () => {
      try {
        const { data } = await api.get('/api/dm/search/messages', { params: { q: q.trim() } })
        setMessageResults(data)
      } catch {
        setMessageResults([])
      }
    }, 300)
  }

  const selectConversation = (convId) => {
    navigate(`/messages/${convId}`)
  }

  const handleMobileBack = () => {
    navigate('/messages')
  }

  // Filter conversations by search
  const filtered = searchQuery.trim()
    ? conversations.filter(c => {
        const o = c.other_user
        const name = (o ? displayName(o, false) : '').toLowerCase()
        const last = (c.last_message || '').toLowerCase()
        const q = searchQuery.toLowerCase()
        return name.includes(q) || last.includes(q)
      })
    : conversations

  const totalUnread = conversations.reduce((sum, c) => sum + (c.unread_count || 0), 0)

  const sidebarContent = (
    <div className="flex flex-col h-full">
      {/* Sidebar header */}
      <div className="flex items-center justify-between px-1 pb-3 flex-shrink-0">
        <div className="flex items-center gap-2 min-w-0">
          <div className="w-8 h-8 rounded-lg bg-primary-500/15 border border-primary-500/25 flex items-center justify-center flex-shrink-0">
            <MessageCircle size={16} className="text-primary-400" />
          </div>
          <div className="min-w-0">
            <h1 className="font-display text-lg font-bold gradient-text leading-tight truncate">
              {t('messages.title')}
              {totalUnread > 0 && (
                <span className="ml-2 text-xs bg-primary-500 text-dark-950 px-1.5 py-0.5 rounded-full font-medium align-middle">
                  {totalUnread}
                </span>
              )}
            </h1>
            <p className="text-xs text-dark-400">{t('messages.conversations_count', { n: conversations.length })}</p>
          </div>
        </div>
        <div className="flex items-center gap-1 flex-shrink-0">
          <Button variant="ghost" size="xs" icon={PenSquare} onClick={() => setShowNewDM(!showNewDM)} title={t('messages.new_message')} />
          <Button variant="ghost" size="xs" icon={RefreshCw} onClick={loadConversations} />
        </div>
      </div>

      {/* New DM panel */}
        {showNewDM && (
          <div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden flex-shrink-0">
            <div className="bg-dark-800/70 border border-primary-500/20 rounded-xl p-3 mb-3">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-xs font-semibold text-dark-200">{t('messages.new_conversation')}</h3>
                <button onClick={() => { setShowNewDM(false); setNewDMQuery(''); setUserResults([]) }} className="text-dark-500 hover:text-white"><X size={14} /></button>
              </div>
              <div className="relative">
                <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-dark-500" />
                <input
                  value={newDMQuery}
                  onChange={e => handleNewDMSearch(e.target.value)}
                  placeholder={t('messages.search_users')}
                  className="w-full bg-dark-950/60 border border-primary-500/15 rounded-lg pl-9 pr-3 py-2 text-sm placeholder:text-dark-500 focus:outline-none focus:border-primary-500/50 transition-colors"
                  autoFocus
                />
              </div>
              {searchingUsers && <div className="text-xs text-dark-500 mt-2 text-center">{t('messages.searching')}</div>}
              {userResults.length > 0 && (
                <div className="mt-2 space-y-1 max-h-48 overflow-y-auto">
                  {userResults.map(u => (
                    <button
                      key={u.id}
                      onClick={() => startConversation(u.id)}
                      className="w-full flex items-center gap-3 p-2 rounded-lg hover:bg-dark-800/70 transition-colors text-left"
                    >
                      <div className="w-8 h-8 rounded-full bg-dark-700 overflow-hidden flex-shrink-0">
                        {u.avatar_url ? (
                          <img src={u.avatar_url} alt="" className="w-full h-full object-cover" />
                        ) : (
                          <div className="w-full h-full flex items-center justify-center text-xs font-bold text-dark-400">
                            {displayName(u, false)[0].toUpperCase()}
                          </div>
                        )}
                      </div>
                      <div>
                        <div className="text-sm font-medium">{displayName(u)}</div>
                        <div className="text-[10px] text-dark-500">{t('messages.posts_count', { n: u.post_count || 0 })}</div>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

      {/* Search */}
      <div className="relative mb-3 flex-shrink-0">
        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-dark-500" />
        <input
          value={searchQuery}
          onChange={e => handleSearchChange(e.target.value)}
          placeholder={t('messages.search_placeholder')}
          className="w-full bg-dark-950/60 border border-primary-500/15 rounded-xl pl-9 pr-8 py-2.5 text-sm placeholder:text-dark-500 focus:outline-none focus:border-primary-500/50 transition-colors"
        />
        {searchQuery && (
          <button onClick={() => handleSearchChange('')} className="absolute right-3 top-1/2 -translate-y-1/2 text-dark-500 hover:text-dark-300">
            <X size={14} />
          </button>
        )}
      </div>

      {/* Message search results */}
      {messageResults !== null && (
        <div className="mb-3 flex-shrink-0">
          <p className="text-[10px] uppercase tracking-widest text-dark-500 font-mono mb-1.5">
            {t('messages.search_results', { n: messageResults.length })}
          </p>
          {messageResults.length === 0 ? (
            <p className="text-xs text-dark-500 px-1">{t('messages.no_messages_match')}</p>
          ) : (
            <div className="space-y-1 max-h-48 overflow-y-auto">
              {messageResults.map(m => (
                <button
                  key={m.id}
                  onClick={() => { handleSearchChange(''); selectConversation(m.conversation_id) }}
                  className="w-full text-left p-2 rounded-lg hover:bg-dark-800/70 transition-colors"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-[11px] font-semibold text-dark-300 truncate">
                      {m.sender ? displayName(m.sender) : `@${m.sender_username || '?'}`}
                    </span>
                    <span className="text-[9px] text-dark-600 flex-shrink-0">{timeAgo(m.created_at)}</span>
                  </div>
                  <p className="text-xs text-dark-400 truncate">{m.content}</p>
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Conversation list */}
      <div className="flex-1 overflow-y-auto min-h-0 space-y-1">
        {loading ? (
          <LoadingState label={t('messages.loading_conversations')} />
        ) : filtered.length === 0 ? (
          <EmptyState icon={MessageCircle}>
            {searchQuery ? t('messages.no_conversations_match') : t('messages.no_conversations')}
          </EmptyState>
        ) : (
          filtered.map((conv, i) => (
            <div
              key={conv.id}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.02 }}
            >
              <ConversationRow
                conv={conv}
                active={conv.id === selectedConvId}
                onClick={() => selectConversation(conv.id)}
              />
            </div>
          ))
        )}
      </div>
    </div>
  )

  return (
    <div className="h-[calc(100vh-130px)] flex flex-col">
      {/* ============== DESKTOP (md+) ============== */}
      <div className="hidden md:flex flex-1 overflow-hidden gap-3">
        {/* Sidebar */}
        <div className="w-80 flex-shrink-0 border-r border-primary-500/10 pr-3">
          {sidebarContent}
        </div>

        {/* Chat */}
        <div className="flex-1 flex flex-col min-w-0">
          {selectedConvId ? (
            <ChatView convId={selectedConvId} onBack={null} />
          ) : (
            <EmptyChat />
          )}
        </div>
      </div>

      {/* ============== MOBILE (<md) ============== */}
      <div className="md:hidden flex-1 flex flex-col overflow-hidden">
        {mobileView === 'list' ? (
          sidebarContent
        ) : selectedConvId ? (
          <ChatView convId={selectedConvId} onBack={handleMobileBack} />
        ) : (
          <EmptyChat />
        )}
      </div>
    </div>
  )
}
