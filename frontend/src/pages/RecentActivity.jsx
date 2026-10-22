import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import api from '../lib/api'
import { useAuthStore } from '../store/authStore'
import { TrendingUp, MessageSquare, Eye, Heart, ChevronRight, Pin, ArrowLeft, BarChart3, UserPlus, ThumbsUp, ThumbsDown } from 'lucide-react'
import { timeAgo, displayName, nameColorStyle } from '../lib/utils'
import { Card, PageHeading, Button, Tag, EmptyState, LoadingState, roleStyle } from '../components/ui'
import { useT } from '../lib/i18n'

// Round avatar with a username-initial fallback, used by every feed row.
function Avatar({ user, icon: Icon }) {
  return (
    <div className="w-10 h-10 rounded-full bg-dark-800 flex items-center justify-center flex-shrink-0 overflow-hidden">
      {user?.avatar_url ? (
        <img src={user.avatar_url} alt="" className="w-full h-full object-cover" />
      ) : Icon ? (
        <Icon size={16} className="text-dark-400" />
      ) : (
        <span className="text-sm font-bold text-dark-400">
          {(user ? displayName(user, false) : '?')[0]?.toUpperCase()}
        </span>
      )}
    </div>
  )
}

// Renders one activity-feed entry. The feed is heterogeneous: a `type`
// discriminator ('thread' | 'join' | 'rep') selects the layout.
function ActivityRow({ item }) {
  const t = useT()
  const time = (
    <span className="text-[11px] font-mono text-dark-500 flex-shrink-0 w-16 text-right">
      {timeAgo(item.last_post_at || item.created_at)}
    </span>
  )

  if (item.type === 'join') {
    return (
      <Link
        to={`/profile/${item.user?.id}`}
        className="flex items-center gap-3 px-4 py-3.5 hover:bg-primary-500/5 transition-colors"
      >
        <Avatar user={item.user} icon={UserPlus} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <Tag tone="green" icon={UserPlus}>{t('forum.tag_joined')}</Tag>
            <h3 className={`text-sm font-medium truncate ${roleStyle(item.user?.role).text}`} style={nameColorStyle(item.user)}>{displayName(item.user)}</h3>
          </div>
          <div className="mt-0.5 text-[11px] font-mono text-dark-500">
            {t('forum.joined_board')}
          </div>
        </div>
        {time}
        <ChevronRight size={14} className="text-dark-600 flex-shrink-0" />
      </Link>
    )
  }

  if (item.type === 'rep') {
    const positive = item.is_positive
    return (
      <Link
        to={`/profile/${item.to_user?.id}`}
        className="flex items-center gap-3 px-4 py-3.5 hover:bg-primary-500/5 transition-colors"
      >
        <Avatar user={item.from_user} icon={positive ? ThumbsUp : ThumbsDown} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <Tag tone={positive ? 'green' : 'red'} icon={positive ? ThumbsUp : ThumbsDown}>
              {positive ? '+REP' : '−REP'}
            </Tag>
            <h3 className="text-sm font-medium truncate">
              <span className={roleStyle(item.from_user?.role).text} style={nameColorStyle(item.from_user)}>{displayName(item.from_user)}</span> <span className="text-dark-400">→</span> <span className={roleStyle(item.to_user?.role).text} style={nameColorStyle(item.to_user)}>{displayName(item.to_user)}</span>
            </h3>
          </div>
          {item.comment && (
            <div className="mt-0.5 text-[11px] font-mono text-dark-500 truncate">
              “{item.comment}”
            </div>
          )}
        </div>
        {time}
        <ChevronRight size={14} className="text-dark-600 flex-shrink-0" />
      </Link>
    )
  }

  // Default: a thread.
  const th = item
  return (
    <Link
      to={`/thread/${th.slug}`}
      className="flex items-center gap-3 px-4 py-3.5 hover:bg-primary-500/5 transition-colors"
    >
      <Avatar user={th.author} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          {th.is_pinned && <Tag tone="amber" icon={Pin}>{t('forum.tag_pinned')}</Tag>}
          <h3
            className={`text-sm font-medium truncate ${th.title_color ? '' : 'text-white'}`}
            style={th.title_color ? { color: th.title_color, textShadow: th.title_glow ? `0 0 6px ${th.title_color}` : undefined } : undefined}
          >
            {th.title}
          </h3>
        </div>
        <div className="flex items-center gap-2 mt-0.5 text-[11px] font-mono text-dark-500 flex-wrap">
          {th.board_name && (
            <span className="text-primary-300 bg-primary-500/10 border border-primary-500/20 px-1.5 py-0.5 rounded">
              {th.board_name}
            </span>
          )}
          <span>{t('forum.by')} <span className={roleStyle(th.author?.role).text} style={nameColorStyle(th.author)}>{displayName(th.author)}</span></span>
          {th.reply_count > 0 && th.last_post_by && (
            <>
              <span>•</span>
              <span>{t('forum.last_by')} <span className={roleStyle(th.last_post_by?.role).text} style={nameColorStyle(th.last_post_by)}>{displayName(th.last_post_by)}</span></span>
            </>
          )}
        </div>
      </div>
      <div className="flex items-center gap-4 text-xs font-mono text-dark-500 flex-shrink-0">
        <div className="flex items-center gap-1" title={t('forum.replies_title')}>
          <MessageSquare size={12} />
          <span>{th.reply_count || 0}</span>
        </div>
        <div className="flex items-center gap-1" title={t('forum.views_title')}>
          <Eye size={12} />
          <span>{th.view_count || 0}</span>
        </div>
        <div className="flex items-center gap-1" title={t('forum.likes_title')}>
          <Heart size={12} />
          <span>{th.like_count || 0}</span>
        </div>
      </div>
      {time}
      <ChevronRight size={14} className="text-dark-600 flex-shrink-0" />
    </Link>
  )
}

