import { useState, useEffect, useRef, Fragment } from 'react'
import { Link } from 'react-router-dom'
import api from '../lib/api'
import { useAuthStore } from '../store/authStore'
import { timeAgo, displayName, nameColorStyle } from '../lib/utils'
import Spinner from '../components/Spinner'
import { MessageSquare, Search, X, TrendingUp, ShieldCheck, Info, Star, ChevronRight, CornerDownRight, UserPlus, ThumbsUp, ThumbsDown, Link2, ExternalLink } from 'lucide-react'
import BannerRows from '../components/BannerRows'
import { Card, SectionHeader, Button, Tag, StatTile, EmptyState, tabClass, roleStyle } from '../components/ui'
import { useT } from '../lib/i18n'

// A single board row. depth 0 = top-level board; depth >= 1 = sub-board, which
// gets indented, a lighter background, a left accent and a smaller "branch" icon
// so it reads as nested under its parent rather than as a sibling board.
function BoardRow({ board, depth = 0 }) {
  const t = useT()
  const isSub = depth > 0
  const isLink = board.board_type === 'link'
  const isExternal = isLink && /^https?:\/\//i.test(board.link_target || '')

  // A link board is a shortcut to another page (e.g. /leaderboard, /giveaways,
  // or an external URL) rather than a thread container — render it as a plain
  // link with no thread/post stats. External targets open in a new tab.
  if (isLink) {
    const rowClass = `flex items-center gap-4 p-4 transition-colors ${
      isSub
        ? 'bg-dark-900/40 hover:bg-primary-500/[0.07] border-l-2 border-primary-500/25'
        : 'hover:bg-primary-500/5'
    }`
    const rowStyle = isSub ? { paddingLeft: `${depth * 1.5 + 1}rem` } : undefined
    const inner = (
      <>
        <div className={`${isSub ? 'w-8 h-8 rounded-lg' : 'w-10 h-10 rounded-xl'} bg-gradient-to-br from-accent-purple/20 to-primary-500/20 border border-primary-500/15 flex items-center justify-center flex-shrink-0`}>
          <Link2 size={isSub ? 14 : 18} className="text-accent-purple" />
        </div>
        <div className="flex-1 min-w-0">
          <h3 className={`font-semibold text-white ${isSub ? 'text-sm' : ''}`}>{board.name}</h3>
          {board.description && (
            <p className="text-sm text-dark-400 truncate">{board.description}</p>
          )}
        </div>
        {isExternal
          ? <ExternalLink size={16} className="text-dark-500 flex-shrink-0" />
          : <ChevronRight size={18} className="text-dark-500 flex-shrink-0" />}
      </>
    )
    return isExternal
      ? <a href={board.link_target} target="_blank" rel="noopener noreferrer" className={rowClass} style={rowStyle}>{inner}</a>
      : <Link to={board.link_target || '/'} className={rowClass} style={rowStyle}>{inner}</Link>
  }

  return (
    <Link
      to={`/board/${board.slug}`}
      className={`flex items-center gap-4 p-4 transition-colors ${
        isSub
          ? 'bg-dark-900/40 hover:bg-primary-500/[0.07] border-l-2 border-primary-500/25'
          : 'hover:bg-primary-500/5'
      }`}
      style={isSub ? { paddingLeft: `${depth * 1.5 + 1}rem` } : undefined}
    >
      <div className={`${isSub ? 'w-8 h-8 rounded-lg' : 'w-10 h-10 rounded-xl'} bg-gradient-to-br from-primary-500/20 to-accent-purple/20 border border-primary-500/15 flex items-center justify-center flex-shrink-0`}>
        {isSub
          ? <CornerDownRight size={14} className="text-primary-400/70" />
          : <MessageSquare size={18} className="text-primary-400" />}
      </div>
      <div className="flex-1 min-w-0">
        <h3 className={`font-semibold text-white ${isSub ? 'text-sm' : ''}`}>{board.name}</h3>
        {board.description && (
          <p className="text-sm text-dark-400 truncate">{board.description}</p>
        )}
      </div>
      <div className="text-right text-xs flex-shrink-0 min-w-0 max-w-[200px]">
        {board.last_thread ? (
          <>
            <p className="text-dark-300 truncate font-medium">{board.last_thread.title}</p>
            <p className="text-dark-500 mt-0.5 truncate">
              <span className={`font-medium ${roleStyle(board.last_thread.author?.role).text}`} style={nameColorStyle(board.last_thread.author)}>{displayName(board.last_thread.author)}</span>
              {board.last_thread.last_post_by && board.last_thread.last_post_by.id !== board.last_thread.author.id && (
                <>
                  <span className="text-dark-600"> → </span>
                  <span className={`font-medium ${roleStyle(board.last_thread.last_post_by?.role).text}`} style={nameColorStyle(board.last_thread.last_post_by)}>{displayName(board.last_thread.last_post_by)}</span>
                </>
              )}
              <span className="text-dark-600"> · </span>
              <span>{timeAgo(board.last_thread.last_post_at || board.last_post_at)}</span>
            </p>
          </>
        ) : (
          <>
            <div className="text-dark-400">{t('forum.threads_count', { n: board.thread_count || 0 })}</div>
            <div className="text-dark-400">{t('forum.posts_count', { n: board.post_count || 0 })}</div>
          </>
        )}
      </div>
      <ChevronRight size={18} className="text-dark-500 flex-shrink-0" />
    </Link>
  )
}

