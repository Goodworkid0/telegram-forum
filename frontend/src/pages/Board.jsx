import { useState, useEffect, useRef } from 'react'
import { Link, useParams } from 'react-router-dom'
import api from '../lib/api'
import { useAuthStore } from '../store/authStore'
import { timeAgo, displayName, nameColorStyle } from '../lib/utils'
import Spinner from '../components/Spinner'
import ForumBreadcrumb from '../components/ForumBreadcrumb'
import { Card, PageHeading, Button, Tag, EmptyState, roleStyle } from '../components/ui'
import { Search, X, Pin, Lock, MessageSquare, Eye, Plus, ArrowUpDown, MessagesSquare } from 'lucide-react'
import { useT } from '../lib/i18n'

export default function Board() {
  const t = useT()
  const { id: slug } = useParams()
  const { user, canCreateThread } = useAuthStore()
  const userRole = user?.role?.toUpperCase()

  const [board, setBoard] = useState(null)
  const [threads, setThreads] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [page, setPage] = useState(1)
  const [hasMore, setHasMore] = useState(false)
  const [sort, setSort] = useState('latest')
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState(null)
  const [searching, setSearching] = useState(false)
  const [showSortMenu, setShowSortMenu] = useState(false)
  const searchTimer = useRef(null)
  const sortRef = useRef(null)

  const canCreate = canCreateThread(board)

  useEffect(() => { loadBoard() }, [slug])
  useEffect(() => { loadThreads() }, [slug, page, sort])
  useEffect(() => {
    const handler = (e) => { if (sortRef.current && !sortRef.current.contains(e.target)) setShowSortMenu(false) }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  useEffect(() => {
    clearTimeout(searchTimer.current)
    if (!searchQuery.trim() || searchQuery.trim().length < 2) {
      setSearchResults(null)
      return
    }
    searchTimer.current = setTimeout(async () => {
      setSearching(true)
      try {
        const res = await api.get('/api/forum/search', { params: { q: searchQuery.trim(), per_page: 15 } })
        const filtered = (res.data?.results || []).filter(r => r.board_name === board?.name)
        setSearchResults(filtered)
      } catch { setSearchResults([]) }
      finally { setSearching(false) }
    }, 400)
    return () => clearTimeout(searchTimer.current)
  }, [searchQuery, board?.name])

  const loadBoard = async () => {
    try {
      const res = await api.get(`/api/forum/boards/${slug}`)
      setBoard(res.data)
      setError(null)
    } catch (err) {
      if (import.meta.env.DEV) console.error('Failed to load board:', err)
      setError('forum.load_board_failed')
    }
  }

  const loadThreads = async () => {
    try {
      setLoading(true)
      const res = await api.get(`/api/forum/boards/${slug}/threads`, { params: { page, per_page: 20, sort } })
      if (page === 1) {
        setThreads(res.data.threads || [])
      } else {
        setThreads(prev => [...prev, ...(res.data.threads || [])])
      }
      setHasMore(res.data.has_more || false)
    } catch (err) {
      if (import.meta.env.DEV) console.error('Failed to load threads:', err)
    } finally {
      setLoading(false)
    }
  }

  const sortLabels = {
    latest: t('forum.sort_latest'),
    popular: t('forum.sort_popular'),
    replies: t('forum.sort_replies')
  }

  if (loading && !board && !error) {
    return <Spinner className="min-h-[60vh]" />
  }

  if (error && !board) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-20 text-center">
        <div className="text-dark-500 text-lg">{t(error)}</div>
        <Button
          variant="primary"
          className="mt-4"
          onClick={() => { setError(null); setLoading(true); loadBoard(); loadThreads() }}
        >
          {t('common.retry')}
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-5 max-w-4xl mx-auto">
      {/* Breadcrumb */}
      <ForumBreadcrumb items={[{ label: board?.name }]} />

      {/* Board Header Card (sticky) */}
      <Card blur={false} className="sticky top-16 z-20 bg-dark-900/95 space-y-4">
        <PageHeading
          icon={MessagesSquare}
          title={
            <span className="inline-flex items-center gap-2">
              {board?.icon && <span className="text-xl">{board.icon}</span>}
              {board?.name}
            </span>
          }
          subtitle={board?.description || `${t('forum.threads_count', { n: board?.thread_count || 0 })} · ${t('forum.posts_count', { n: board?.post_count || 0 })}`}
          right={
            canCreate ? (
              <Link to={`/board/${slug}/new`} className="flex-shrink-0">
                <Button variant="primary" icon={Plus}>
                  <span className="hidden sm:inline">{t('forum.new_thread')}</span>
                </Button>
              </Link>
            ) : (
              <div className="text-xs text-dark-500 flex-shrink-0">
                {userRole === 'TRIAL'
                  ? <Link to="/shop" className="text-primary-400 hover:underline font-medium">{t('forum.upgrade_to_post')}</Link>
                  : <span className="text-dark-500">{t('forum.restricted')}</span>
                }
              </div>
            )
          }
        />
        {/* Action bar with inline stats */}
        <div className="flex items-center gap-3">
          <div className="relative flex-1">
            <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-dark-500" />
            <input
              type="text"
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              placeholder={t('forum.search_in_board')}
              className="w-full bg-dark-950/60 border border-primary-500/15 rounded-lg pl-9 pr-9 py-2 text-sm focus:outline-none focus:border-primary-500/50 focus:shadow-[0_0_0_1px_rgba(0,200,230,0.35)] transition-all"
            />
            {searchQuery && (
              <button onClick={() => { setSearchQuery(''); setSearchResults(null) }} className="absolute right-3 top-1/2 -translate-y-1/2 text-dark-400 hover:text-white transition-colors">
                <X size={14} />
              </button>
            )}
          </div>
          {/* Inline stats */}
          <div className="hidden sm:flex items-center gap-1 text-xs text-dark-500 flex-shrink-0">
            <span className="text-dark-300 font-medium">{board?.thread_count || 0}</span>
            <span>{t('forum.threads_label')}</span>
            <span className="mx-1 text-dark-600">·</span>
            <span className="text-dark-300 font-medium">{board?.post_count || 0}</span>
            <span>{t('forum.posts_label')}</span>
          </div>
          <div className="relative" ref={sortRef}>
            <button
              onClick={() => setShowSortMenu(!showSortMenu)}
              className="flex items-center gap-1.5 bg-dark-800 border border-primary-500/15 rounded-lg px-3 py-2 text-sm text-dark-400 hover:text-white hover:border-primary-500/40 transition-all flex-shrink-0"
            >
              <ArrowUpDown size={14} />
              <span className="hidden sm:inline">{sortLabels[sort]}</span>
            </button>
            {showSortMenu && (
              <div className="absolute right-0 top-full mt-1 bg-dark-800 border border-primary-500/15 rounded-lg shadow-lg z-20 py-1 min-w-[140px]">
                {Object.entries(sortLabels).map(([key, label]) => (
                  <button
                    key={key}
                    onClick={() => { setSort(key); setPage(1); setShowSortMenu(false) }}
                    className={`w-full text-left px-3 py-2 text-sm transition-colors ${sort === key ? 'text-primary-400 bg-primary-500/10' : 'text-dark-300 hover:text-white hover:bg-dark-700/50'}`}
                  >
                    {label}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </Card>

      {/* Search Results */}
      {searchResults !== null && (
        <Card className="!p-0 overflow-hidden">
          <div className="px-5 py-3 bg-dark-800/50 border-b border-primary-500/15 flex items-center justify-between">
            <span className="text-xs text-dark-400">
              {searching ? (
                <span className="flex items-center gap-2"><div className="w-3 h-3 border-2 border-primary-400/50 border-t-transparent rounded-full animate-spin" /> {t('forum.searching')}</span>
              ) : (
                t(searchResults.length === 1 ? 'forum.results_for_one' : 'forum.results_for_many', { n: searchResults.length, q: searchQuery })
              )}
            </span>
            <button onClick={() => { setSearchQuery(''); setSearchResults(null) }} className="text-xs text-dark-400 hover:text-white transition-colors">{t('forum.clear')}</button>
          </div>
          {searchResults.length === 0 ? (
            <div className="p-10 text-center">
              <Search size={32} className="mx-auto text-dark-600 mb-3" />
              <p className="text-dark-400 text-sm">{t('forum.no_results_board')}</p>
            </div>
          ) : (
            <div className="divide-y divide-primary-500/10">
              {searchResults.map((r, i) => (
                <Link
                  key={`${r.type}-${r.thread_id}-${r.post_id || i}`}
                  to={r.post_id ? `/thread/${r.thread_slug}#post-${r.post_id}` : `/thread/${r.thread_slug}`}
                  className="block px-5 py-3.5 hover:bg-dark-800/40 transition-colors"
                >
                  <div className="flex items-center gap-2 mb-1">
                    <Tag tone={r.type === 'thread' ? 'cyan' : 'neutral'}>
                      {r.type === 'thread' ? t('forum.tag_thread') : t('forum.tag_post')}
                    </Tag>
                    <span className="text-sm font-medium text-white truncate">{r.thread_title}</span>
                  </div>
                  <p className="text-xs text-dark-500 line-clamp-2">{r.snippet}</p>
                </Link>
              ))}
            </div>
          )}
        </Card>
      )}

      {/* Threads List */}
      {!searchResults && (
        <>
          {threads.length === 0 ? (
            <Card className="text-center py-12">
              <EmptyState icon={MessageSquare}>{t('forum.no_threads')}</EmptyState>
              <div className="mt-4">
                {canCreate ? (
                  <Link to={`/board/${slug}/new`}>
                    <Button variant="primary" icon={Plus}>{t('forum.create_first_thread')}</Button>
                  </Link>
                ) : (
                  <p className="text-dark-500 text-xs">
                    {userRole === 'TRIAL'
                      ? <Link to="/shop" className="text-primary-400 hover:underline">{t('forum.upgrade_account')}</Link>
                      : t('forum.no_thread_perms')
                    }
                  </p>
                )}
              </div>
            </Card>
          ) : (
            <Card className="!p-0 overflow-hidden">
              <div className="divide-y divide-primary-500/10">
                {threads.map((thread, idx) => (
                  <Link
                    key={thread.id}
                    to={`/thread/${thread.slug}`}
                    className={`group flex items-center gap-4 px-5 py-4 hover:bg-dark-800/40 transition-all ${thread.has_unread ? 'border-l-2 border-l-primary-500 pl-[18px]' : ''}`}
                  >
                    {/* Author avatar */}
                    <div className="w-9 h-9 rounded-full bg-dark-700 flex items-center justify-center flex-shrink-0 overflow-hidden ring-1 ring-dark-600/50">
                      {thread.author?.avatar_url ? (
                        <img src={thread.author.avatar_url} alt="" className="w-full h-full object-cover" />
                      ) : (
                        <span className="text-xs font-bold text-dark-400">
                          {displayName(thread.author)?.[0]?.toUpperCase() || '?'}
                        </span>
                      )}
                    </div>

                    {/* Thread content */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1.5 flex-wrap">
                        {thread.is_pinned && <Tag tone="amber" icon={Pin}>{t('forum.tag_pinned')}</Tag>}
                        {thread.status === 'locked' && <Tag tone="red" icon={Lock}>{t('forum.tag_locked')}</Tag>}
                        <h3
                          className={`font-semibold text-sm truncate group-hover:text-primary-300 transition-colors ${thread.title_color ? '' : (thread.has_unread ? 'text-white' : 'text-dark-200')}`}
                          style={thread.title_color ? { color: thread.title_color, textShadow: thread.title_glow ? `0 0 6px ${thread.title_color}` : undefined } : undefined}
                        >
                          {thread.title}
                        </h3>
                      </div>
                      <div className="flex items-center gap-2 mt-1">
                        <span className={`text-xs font-medium ${roleStyle(thread.author?.role).text}`} style={nameColorStyle(thread.author)}>{displayName(thread.author)}</span>
                        <span className="text-dark-600">·</span>
                        <span className="text-xs text-dark-500">{timeAgo(thread.created_at)}</span>
                        {thread.tags?.length > 0 && (
                          <>
                            <span className="text-dark-600">·</span>
                            <div className="flex items-center gap-1">
                              {thread.tags.slice(0, 2).map(tag => (
                                <Tag key={tag} tone="neutral">{tag}</Tag>
                              ))}
                            </div>
                          </>
                        )}
                        {thread.reply_count > 0 && thread.last_post_by && thread.last_post_at ? (
                          <span className="text-xs text-dark-500 hidden sm:inline">
                            <span className="text-dark-600">·</span> {t('forum.last_reply_by')} <span className={`font-medium ${roleStyle(thread.last_post_by?.role).text}`} style={nameColorStyle(thread.last_post_by)}>{displayName(thread.last_post_by)}</span> {timeAgo(thread.last_post_at)}
                          </span>
                        ) : (
                          <span className="text-xs text-dark-500 hidden sm:inline">
                            <span className="text-dark-600">·</span> {t('forum.no_replies_yet')}
                          </span>
                        )}
                      </div>
                      {/* Mobile stat line (collapses right-side columns on <sm) */}
                      <div className="flex sm:hidden items-center gap-3 mt-1.5 font-mono text-[11px] text-dark-500">
                        <span className="inline-flex items-center gap-1">
                          <MessageSquare size={11} /> {t('forum.replies_count', { n: thread.reply_count || 0 })}
                        </span>
                        <span className="text-dark-600">·</span>
                        <span className="inline-flex items-center gap-1">
                          <Eye size={11} /> {t('forum.views_count', { n: thread.view_count || 0 })}
                        </span>
                      </div>
                    </div>

                    {/* Stats (sm+ only) */}
                    <div className="hidden sm:flex items-center gap-3 flex-shrink-0">
                      <div className="flex flex-col items-center min-w-[40px]">
                        <span className="text-xs font-semibold text-dark-300">{thread.reply_count || 0}</span>
                        <span className="text-[10px] text-dark-500">{t('forum.replies_label')}</span>
                      </div>
                      <div className="flex flex-col items-center min-w-[36px]">
                        <span className="text-xs font-semibold text-dark-300">{thread.view_count || 0}</span>
                        <span className="text-[10px] text-dark-500">{t('forum.views_label')}</span>
                      </div>
                    </div>
                  </Link>
                ))}
              </div>
            </Card>
          )}

          {/* Load More */}
          {hasMore && !searchResults && (
            <button
              onClick={() => setPage(p => p + 1)}
              disabled={loading}
              className="w-full py-3.5 rounded-xl bg-dark-800/40 border border-primary-500/15 text-sm text-dark-400 hover:text-primary-400 hover:border-primary-500/40 transition-all disabled:opacity-50"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2"><div className="w-3.5 h-3.5 border-2 border-dark-500 border-t-transparent rounded-full animate-spin" /> {t('app.loading')}</span>
              ) : (
                t('forum.load_more_threads')
              )}
            </button>
          )}
        </>
      )}
    </div>
  )
}
