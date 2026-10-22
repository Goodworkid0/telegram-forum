import { useState, useEffect, useRef } from 'react'
import { Link, useParams, useNavigate, useLocation } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { Pin, Megaphone, Lock, Unlock, Eye, MessageSquare, Heart, Trash2, Reply as ReplyIcon, ArrowUp } from 'lucide-react'
import { Card, Button, Tag, tabClass } from '../components/ui'
import api from '../lib/api'
import { useAuthStore } from '../store/authStore'
import { useToast } from '../components/Toast'
import MarkdownToolbar from '../components/MarkdownToolbar'
import Spinner from '../components/Spinner'
import ForumBreadcrumb from '../components/ForumBreadcrumb'
import { displayName, parseDate } from '../lib/utils'
import MarkdownContent from './forum/MarkdownContent'
import MentionTextarea from './forum/MentionTextarea'
import PostItem from './forum/PostItem'
import UserListModal from '../components/UserListModal'
import Pagination from './forum/Pagination'
import PollCard from './forum/PollCard'
import { useT, getDateLocale } from '../lib/i18n'

export default function Thread() {
  const t = useT()
  const { id } = useParams()
  const navigate = useNavigate()
  const location = useLocation()
  const { user, canPost, isModerator, isVerified } = useAuthStore()
  const { showToast } = useToast()
  
  const [thread, setThread] = useState(null)
  const [threadId, setThreadId] = useState(null)  // numeric ID for API calls
  const [error, setError] = useState(null)
  const [posts, setPosts] = useState([])
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [replyContent, setReplyContent] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [replyTo, setReplyTo] = useState(null)
  const [previewMode, setPreviewMode] = useState(false)
  const [editingPost, setEditingPost] = useState(null)
  const [editContent, setEditContent] = useState('')
  const [editSubmitting, setEditSubmitting] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [threadDeleteOpen, setThreadDeleteOpen] = useState(false)
  const [repTarget, setRepTarget] = useState(null)
  const [repPositive, setRepPositive] = useState(true)
  const [repComment, setRepComment] = useState('')
  const [repSubmitting, setRepSubmitting] = useState(false)
  const [likesView, setLikesView] = useState(null) // null | { scope: 'threads'|'posts', id }
  const replyRef = useRef(null)
  const editRef = useRef(null)
  const composerRef = useRef(null)
  const [showReplyFab, setShowReplyFab] = useState(false)
  const mountedRef = useRef(true)
  const composerReadyRef = useRef(false)

  useEffect(() => {
    mountedRef.current = true
    return () => { mountedRef.current = false }
  }, [])

  // Track whether the composer has appeared in the DOM at least once
  useEffect(() => {
    if (!loading && thread) composerReadyRef.current = true
  }, [loading, thread])

  // Show the mobile quick-reply FAB only when the composer is scrolled out of view.
  // Observe the composer only after it first appears, and disconnect only on unmount.
  useEffect(() => {
    const el = composerRef.current
    if (!el || !composerReadyRef.current) {
      setShowReplyFab(false)
      return
    }
    const observer = new IntersectionObserver(
      ([entry]) => setShowReplyFab(!entry.isIntersecting),
      { rootMargin: '0px 0px -120px 0px' }
    )
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  const scrollToComposer = () => {
    composerRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    setTimeout(() => replyRef.current?.focus(), 350)
  }

  // Load draft from localStorage
  useEffect(() => {
    const draft = localStorage.getItem(`reply_draft_${id}`)
    if (draft) setReplyContent(draft)
  }, [id])
  
  // Save draft
  useEffect(() => {
    if (replyContent) {
      localStorage.setItem(`reply_draft_${id}`, replyContent)
    } else {
      localStorage.removeItem(`reply_draft_${id}`)
    }
  }, [replyContent, id])

  useEffect(() => { loadThread() }, [id])
  useEffect(() => { if (threadId) loadPosts() }, [threadId, page])
  
  // Scroll to post anchor on load
  useEffect(() => {
    if (!loading && posts.length > 0) {
      const hash = location.hash
      if (hash?.startsWith('#post-')) {
        const el = document.getElementById(hash.slice(1))
        if (el) {
          setTimeout(() => el.scrollIntoView({ behavior: 'smooth', block: 'center' }), 200)
          el.classList.add('ring-2', 'ring-primary-500/40')
          setTimeout(() => el.classList.remove('ring-2', 'ring-primary-500/40'), 3000)
        }
      }
    }
  }, [loading, posts, location.hash])

  const loadThread = async () => {
    try {
      let res
      if (/^\d+$/.test(id)) {
        res = await api.get(`/api/forum/threads/${id}`)
      } else {
        res = await api.get(`/api/forum/threads/by-slug/${id}`)
      }
      if (!mountedRef.current) return
      setThread(res.data)
      setThreadId(res.data.id)
      setError(null)
    } catch (err) {
      if (!mountedRef.current) return
      if (import.meta.env.DEV) console.error('Failed to load thread:', err)
      if (err.response?.status === 404) { navigate('/'); return }
      setError('forum.load_thread_failed')
      setLoading(false)
    }
  }

  const loadPosts = async () => {
    if (!threadId) return
    try {
      setLoading(true)
      const res = await api.get(`/api/forum/threads/${threadId}/posts`, { params: { page, per_page: 20 } })
      if (!mountedRef.current) return
      setPosts(res.data.posts || [])
      setTotalPages(res.data.total_pages || 1)
    } catch (err) {
      if (import.meta.env.DEV) console.error('Failed to load posts:', err)
    } finally {
      if (mountedRef.current) setLoading(false)
    }
  }

  const handlePageChange = (newPage) => {
    setPage(newPage)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  // ---- Reply ----
  const handleReply = async (e) => {
    e.preventDefault()
    if (!replyContent.trim() || submitting || !threadId) return
    try {
      setSubmitting(true)
      await api.post(`/api/forum/threads/${threadId}/posts`, {
        content: replyContent,
        parent_id: replyTo?.id || null
      })
      setReplyContent('')
      setReplyTo(null)
      setPreviewMode(false)
      localStorage.removeItem(`reply_draft_${id}`)
      const res = await api.get(`/api/forum/threads/${threadId}/posts`, { params: { page: 1, per_page: 20 } })
      const lastPage = res.data.total_pages || 1
      setPage(lastPage)
      await loadPosts()
      showToast(t('forum.reply_posted'), 'success')
    } catch (err) {
      showToast(err.response?.data?.detail || t('forum.reply_failed'), 'error')
    } finally {
      setSubmitting(false)
    }
  }

  // ---- Like ----
  const handleLikeThread = async () => {
    if (!user) return
    const isLiked = thread.user_liked || thread.is_liked
    if (!isVerified() && !isLiked) {
      showToast(t('forum.verify_to_like'), 'warning')
      return
    }
    try {
      const res = isLiked
        ? await api.delete(`/api/forum/threads/${threadId}/like`)
        : await api.post(`/api/forum/threads/${threadId}/like`)
      setThread(prev => ({ ...prev, like_count: res.data.like_count, user_liked: res.data.liked, is_liked: res.data.liked }))
    } catch (err) {
      if (err.response?.status !== 400) showToast(t('forum.like_failed'), 'error')
    }
  }

  const handleLikePost = async (postId) => {
    if (!user) return
    const post = posts.find(p => p.id === postId)
    const isLiked = post?.user_liked || post?.is_liked
    if (!isVerified() && !isLiked) {
      showToast(t('forum.verify_to_like'), 'warning')
      return
    }
    try {
      const res = isLiked
        ? await api.delete(`/api/forum/posts/${postId}/like`)
        : await api.post(`/api/forum/posts/${postId}/like`)
      setPosts(prev => prev.map(p =>
        p.id === postId ? { ...p, like_count: res.data.like_count, user_liked: res.data.liked, is_liked: res.data.liked } : p
      ))
    } catch (err) {
      if (err.response?.status !== 400) showToast(t('forum.like_failed'), 'error')
    }
  }

  // ---- Quote ----
  const setQuoteReply = (post) => {
    const quotedLines = post.content.split('\n').map(l => `> ${l}`).join('\n')
    const authorName = post.author ? displayName(post.author, false) : 'user'
    setReplyTo(post)
    setReplyContent(`**@${authorName}** wrote:\n${quotedLines}\n\n`)
    replyRef.current?.focus()
  }

  // ---- Watch ----
  const handleToggleWatch = async () => {
    if (!user || !thread) return
    try {
      if (thread.is_watched) {
        await api.delete(`/api/forum/threads/${threadId}/watch`)
        setThread(prev => ({ ...prev, is_watched: false }))
        showToast(t('forum.stopped_watching'), 'success')
      } else {
        await api.post(`/api/forum/threads/${threadId}/watch`)
        setThread(prev => ({ ...prev, is_watched: true }))
        showToast(t('forum.watching_thread'), 'success')
      }
    } catch (err) {
      showToast(err.response?.data?.detail || t('forum.action_failed'), 'error')
    }
  }

  // ---- Mod Controls ----
  const handleToggleLock = async () => {
    if (!thread) return
    try {
      const newStatus = isLocked ? 'open' : 'locked'
      await api.patch(`/api/forum/threads/${threadId}/mod`, { status: newStatus })
      setThread(prev => ({ ...prev, status: newStatus, is_locked: newStatus === 'locked' }))
      showToast(newStatus === 'locked' ? t('forum.thread_locked_toast') : t('forum.thread_unlocked_toast'), 'success')
    } catch (err) {
      showToast(err.response?.data?.detail || t('forum.action_failed'), 'error')
    }
  }

  const handleTogglePin = async () => {
    if (!thread) return
    try {
      await api.patch(`/api/forum/threads/${threadId}/mod`, { is_pinned: !thread.is_pinned })
      setThread(prev => ({ ...prev, is_pinned: !prev.is_pinned }))
      showToast(thread.is_pinned ? t('forum.thread_unpinned_toast') : t('forum.thread_pinned_toast'), 'success')
    } catch (err) {
      showToast(err.response?.data?.detail || t('forum.action_failed'), 'error')
    }
  }

  const handleAuthorLock = async () => {
    if (!thread) return
    try {
      await api.post(`/api/forum/threads/${threadId}/lock`, null, { params: { locked: !isLocked } })
      showToast(isLocked ? t('forum.thread_unlocked_toast') : t('forum.thread_locked_toast'), 'success')
      loadThread()
    } catch (err) {
      showToast(err.response?.data?.detail || t('forum.action_failed'), 'error')
    }
  }

  const handleBump = async () => {
    if (!thread) return
    try {
      await api.post(`/api/forum/threads/${threadId}/bump`)
      showToast(t('forum.thread_bumped'), 'success')
      loadThread()
    } catch (err) {
      showToast(err.response?.data?.detail || t('forum.bump_failed'), 'error')
    }
  }

  const handleDeleteThread = async () => {
    if (!thread) return
    setThreadDeleteOpen(true)
  }

  const doDeleteThread = async () => {
    setThreadDeleteOpen(false)
    try {
      await api.patch(`/api/forum/threads/${threadId}/mod`, { status: 'deleted' })
      showToast(t('forum.thread_deleted'), 'success')
      navigate(`/board/${thread.board?.slug || ''}`)
    } catch (err) {
      showToast(err.response?.data?.detail || t('forum.action_failed'), 'error')
    }
  }

  // ---- Edit Post ----
  const startEdit = (post) => {
    setEditingPost(post)
    setEditContent(post.content)
  }
  
  const cancelEdit = () => {
    setEditingPost(null)
    setEditContent('')
  }
  
  const handleEditSubmit = async () => {
    if (!editContent.trim() || editSubmitting) return
    try {
      setEditSubmitting(true)
      if (editingPost._isOP) {
        // The opening post IS the thread, not a Post row — edit via the thread
        // endpoint and update thread state (the OP renders from `thread`).
        await api.put(`/api/forum/threads/${threadId}`, { content: editContent })
        setThread(prev => ({ ...prev, content: editContent, is_edited: true, edited_at: new Date().toISOString(), edit_count: (prev.edit_count || 0) + 1 }))
      } else {
        await api.put(`/api/forum/posts/${editingPost.id}`, { content: editContent })
        setPosts(prev => prev.map(p =>
          p.id === editingPost.id ? { ...p, content: editContent, is_edited: true, edited_at: new Date().toISOString(), edit_count: (p.edit_count || 0) + 1 } : p
        ))
      }
      cancelEdit()
      showToast(editingPost._isOP ? t('forum.thread_updated') : t('forum.post_updated'), 'success')
    } catch (err) {
      showToast(err.response?.data?.detail || t('forum.edit_failed'), 'error')
    } finally {
      setEditSubmitting(false)
    }
  }

  // ---- Delete Post ----
  const handleDelete = async () => {
    if (!deleteTarget) return
    try {
      await api.delete(`/api/forum/posts/${deleteTarget.id}`)
      setPosts(prev => prev.map(p =>
        p.id === deleteTarget.id ? { ...p, is_deleted: true, content: '' } : p
      ))
      setDeleteTarget(null)
      showToast(t('forum.post_deleted'), 'success')
    } catch (err) {
      showToast(err.response?.data?.detail || t('forum.delete_post_failed'), 'error')
    }
  }

  const handleRepClick = (post) => {
    if (!isVerified()) {
      showToast(t('forum.verify_to_rep'), 'warning')
      return
    }
    setRepTarget(post)
  }

  const handleGiveRep = async () => {
    if (!repTarget || !repComment.trim()) return
    if (!isVerified()) {
      showToast(t('forum.verify_to_rep'), 'warning')
      setRepTarget(null)
      setRepComment('')
      return
    }
    try {
      setRepSubmitting(true)
      await api.post(`/api/reputation/users/${repTarget.author.id}`, {
        is_positive: repPositive,
        comment: repComment.trim(),
        post_id: repTarget.id,
        thread_id: parseInt(id)
      })
      showToast(repPositive ? t('forum.rep_given_pos') : t('forum.rep_given_neg'), 'success')
      setRepTarget(null)
      setRepComment('')
    } catch (err) {
      showToast(err.response?.data?.detail || t('forum.rep_failed'), 'error')
    } finally {
      setRepSubmitting(false)
    }
  }

  // ---- Loading ----
  if (error && !thread) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-20 text-center">
        <div className="text-dark-500 text-lg mb-4">{t(error)}</div>
        <Button variant="primary" onClick={() => { setError(null); setLoading(true); loadThread() }}>{t('common.retry')}</Button>
      </div>
    )
  }

  if (loading && !thread) {
    return (
      <div className="max-w-4xl mx-auto space-y-3">
        <div className="h-4 w-48 bg-dark-700/50 rounded animate-pulse" />
        <div className="bg-dark-800/50 rounded-xl p-5 border border-dark-700/50 space-y-3">
          <div className="h-6 w-3/4 bg-dark-700/50 rounded animate-pulse" />
          <div className="h-3 w-32 bg-dark-700/50 rounded animate-pulse" />
        </div>
        <div className="bg-dark-900/80 rounded-xl border border-primary-500/15 overflow-hidden">
          <div className="h-8 bg-dark-750/50 border-b border-dark-700/30" />
          <div className="flex p-4 gap-4">
            <div className="w-36 flex flex-col items-center gap-2">
              <div className="w-20 h-20 rounded-full bg-dark-700/50 animate-pulse" />
              <div className="h-3 w-20 bg-dark-700/50 rounded animate-pulse" />
              <div className="h-4 w-16 bg-dark-700/50 rounded animate-pulse" />
            </div>
            <div className="flex-1 space-y-2">
              <div className="h-3 w-full bg-dark-700/50 rounded animate-pulse" />
              <div className="h-3 w-5/6 bg-dark-700/50 rounded animate-pulse" />
              <div className="h-3 w-3/4 bg-dark-700/50 rounded animate-pulse" />
            </div>
          </div>
        </div>
      </div>
    )
  }

  if (!thread) return null

  const isLocked = thread.status === 'locked' || thread.is_locked
  const isOwner = !!(user && thread.author && user.id === thread.author.id)
  const canManageOwn = isOwner && isVerified()
  // Per-user cooldown: the server tells us when THIS member may next bump.
  const bumpReadyAt = thread.bump_available_at ? parseDate(thread.bump_available_at) : null
  const bumpOnCooldown = bumpReadyAt ? bumpReadyAt > new Date() : false
  const canPostHere = () => canPost(thread?.board)
  const userRole = user?.role?.toUpperCase()
  const minRoleToPost = thread?.board?.min_role_to_post?.toUpperCase()

  return (
    <div className="space-y-3 max-w-4xl mx-auto">
      {/* Breadcrumb */}
      <ForumBreadcrumb items={[
        thread.section_name && { label: thread.section_name, to: null },
        thread.board?.name && { label: thread.board.name, to: `/board/${thread.board.slug}` },
        { label: thread.title }
      ].filter(Boolean)} />

      {/* Thread Title Bar */}
      <Card
        as={motion.div}
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        className="!p-3 sm:!p-4"
      >
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              {thread.is_pinned && <Tag tone="amber" icon={Pin}>{t('forum.pinned')}</Tag>}
              {thread.is_announcement && <Tag tone="cyan" icon={Megaphone}>{t('forum.announcement')}</Tag>}
              {isLocked && <Tag tone="red" icon={Lock}>{t('forum.locked')}</Tag>}
              <h1
                className={`font-display text-base sm:text-xl font-bold leading-snug ${thread.title_color ? '' : 'text-white'}`}
                style={thread.title_color ? { color: thread.title_color, textShadow: thread.title_glow ? `0 0 8px ${thread.title_color}` : undefined } : undefined}
              >
                {thread.title}
              </h1>
              {thread.tags?.length > 0 && (
                <div className="flex items-center gap-1.5 flex-wrap">
                  {thread.tags.map(tag => (
                    <Tag key={tag}>{tag}</Tag>
                  ))}
                </div>
              )}
            </div>
            <div className="flex items-center gap-3 sm:gap-4 mt-1.5 font-mono text-[10px] sm:text-xs text-dark-400">
              <span className="flex items-center gap-1">
                <Eye size={13} />
                {thread.view_count || 0}
              </span>
              <span className="flex items-center gap-1">
                <MessageSquare size={13} />
                {thread.reply_count || 0}
              </span>
              {(thread.like_count || 0) > 0 ? (
                <button
                  onClick={() => setLikesView({ scope: 'threads', id: thread.id })}
                  className="flex items-center gap-1 hover:text-primary-300 transition-colors"
                >
                  <Heart size={13} fill="currentColor" />
                  {thread.like_count}
                </button>
              ) : (
                <span className="flex items-center gap-1">
                  <Heart size={13} fill="none" />
                  0
                </span>
              )}
            </div>
          </div>

          {/* Watch Button */}
          {user && (
            <Button
              variant={thread.is_watched ? 'secondary' : 'ghost'}
              size="xs"
              onClick={handleToggleWatch}
              className="flex-shrink-0 !px-2 !py-1"
            >
              <svg className="w-3.5 h-3.5" fill={thread.is_watched ? 'currentColor' : 'none'} viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
              </svg>
              {thread.is_watched ? '' : ''}
            </Button>
          )}

          {/* Mod Controls */}
          {isModerator() && (
            <div className="flex items-center gap-1 flex-shrink-0">
              <Button
                variant={thread.is_pinned ? 'warn' : 'ghost'}
                size="xs"
                onClick={handleTogglePin}
                title={thread.is_pinned ? t('forum.unpin') : t('forum.pin')}
                className="!px-1.5 !py-1"
              >
                <Pin size={13} fill={thread.is_pinned ? 'currentColor' : 'none'} />
              </Button>
              <Button
                variant={isLocked ? 'danger' : 'ghost'}
                size="xs"
                onClick={handleToggleLock}
                title={isLocked ? t('forum.unlock') : t('forum.lock')}
                className="!px-1.5 !py-1"
              >
                {isLocked ? <Unlock size={13} /> : <Lock size={13} />}
              </Button>
              <Button
                variant="danger"
                size="xs"
                onClick={handleDeleteThread}
                title={t('forum.delete_thread')}
                className="!px-1.5 !py-1"
              >
                <Trash2 size={13} />
              </Button>
            </div>
          )}

          {/* Author Controls (own thread, USER+): bump + lock */}
          {canManageOwn && (
            <div className="flex items-center gap-1.5 flex-shrink-0">
              {!isLocked && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleBump}
                  disabled={bumpOnCooldown}
                  title={bumpOnCooldown ? t('forum.bump_cooldown', { time: bumpReadyAt.toLocaleString(getDateLocale()) }) : t('forum.bump_title')}
                  className="!px-2.5 min-h-[40px]"
                >
                  <ArrowUp size={16} />
                </Button>
              )}
              {!isModerator() && (
                <Button
                  variant={isLocked ? 'danger' : 'ghost'}
                  size="sm"
                  onClick={handleAuthorLock}
                  title={isLocked ? t('forum.unlock_own') : t('forum.lock_own')}
                  className="!px-2.5 min-h-[40px]"
                >
                  {isLocked ? <Unlock size={16} /> : <Lock size={16} />}
                </Button>
              )}
            </div>
          )}
        </div>
      </Card>

      {/* OP Post — the opening post is the thread itself. When editing it we overlay
          an inline editor (saved via the thread endpoint); deleting it goes through
          the thread-delete flow, not the post-delete path.
          PostItem stays in the DOM but is hidden via CSS to avoid GPU-level unmount/mount
          turnover that crashes the Telegram WebView on mobile. */}
      <div className="relative">
        <div className={editingPost?._isOP ? 'invisible absolute inset-0 overflow-hidden' : ''}>
          <PostItem
            post={{ ...thread, _isOP: true, author: thread.author, user_liked: thread.user_liked, is_liked: thread.is_liked }}
            postNumber={1}
            isLocked={isLocked}
            user={user}
            canPost={canPostHere}
            onLike={() => handleLikeThread()}
            onShowLikes={() => setLikesView({ scope: 'threads', id: thread.id })}
            onQuote={setQuoteReply}
            onEdit={startEdit}
            onDelete={() => handleDeleteThread()}
            onRep={handleRepClick}
          />
        </div>
        {editingPost?._isOP && (
          <div id={`post-${thread.id}`} className="relative bg-dark-900/60 border border-primary-500/10 rounded-xl overflow-hidden scroll-mt-20">
            <div className="bg-primary-500/10 border-b border-primary-500/20 px-5 py-2 flex items-center justify-between">
              <span className="text-xs text-primary-400 font-medium">{t('forum.editing_op')}</span>
              <button onClick={cancelEdit} className="text-xs text-dark-400 hover:text-red-400 transition-colors">{t('common.cancel')}</button>
            </div>
            <MarkdownToolbar textareaRef={editRef} />
            <div className="p-4">
              <MentionTextarea
                textareaRef={editRef}
                value={editContent}
                onChange={setEditContent}
                rows={6}
                className="w-full bg-dark-900 border border-dark-700 rounded-xl p-4 resize-none focus:outline-none focus:border-primary-500/50 focus:ring-1 focus:ring-primary-500/20 transition-all text-sm leading-relaxed"
              />
              <div className="flex justify-end gap-2 mt-3">
                <Button variant="ghost" size="sm" onClick={cancelEdit}>{t('common.cancel')}</Button>
                <Button variant="primary" size="sm" onClick={handleEditSubmit} disabled={!editContent.trim() || editSubmitting}>
                  {editSubmitting ? t('common.saving') : t('forum.save_edit')}
                </Button>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Poll */}
      {thread.poll && (
        <PollCard
          poll={thread.poll}
          threadId={id}
          user={user}
          onUpdate={(updatedPoll) => setThread(prev => ({ ...prev, poll: updatedPoll }))}
        />
      )}

      {/* Pagination Top */}
      {totalPages > 1 && (
        <div className="flex justify-between items-center">
          <span className="text-xs text-dark-500">
            {t('forum.page_of', { page, total: totalPages, n: thread.reply_count || 0 })}
          </span>
          <Pagination page={page} totalPages={totalPages} onPageChange={handlePageChange} />
        </div>
      )}

      {/* Replies */}
      {posts.length > 0 && (
        <div className="space-y-3">
          <Card className="!p-3 sm:!px-5">
            <h2 className="font-mono text-sm font-semibold uppercase tracking-wider text-primary-300 flex items-center gap-2">
              <span className="text-primary-500/60">&gt;</span>
              {thread.reply_count || posts.length} {(thread.reply_count || posts.length) === 1 ? t('forum.reply_singular') : t('forum.replies_plural')}
            </h2>
          </Card>
          {posts.map((post, idx) => {
            const isEditingThis = editingPost?.id === post.id && !editingPost?._isOP
            return (
            <div key={post.id} className="relative">
              <div className={isEditingThis ? 'invisible absolute inset-0 overflow-hidden' : ''}>
                <PostItem
                  post={post}
                  postNumber={(page - 1) * 20 + idx + 2}
                  isLocked={isLocked}
                  user={user}
                  canPost={canPostHere}
                  onLike={handleLikePost}
                  onShowLikes={(postId) => setLikesView({ scope: 'posts', id: postId })}
                  onQuote={setQuoteReply}
                  onEdit={startEdit}
                  onDelete={setDeleteTarget}
                  onRep={handleRepClick}
                />
              </div>
              {isEditingThis && (
                <div id={`post-${post.id}`} className="relative bg-dark-900/60 border border-primary-500/10 rounded-xl overflow-hidden scroll-mt-20">
                  <div className="bg-primary-500/10 border-b border-primary-500/20 px-5 py-2 flex items-center justify-between">
                    <span className="text-xs text-primary-400 font-medium">{t('forum.editing_post', { n: (page - 1) * 20 + idx + 2 })}</span>
                    <button onClick={cancelEdit} className="text-xs text-dark-400 hover:text-red-400 transition-colors">{t('common.cancel')}</button>
                  </div>
                  <MarkdownToolbar textareaRef={editRef} />
                  <div className="p-4">
                    <MentionTextarea
                      textareaRef={editRef}
                      value={editContent}
                      onChange={setEditContent}
                      rows={6}
                      className="w-full bg-dark-900 border border-dark-700 rounded-xl p-4 resize-none focus:outline-none focus:border-primary-500/50 focus:ring-1 focus:ring-primary-500/20 transition-all text-sm leading-relaxed"
                    />
                    <div className="flex justify-end gap-2 mt-3">
                      <Button variant="ghost" size="sm" onClick={cancelEdit}>{t('common.cancel')}</Button>
                      <Button
                        variant="primary"
                        size="sm"
                        onClick={handleEditSubmit}
                        disabled={!editContent.trim() || editSubmitting}
                      >
                        {editSubmitting ? t('common.saving') : t('forum.save_edit')}
                      </Button>
                    </div>
                  </div>
                </div>
              )}
            </div>
            )
          })}
        </div>
      )}

      {/* Loading posts */}
      {loading && posts.length === 0 && thread && <Spinner size="sm" className="py-8" />}

      {/* Pagination Bottom */}
      {totalPages > 1 && (
        <div className="flex justify-center">
          <Pagination page={page} totalPages={totalPages} onPageChange={handlePageChange} />
        </div>
      )}

      {/* Reply Form - only shown when user has permission */}
      {canPostHere() && !isLocked && (
        <Card
          as={motion.form}
          ref={composerRef}
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          onSubmit={handleReply}
          className="!p-0 overflow-hidden scroll-mt-20"
        >
          <div className="bg-dark-800/50 border-b border-primary-500/10 px-4 sm:px-5 py-2.5 flex items-center justify-between gap-2">
            <h3 className="font-mono text-sm font-semibold uppercase tracking-wider text-primary-300 flex items-center gap-2 min-w-0">
              {replyTo ? (
                <span className="flex items-center gap-2 min-w-0">
                  <ReplyIcon size={15} className="text-dark-400 shrink-0" />
                  <span className="truncate">{t('forum.replying_to')} <span className="text-primary-400">{displayName(replyTo.author)}</span></span>
                </span>
              ) : (
                <><span className="text-primary-500/60">&gt;</span> {t('forum.post_a_reply')}</>
              )}
            </h3>
            <div className="flex items-center gap-2 shrink-0">
              {replyTo && (
                <button type="button" onClick={() => { setReplyTo(null); setReplyContent('') }} className="text-xs text-dark-400 hover:text-red-400 transition-colors">
                  {t('common.cancel')}
                </button>
              )}
              <div className="flex items-center gap-1 rounded-lg bg-dark-900/60 p-1">
                <button
                  type="button"
                  onClick={() => setPreviewMode(false)}
                  className={tabClass(!previewMode)}
                >
                  {t('forum.write')}
                </button>
                <button
                  type="button"
                  onClick={() => setPreviewMode(true)}
                  className={tabClass(previewMode)}
                >
                  {t('forum.preview')}
                </button>
              </div>
            </div>
          </div>

          {!previewMode && <MarkdownToolbar textareaRef={replyRef} />}

          <div className="p-4">
            {previewMode ? (
              <div className="min-h-[120px] bg-dark-900 border border-dark-700 rounded-xl p-4">
                {replyContent.trim() ? (
                  <MarkdownContent content={replyContent} />
                ) : (
                  <p className="text-dark-500 text-sm italic">{t('forum.nothing_to_preview')}</p>
                )}
              </div>
            ) : (
              <MentionTextarea
                textareaRef={replyRef}
                value={replyContent}
                onChange={setReplyContent}
                placeholder={t('forum.reply_placeholder')}
                rows={5}
                className="w-full bg-dark-900 border border-dark-700 rounded-xl p-4 resize-none focus:outline-none focus:border-primary-500/50 focus:ring-1 focus:ring-primary-500/20 transition-all text-sm leading-relaxed font-mono"
              />
            )}
            <div className="flex items-center justify-between mt-3">
              <span className="font-mono text-[10px] text-dark-500">
                {replyContent.length > 0 ? `${replyContent.length.toLocaleString()} / 50,000` : t('forum.markdown_supported')}
              </span>
              <Button
                type="submit"
                variant="primary"
                disabled={!replyContent.trim() || submitting}
              >
                {submitting ? (
                  <><div className="w-4 h-4 border-2 border-white/50 border-t-transparent rounded-full animate-spin" /> {t('forum.posting')}</>
                ) : t('forum.post_reply')}
              </Button>
            </div>
          </div>
        </Card>
      )}

      {/* No permission notice (not locked, but user can't post) */}
      {!isLocked && !canPostHere() && (
        <Card as={motion.div} initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="text-center !py-6">
          <Lock className="w-8 h-8 text-dark-500 mx-auto mb-2" />
          {userRole === 'TRIAL' ? (
            <>
              <p className="text-dark-300 text-sm font-medium">{t('forum.trial_cant_reply')}</p>
              <p className="text-dark-500 text-xs mt-1">
                {t('forum.board_requires_level', { role: minRoleToPost || 'USER' })}{' '}
                <Link to="/shop" className="text-primary-400 hover:underline">{t('forum.upgrade_account')}</Link> {t('forum.to_participate')}
              </p>
            </>
          ) : (
            <>
              <p className="text-dark-400 text-sm">{t('forum.no_reply_permission')}</p>
              <p className="text-dark-500 text-xs mt-1">
                {t('forum.board_requires_level_replies', { role: minRoleToPost || t('forum.role_higher') })}
              </p>
            </>
          )}
        </Card>
      )}

      {/* Locked notice */}
      {isLocked && (
        <Card as={motion.div} initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="text-center !py-6">
          <div className="flex justify-center mb-2">
            <Tag tone="red" icon={Lock}>{t('forum.locked')}</Tag>
          </div>
          <p className="text-dark-400 text-sm">{t('forum.thread_locked_notice')}</p>
        </Card>
      )}

      {/* Mobile quick-reply FAB — scrolls to + focuses the composer */}
      <AnimatePresence>
        {canPostHere() && !isLocked && showReplyFab && (
          <motion.button
            type="button"
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.8 }}
            onClick={scrollToComposer}
            aria-label={t('forum.reply')}
            className="fixed right-4 bottom-[calc(76px+env(safe-area-inset-bottom))] z-30 md:hidden flex items-center gap-2 px-4 h-12 rounded-full bg-primary-500 text-dark-950 font-semibold text-sm shadow-lg shadow-primary-500/30 active:scale-95 transition-transform"
          >
            <ReplyIcon size={18} />
            {t('forum.reply')}
          </motion.button>
        )}
      </AnimatePresence>

      {/* Delete Confirmation Modal */}
      <AnimatePresence>
        {deleteTarget && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4"
            onClick={() => setDeleteTarget(null)}
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              onClick={e => e.stopPropagation()}
              className="bg-dark-800 border border-dark-700 rounded-xl p-6 max-w-sm w-full"
            >
              <h3 className="font-semibold text-lg mb-2">{t('forum.delete_post_title')}</h3>
              <p className="text-dark-400 text-sm mb-4">{t('forum.delete_post_confirm')}</p>
              <div className="flex justify-end gap-2">
                <button
                  onClick={() => setDeleteTarget(null)}
                  className="px-4 py-2 text-sm text-dark-400 hover:text-white rounded-lg border border-dark-700/50 hover:bg-dark-700/50 transition-all"
                >
                  {t('common.cancel')}
                </button>
                <button
                  onClick={handleDelete}
                  className="px-4 py-2 text-sm bg-red-500 hover:bg-red-600 text-white rounded-lg transition-all font-medium"
                >
                  {t('common.delete')}
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Thread Delete Confirmation Modal */}
      <AnimatePresence>
        {threadDeleteOpen && (
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4"
            onClick={() => setThreadDeleteOpen(false)}
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.95, opacity: 0 }}
              onClick={e => e.stopPropagation()}
              className="bg-dark-800 border border-dark-700 rounded-xl p-6 max-w-sm w-full"
            >
              <h3 className="font-semibold text-lg mb-2">{t('forum.delete_thread_title')}</h3>
              <p className="text-dark-400 text-sm mb-4">{t('forum.delete_thread_confirm')}</p>
              <div className="flex justify-end gap-2">
                <button onClick={() => setThreadDeleteOpen(false)} className="px-4 py-2 text-sm text-dark-400 hover:text-white rounded-lg border border-dark-700/50 hover:bg-dark-700/50 transition-all">{t('common.cancel')}</button>
                <button onClick={doDeleteThread} className="px-4 py-2 text-sm bg-red-500 hover:bg-red-600 text-white rounded-lg transition-all font-medium">{t('common.delete')}</button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Rep Modal */}
      <AnimatePresence>
        {repTarget && (
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4"
            onClick={() => { setRepTarget(null); setRepComment('') }}
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              onClick={e => e.stopPropagation()}
              className="bg-dark-800 border border-dark-700 rounded-xl p-5 max-w-sm w-full space-y-4"
            >
              <h3 className="font-semibold text-lg">
                {t('forum.give_rep_to', { name: displayName(repTarget.author) })}
              </h3>
              <div className="flex gap-2">
                <button
                  onClick={() => setRepPositive(true)}
                  className={`flex-1 py-2.5 rounded-xl font-semibold flex items-center justify-center gap-2 transition-colors ${
                    repPositive ? 'bg-green-500/20 text-green-400 ring-1 ring-green-500/50' : 'bg-dark-700 text-dark-400'
                  }`}
                >
                  {t('forum.rep_plus')}
                </button>
                <button
                  onClick={() => setRepPositive(false)}
                  className={`flex-1 py-2.5 rounded-xl font-semibold flex items-center justify-center gap-2 transition-colors ${
                    !repPositive ? 'bg-red-500/20 text-red-400 ring-1 ring-red-500/50' : 'bg-dark-700 text-dark-400'
                  }`}
                >
                  {t('forum.rep_minus')}
                </button>
              </div>
              <textarea
                value={repComment}
                onChange={e => setRepComment(e.target.value)}
                placeholder={t('forum.rep_comment_placeholder')}
                rows={3}
                className="w-full bg-dark-700/50 border border-dark-600 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-1 focus:ring-primary-500 resize-none"
              />
              <div className="flex justify-end gap-2">
                <button
                  onClick={() => { setRepTarget(null); setRepComment('') }}
                  className="px-4 py-2 text-sm text-dark-400 hover:text-white rounded-lg border border-dark-700/50 hover:bg-dark-700/50 transition-all"
                >
                  {t('common.cancel')}
                </button>
                <button
                  onClick={handleGiveRep}
                  disabled={repSubmitting || !repComment.trim()}
                  className="px-4 py-2 text-sm bg-primary-500 hover:bg-primary-600 text-dark-950 rounded-lg transition-all font-medium disabled:opacity-50"
                >
                  {repSubmitting ? t('forum.submitting') : t('forum.give_rep')}
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Likes list (thread or post) */}
      <UserListModal
        open={!!likesView}
        onClose={() => setLikesView(null)}
        title={t('forum.liked_by')}
        url={likesView ? `/api/forum/${likesView.scope}/${likesView.id}/likes` : null}
      />
    </div>
  )
}