export default function RecentActivity() {
  const t = useT()
  const { user } = useAuthStore()
  const [threads, setThreads] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [loadingMore, setLoadingMore] = useState(false)
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [activityCount, setActivityCount] = useState(null)
  const [countLoading, setCountLoading] = useState(false)
  const perPage = 50

  const isTrial = user?.role?.toUpperCase() === 'TRIAL'

  useEffect(() => {
    loadThreads(1, false)
  }, [])

  useEffect(() => {
    if (isTrial) {
      setCountLoading(true)
      api.get('/api/forum/activity-count')
        .then(res => setActivityCount(res.data))
        .catch(() => {})
        .finally(() => setCountLoading(false))
    }
  }, [isTrial])

  const loadThreads = async (pageVal, append) => {
    if (append) setLoadingMore(true)
    else setLoading(true)
    try {
      const res = await api.get('/api/forum/activity-feed', { params: { limit: perPage, page: pageVal } })
      const items = res.data.items || []
      setThreads(prev => append ? [...prev, ...items] : items)
      setTotal(res.data.total || 0)
      setPage(pageVal)
      setError(null)
    } catch (err) {
      if (import.meta.env.DEV) console.error('Failed to load recent activity:', err)
      if (!append) setError('forum.load_activity_failed')
    } finally {
      setLoading(false)
      setLoadingMore(false)
    }
  }

  const handleLoadMore = () => loadThreads(page + 1, true)
  const hasMore = threads.length < total

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Link to="/" className="p-2 rounded-lg hover:bg-dark-800/60 transition-colors">
          <ArrowLeft size={18} className="text-dark-400" />
        </Link>
        <PageHeading
          icon={TrendingUp}
          title={t('forum.tab_recent')}
          subtitle={t('forum.events_count', { n: total })}
          className="flex-1"
        />
      </div>

      {/* Trial Banner */}
      {isTrial && (
        <Card className="bg-gradient-to-r from-amber-500/10 via-amber-500/5 to-dark-900/80 border-amber-500/30">
          <div className="flex items-start gap-3">
            <div className="w-9 h-9 rounded-lg bg-amber-500/20 border border-amber-500/30 flex items-center justify-center flex-shrink-0">
              <BarChart3 size={18} className="text-amber-400" />
            </div>
            <div className="flex-1 min-w-0">
              <h3 className="font-semibold text-amber-300">{t('forum.unlock_full_access')}</h3>
              <p className="text-sm text-dark-300 mt-1">
                {countLoading
                  ? t('forum.activity_count_loading')
                  : t(activityCount?.total === 1 ? 'forum.activity_count_one' : 'forum.activity_count_many', { n: activityCount?.total ?? '...' })
                } {t('forum.trial_gain_access')}
              </p>
              <div className="flex items-center gap-2 mt-3">
                <Link
                  to="/shop"
                  className="px-4 py-1.5 rounded-lg bg-amber-500 hover:bg-amber-600 text-white text-sm font-semibold transition-colors"
                >
                  {t('forum.purchase_premium')}
                </Link>
                <Link
                  to="/board/request-access"
                  className="px-4 py-1.5 rounded-lg bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 text-sm font-semibold border border-amber-500/30 transition-colors"
                >
                  {t('forum.request_full_access')}
                </Link>
              </div>
            </div>
          </div>
        </Card>
      )}

      {/* Thread List */}
      {loading ? (
        <LoadingState label={t('forum.loading_activity')} className="min-h-[40vh] flex flex-col justify-center" />
      ) : error && threads.length === 0 ? (
        <Card className="text-center py-12">
          <p className="text-dark-500 text-sm mb-4">{t(error)}</p>
          <Button variant="primary" onClick={() => { setError(null); loadThreads(1, false) }}>{t('common.retry')}</Button>
        </Card>
      ) : threads.length === 0 ? (
        <Card className="text-center">
          <EmptyState icon={MessageSquare}>{t('forum.no_recent_activity')}</EmptyState>
          <p className="text-dark-500 text-sm -mt-6 pb-2">{t('forum.threads_appear')}</p>
        </Card>
      ) : (
        <Card className="!p-0 overflow-hidden">
          <div className="divide-y divide-primary-500/10">
            {threads.map(item => (
              <ActivityRow key={`${item.type}-${item.id}`} item={item} />
            ))}
          </div>
        </Card>
      )}

      {/* Load more */}
      {hasMore && (
        <div className="flex flex-col items-center gap-2 pt-1">
          <Button
            variant="secondary"
            size="sm"
            onClick={handleLoadMore}
            disabled={loadingMore}
            className="w-full max-w-xs"
          >
            {loadingMore ? t('forum.loading_more') : t('forum.load_more')}
          </Button>
          <span className="text-[11px] font-mono text-dark-500">
            {t('forum.n_of_total', { n: threads.length, total })}
          </span>
        </div>
      )}
    </div>
  )
}