// Compact row for the home-page "Recent Activity" tab. The feed is mixed —
// `item.type` is 'thread' | 'join' | 'rep' — so each gets its own one-line layout.
function ActivityFeedRow({ item }) {
  const t = useT()
  const time = (
    <span className="text-[11px] font-mono text-dark-500 flex-shrink-0 w-16 text-right">
      {timeAgo(item.last_post_at || item.created_at)}
    </span>
  )

  if (item.type === 'join') {
    return (
      <Link to={`/profile/${item.user?.id}`} className="flex items-center gap-3 px-4 py-3.5 hover:bg-primary-500/5 transition-colors">
        <UserPlus size={15} className="text-neon-400 flex-shrink-0" />
        <div className="flex-1 min-w-0 text-sm">
          <span className={`font-medium ${roleStyle(item.user?.role).text}`} style={nameColorStyle(item.user)}>{displayName(item.user)}</span>
          <span className="text-dark-400"> {t('forum.joined_board')}</span>
        </div>
        {time}
      </Link>
    )
  }

  if (item.type === 'rep') {
    const positive = item.is_positive
    const Icon = positive ? ThumbsUp : ThumbsDown
    return (
      <Link to={`/profile/${item.to_user?.id}`} className="flex items-center gap-3 px-4 py-3.5 hover:bg-primary-500/5 transition-colors">
        <Icon size={15} className={`flex-shrink-0 ${positive ? 'text-neon-400' : 'text-red-400'}`} />
        <div className="flex-1 min-w-0 text-sm truncate">
          <span className={`font-medium ${roleStyle(item.from_user?.role).text}`} style={nameColorStyle(item.from_user)}>{displayName(item.from_user)}</span>
          <span className="text-dark-400"> {t('forum.gave_rep', { rep: positive ? '+rep' : '−rep' })} </span>
          <span className={`font-medium ${roleStyle(item.to_user?.role).text}`} style={nameColorStyle(item.to_user)}>{displayName(item.to_user)}</span>
        </div>
        {time}
      </Link>
    )
  }

  const th = item
  return (
    <Link to={`/thread/${th.slug}`} className="flex items-center gap-3 px-4 py-3.5 hover:bg-primary-500/5 transition-colors">
      <MessageSquare size={15} className="text-primary-400 flex-shrink-0" />
      <div className="flex-1 min-w-0">
        <h3
          className={`text-sm font-medium truncate ${th.title_color ? '' : 'text-white'}`}
          style={th.title_color ? { color: th.title_color, textShadow: th.title_glow ? `0 0 6px ${th.title_color}` : undefined } : undefined}
        >
          {th.title}
        </h3>
        <div className="flex items-center gap-2 mt-0.5 text-[11px] font-mono text-dark-500 flex-wrap">
          {th.board_name && (
            <span className="text-primary-300 bg-primary-500/10 border border-primary-500/20 px-1.5 py-0.5 rounded">
              {th.board_name}
            </span>
          )}
          <span>{t('forum.by')} <span className={roleStyle(th.author?.role).text} style={nameColorStyle(th.author)}>{displayName(th.author)}</span></span>
        </div>
      </div>
      {time}
      <ChevronRight size={14} className="text-dark-600 flex-shrink-0" />
    </Link>
  )
}

export default function ForumHome() {
  const t = useT()
  const [tabs, setTabs] = useState([])
  const [stats, setStats] = useState(null)
  const [recentThreads, setRecentThreads] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [activeTabId, setActiveTabId] = useState('all')
  const [activeSectionId, setActiveSectionId] = useState(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState(null)
  const [searching, setSearching] = useState(false)
  const searchTimer = useRef(null)
  const { user } = useAuthStore()

  // Role hierarchy for access check (uppercase to match API)
  const roleOrder = { TRIAL: 0, USER: 1, MODERATOR: 2, ADMIN: 3 }
  const actualRole = (user?.role || 'TRIAL').toUpperCase()
  const userRoleLevel = roleOrder[actualRole] ?? 0

  // Filter tabs user can access (based on effective role)
  const accessibleTabs = tabs.filter(t => {
    const tabRoleLevel = roleOrder[t.min_role?.toUpperCase()] ?? 0
    return userRoleLevel >= tabRoleLevel
  })

  // Get current tab's sections (filtered by role). When 'all', combine all tabs.
  const currentTab = accessibleTabs.find(t => t.id === activeTabId)
  const allSections = activeTabId === 'all'
    ? accessibleTabs.flatMap(t => t.sections || [])
    : (currentTab?.sections || [])
  const visibleSections = allSections.filter(s => {
    const sectionRoleLevel = roleOrder[s.min_role?.toUpperCase()] ?? 0
    return userRoleLevel >= sectionRoleLevel
  })

  // Get active section (null when 'all' selected)
  const activeSection = activeSectionId === 'all' ? null : visibleSections.find(s => s.id === activeSectionId)

  useEffect(() => {
    loadData()
  }, [])

  // Search debounce
  useEffect(() => {
    clearTimeout(searchTimer.current)
    if (!searchQuery.trim() || searchQuery.trim().length < 2) {
      setSearchResults(null)
      return
    }
    searchTimer.current = setTimeout(async () => {
      setSearching(true)
      try {
        const res = await api.get('/api/forum/search', { params: { q: searchQuery.trim(), per_page: 20 } })
        setSearchResults({ results: res.data?.results || [], total: res.data?.total || 0 })
      } catch { setSearchResults({ results: [], total: 0 }) }
      finally { setSearching(false) }
    }, 400)
    return () => clearTimeout(searchTimer.current)
  }, [searchQuery])

  // Update active tab when user or tabs change
  useEffect(() => {
    if (accessibleTabs.length > 0 && !accessibleTabs.find(t => t.id === activeTabId) && activeTabId !== 'all' && activeTabId !== 'recent') {
      // Find default tab for trial users
      const defaultTab = accessibleTabs.find(t => t.is_default)
      setActiveTabId(defaultTab?.id || accessibleTabs[0]?.id || null)
    }
  }, [accessibleTabs.length, user?.role])

  // Update active section when tab changes - default to 'all'
  useEffect(() => {
    if (visibleSections.length > 0) {
      setActiveSectionId('all')
    } else {
      setActiveSectionId(null)
    }
  }, [activeTabId, visibleSections.length])

  const loadData = async () => {
    // Settle each request independently so one failure doesn't blank the whole page
    const [tabsRes, statsRes, recentRes] = await Promise.allSettled([
      api.get('/api/forum/tabs'),
      api.get('/api/forum/stats'),
      api.get('/api/forum/activity-feed', { params: { limit: 12 } })
    ])
    if (tabsRes.status === 'fulfilled') setTabs(tabsRes.value.data)
    if (statsRes.status === 'fulfilled') setStats(statsRes.value.data)
    if (recentRes.status === 'fulfilled') setRecentThreads(recentRes.value.data?.items || recentRes.value.data || [])
    // The tabs feed is the backbone of the page — only show a hard error if it fails
    if (tabsRes.status === 'rejected') {
      if (import.meta.env.DEV) console.error('Failed to load forum:', tabsRes.reason)
      setError('forum.load_forum_failed')
    } else {
      setError(null)
    }
    setLoading(false)
  }

  if (loading) {
    return <Spinner className="min-h-[60vh]" />
  }

  if (error && tabs.length === 0) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-20 text-center">
        <div className="text-dark-500 text-lg mb-4">{t(error)}</div>
        <Button variant="primary" onClick={() => { setError(null); setLoading(true); loadData() }}>{t('common.retry')}</Button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Search Bar */}
      <div className="relative">
        <Search size={16} className="absolute left-4 top-1/2 -translate-y-1/2 text-dark-400" />
        <input
          type="text"
          value={searchQuery}
          onChange={e => setSearchQuery(e.target.value)}
          placeholder={t('forum.search_placeholder')}
          className="w-full bg-dark-950/60 border border-primary-500/15 rounded-xl pl-11 pr-10 py-3 text-sm font-mono focus:outline-none focus:border-primary-500/50 focus:shadow-[0_0_0_1px_rgba(0,200,230,0.35)] placeholder-dark-500 transition-all"
        />
        {searchQuery && (
          <button onClick={() => setSearchQuery('')} className="absolute right-4 top-1/2 -translate-y-1/2 text-dark-400 hover:text-white">
            <X size={14} />
          </button>
        )}
      </div>

      {/* Trial Welcome Banner */}
      {user?.role?.toUpperCase() === 'TRIAL' && (
        <Card className="!p-4">
          <div className="flex items-start gap-3">
            <div className="w-9 h-9 rounded-xl bg-primary-500/15 border border-primary-500/25 flex items-center justify-center flex-shrink-0">
              <Info size={18} className="text-primary-400" />
            </div>
            <div className="flex-1 min-w-0">
              <h3 className="font-mono text-sm font-bold uppercase tracking-wider text-primary-300">{t('forum.trial_banner_title')}</h3>
              <p className="text-sm text-dark-300 mt-1">
                {t('forum.trial_banner_text')}
              </p>
              <div className="flex items-center gap-3 mt-3 flex-wrap">
                <Link to="/board/request-access">
                  <Button variant="primary" size="sm" icon={ShieldCheck}>
                    {t('forum.request_full_access')}
                  </Button>
                </Link>
                <Link to="/shop">
                  <Button variant="secondary" size="sm" icon={Star}>
                    {t('forum.purchase_premium')}
                  </Button>
                </Link>
                <span className="text-xs text-dark-400">
                  {t('forum.trial_earn_prefix')} <strong className="text-white">{t('forum.trial_earn_strong')}</strong> {t('forum.trial_earn_suffix')}
                </span>
              </div>
            </div>
          </div>
        </Card>
      )}

      {/* Search Results Overlay */}
      {searchResults && (
        <Card className="!p-0 overflow-hidden">
          <div className="px-4 py-2 bg-dark-950/40 border-b border-primary-500/10 flex items-center justify-between">
            <span className="text-xs font-mono text-dark-400">
              {searching ? t('forum.searching_lower') : t(searchResults.total === 1 ? 'forum.results_for_one' : 'forum.results_for_many', { n: searchResults.total, q: searchQuery })}
            </span>
            <button onClick={() => { setSearchQuery(''); setSearchResults(null) }} className="text-xs text-dark-400 hover:text-white">{t('forum.clear')}</button>
          </div>
          {searchResults.results.length === 0 ? (
            <EmptyState icon={Search}>{t('forum.no_results_found')}</EmptyState>
          ) : (
            <div className="divide-y divide-primary-500/10 max-h-[400px] overflow-y-auto">
              {searchResults.results.map((r, i) => (
                <Link
                  key={`${r.type}-${r.thread_id}-${r.post_id || i}`}
                  to={r.post_id ? `/thread/${r.thread_slug}#post-${r.post_id}` : `/thread/${r.thread_slug}`}
                  className="block p-3 hover:bg-primary-500/5 transition-colors"
                >
                  <div className="flex items-center gap-2">
                    <Tag tone={r.type === 'thread' ? 'cyan' : 'neutral'}>{r.type === 'thread' ? t('forum.tag_thread') : t('forum.tag_post')}</Tag>
                    <span className="text-sm font-medium text-white truncate">{r.thread_title}</span>
                    {r.board_name && <span className="text-[10px] text-dark-500 ml-auto flex-shrink-0">{r.board_name}</span>}
                  </div>
                  <p className="text-xs text-dark-400 mt-1 line-clamp-2">{r.snippet}</p>
                  <div className="text-[10px] text-dark-500 mt-1">
                    {r.author && <>{displayName(r.author)} • </>}
                    {timeAgo(r.created_at)}
                  </div>
                </Link>
              ))}
            </div>
          )}
        </Card>
      )}

      {/* Tab strip — sticky under the global app header (header is sticky ~top-0, ~56-64px tall) */}
      <div className="sticky top-16 z-20 -mx-4 px-4 py-2 bg-dark-950/85 backdrop-blur">
        <div className="flex items-center justify-between gap-4">
          <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-hide flex-1">
            <button
              onClick={() => setActiveTabId('all')}
              className={tabClass(activeTabId === 'all')}
            >
              {t('forum.tab_all')}
            </button>
            {accessibleTabs.map(tab => (
              <button
                key={tab.id}
                onClick={() => { setActiveTabId(tab.id); setActiveSectionId('all') }}
                className={tabClass(activeTabId === tab.id && activeTabId !== 'recent')}
              >
                {tab.icon && <span className="mr-1">{tab.icon}</span>}
                {tab.name}
              </button>
            ))}
            <button
              onClick={() => setActiveTabId('recent')}
              className={`${tabClass(activeTabId === 'recent')} inline-flex items-center gap-1.5`}
            >
              <TrendingUp size={13} />
              {t('forum.tab_recent')}
            </button>
          </div>
        </div>
      </div>

      {/* Banner Ads — 4 horizontal rows below tabs */}
      <BannerRows />

      {/* Boards — grouped by section, no section nav */}
      {activeTabId !== 'recent' && visibleSections.length === 0 ? (
        <Card>
          <EmptyState icon={MessageSquare}>
            {t('forum.no_sections')}
          </EmptyState>
        </Card>
      ) : activeTabId !== 'recent' ? (
        <div className="space-y-6">
          {visibleSections.map(section => {
            const filteredBoards = (section.boards || []).filter(board => {
              const boardRoleLevel = roleOrder[board.min_role?.toUpperCase()] ?? 0
              return userRoleLevel >= boardRoleLevel
            })
            if (!filteredBoards.length) return null
            return (
              <div key={section.id}>
                <SectionHeader>{section.name}</SectionHeader>
                <Card className="!p-0 overflow-hidden">
                  <div className="divide-y divide-primary-500/10">
                    {(() => {
                      // Nest sub-boards (parent_id) under their parent instead of
                      // listing them flat as siblings. Group children by parent;
                      // a board is a root when it has no parent_id or its parent
                      // isn't visible here (filtered by role / different section).
                      const byParent = {}
                      filteredBoards.forEach(b => {
                        const k = b.parent_id || 0
                        ;(byParent[k] = byParent[k] || []).push(b)
                      })
                      const present = new Set(filteredBoards.map(b => b.id))
                      const roots = filteredBoards.filter(b => !b.parent_id || !present.has(b.parent_id))
                      const renderNode = (board, depth) => (
                        <Fragment key={board.id}>
                          <BoardRow board={board} depth={depth} />
                          {depth < 4 && (byParent[board.id] || []).map(child => renderNode(child, depth + 1))}
                        </Fragment>
                      )
                      return roots.map(b => renderNode(b, 0))
                    })()}
                  </div>
                </Card>
              </div>
            )
          })}
        </div>
      ) : (
        <div>
          <SectionHeader
            right={
              <Link to="/recent" className="text-xs font-mono text-primary-400 hover:text-primary-300 inline-flex items-center gap-1">
                {t('forum.view_all')} <ChevronRight size={12} />
              </Link>
            }
          >
            {t('forum.recent_activity_header')}
          </SectionHeader>
          {recentThreads.length === 0 ? (
            <Card>
              <EmptyState icon={MessageSquare}>{t('forum.no_recent_activity')}</EmptyState>
            </Card>
          ) : (
            <Card className="!p-0 overflow-hidden">
              <div className="divide-y divide-primary-500/10">
                {recentThreads.map(item => (
                  <ActivityFeedRow key={`${item.type}-${item.id}`} item={item} />
                ))}
              </div>
            </Card>
          )}
        </div>
      )}

      {/* Board Statistics — mono terminal stat strip */}
      {stats && (
        <div>
          <SectionHeader>{t('forum.board_stats')}</SectionHeader>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <StatTile label={t('forum.stat_threads')} value={stats.total_threads} accent="cyan" />
            <StatTile label={t('forum.stat_members')} value={stats.total_users} accent="emerald" />
            <StatTile label={t('forum.stat_online_24h')} value={stats.online_24h} accent="green" />
            {stats.latest_user ? (
              <Card className="!p-3 text-center">
                <Link
                  to={`/profile/${stats.latest_user.id}`}
                  className="text-base font-bold font-mono text-amber-400 hover:underline truncate block"
                >
                  {displayName(stats.latest_user)}
                </Link>
                <p className="mt-0.5 text-[10px] uppercase tracking-widest text-dark-400">
                  {t('forum.stat_newest')} · {timeAgo(stats.latest_user.joined_at)}
                </p>
              </Card>
            ) : (
              <StatTile label={t('forum.stat_newest')} value="—" accent="default" />
            )}
          </div>
        </div>
      )}
    </div>
  )
}
