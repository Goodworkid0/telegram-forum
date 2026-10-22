import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import api from '../lib/api'
import { useToast } from '../components/Toast'
import { displayName, parseDate, nameColorStyle } from '../lib/utils'
import { roleStyle } from '../components/admin/ui'
import { Trophy, Clock } from 'lucide-react'
import { Card, SectionHeader, PageHeading, Button, EmptyState, LoadingState } from '../components/ui'
import { useT, getDateLocale } from '../lib/i18n'

const PER_PAGE = 20

const TOP_COLORS = {
  1: { text: 'text-yellow-400', bg: 'bg-yellow-500/10', border: 'border-yellow-500/30' },
  2: { text: 'text-gray-300', bg: 'bg-gray-400/10', border: 'border-gray-400/30' },
  3: { text: 'text-amber-600', bg: 'bg-amber-600/10', border: 'border-amber-600/30' },
}

const XP_REWARDS = [1000, 750, 500, 400, 300, 250, 200, 150, 100, 50]

export default function Leaderboard() {
  const { showToast } = useToast()
  const t = useT()
  const [entries, setEntries] = useState([])
  const [currentUserRank, setCurrentUserRank] = useState(null)
  const [currentUserValue, setCurrentUserValue] = useState(null)
  const [page, setPage] = useState(1)
  const [hasMore, setHasMore] = useState(false)
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [periodEndsAt, setPeriodEndsAt] = useState(null)
  const [periodStartsAt, setPeriodStartsAt] = useState(null)
  const [countdown, setCountdown] = useState(null)

  useEffect(() => {
    if (!periodEndsAt) return
    const timer = setInterval(() => {
      const now = Date.now()
      const end = parseDate(periodEndsAt).getTime()
      const diff = end - now
      if (diff <= 0) { setCountdown({ ending: true }); clearInterval(timer); return }
      const d = Math.floor(diff / 86400000)
      const h = Math.floor((diff % 86400000) / 3600000)
      const m = Math.floor((diff % 3600000) / 60000)
      setCountdown({ d, h, m })
    }, 1000)
    return () => clearInterval(timer)
  }, [periodEndsAt])

  const loadEntries = useCallback(async (pageVal, append = false) => {
    try {
      if (append) setLoadingMore(true)
      else setLoading(true)

      const { data } = await api.get(
        `/api/users/leaderboard?type=score&page=${pageVal}&per_page=${PER_PAGE}`
      )

      setEntries(prev => append ? [...prev, ...(data.entries || [])] : (data.entries || []))
      setCurrentUserRank(data.current_user_rank ?? null)
      setCurrentUserValue(data.current_user_value ?? null)
      setPeriodEndsAt(data.period_ends_at)
      setPeriodStartsAt(data.period_starts_at)
      setHasMore((data.entries || []).length >= PER_PAGE)
    } catch (err) {
      if (!append) setEntries([])
      showToast(t('lb.load_failed'), 'error')
    } finally {
      setLoading(false)
      setLoadingMore(false)
    }
  }, [showToast])

  useEffect(() => { setEntries([]); setPage(1); setHasMore(false); loadEntries(1, false) }, [loadEntries])

  const handleLoadMore = () => {
    const nextPage = page + 1
    setPage(nextPage)
    loadEntries(nextPage, true)
  }

  return (
    <div className="max-w-2xl mx-auto space-y-4">
      {/* Header */}
      <Card>
        <PageHeading
          icon={Trophy}
          title={t('lb.title')}
          subtitle={t('lb.subtitle')}
        />
        {periodEndsAt && (
          <div className="mt-3 flex items-center gap-2 text-xs font-mono text-dark-400 bg-dark-950/60 border border-primary-500/15 rounded-xl px-3 py-2">
            <Clock size={13} className="text-primary-400" />
            <span>{t('lb.resets_in')} <span className="text-primary-300 font-semibold">{countdown ? (countdown.ending ? t('lb.ending') : t('lb.countdown', countdown)) : ''}</span></span>
            <span className="text-dark-600 ml-auto">
              {parseDate(periodStartsAt).toLocaleDateString(getDateLocale())} — {parseDate(periodEndsAt).toLocaleDateString(getDateLocale())}
            </span>
          </div>
        )}
      </Card>

      {/* Rewards info */}
      <Card>
        <SectionHeader>{t('lb.top_rewards')}</SectionHeader>
        <div className="flex flex-wrap gap-1">
          {XP_REWARDS.map((xp, i) => (
            <span key={i} className={`text-[10px] font-mono font-semibold px-2 py-0.5 rounded-full border ${i < 3 ? 'bg-yellow-500/10 text-yellow-400 border-yellow-500/30' : 'bg-dark-800/70 text-dark-300 border-dark-600'}`}>
              #{i + 1}: +{xp} XP
            </span>
          ))}
        </div>
      </Card>

      {/* Scoring info */}
      <Card>
        <SectionHeader>{t('lb.how_to_earn')}</SectionHeader>
        <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-[11px] font-mono text-dark-400">
          <span>{t('lb.pt_thread')}: <span className="text-primary-400">{t('lb.plus_pts', { n: 5 })}</span></span>
          <span>{t('lb.pt_post')}: <span className="text-primary-400">{t('lb.plus_pts', { n: 2 })}</span></span>
          <span>{t('lb.pt_like_received')}: <span className="text-primary-400">{t('lb.plus_pt', { n: 1 })}</span></span>
          <span>{t('lb.pt_like_given')}: <span className="text-primary-400">{t('lb.plus_pt', { n: 1 })}</span></span>
          <span>{t('lb.pt_rep_received')}: <span className="text-primary-400">{t('lb.plus_pts', { n: 3 })}</span></span>
        </div>
      </Card>

      {/* Your Rank */}
      {currentUserRank != null && (
        <Card className="bg-primary-500/10 border-primary-500/30">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Trophy size={16} className="text-primary-400" />
              <span className="text-sm text-dark-300">{t('lb.your_rank')}</span>
              <span className="font-bold font-mono text-lg text-white">#{currentUserRank}</span>
            </div>
            <span className="font-semibold font-mono text-primary-400 text-sm">{t('lb.pts_value', { n: currentUserValue?.toLocaleString() ?? '' })}</span>
          </div>
        </Card>
      )}

      {/* Loading */}
      {loading && entries.length === 0 && <LoadingState label={t('lb.loading')} className="min-h-[40vh] flex flex-col justify-center" />}

      {/* Empty */}
      {!loading && entries.length === 0 && (
        <Card className="text-center">
          <EmptyState icon={Trophy}>{t('lb.no_entries')}</EmptyState>
          <p className="text-dark-500 text-xs -mt-6 pb-2">{t('lb.empty_hint')}</p>
        </Card>
      )}

      {/* Ranked List */}
      {entries.length > 0 && (
        <div className="space-y-1">
          {entries.map((entry) => {
            const rank = entry.rank
            const isTop3 = rank <= 3
            const isMe = currentUserRank != null && rank === currentUserRank
            const tc = TOP_COLORS[rank] || {}

            return (
              <Link
                key={entry.user_id}
                to={`/profile/${entry.user_id}`}
                className={`flex items-center gap-3 rounded-xl p-3 border transition-colors ${
                  isMe
                    ? 'bg-primary-500/10 border-primary-500/30 hover:brightness-110'
                    : isTop3
                      ? `${tc.bg} ${tc.border} hover:brightness-110`
                      : 'bg-dark-900/80 border-primary-500/10 hover:border-primary-500/25'
                }`}
              >
                <div className={`w-8 h-8 rounded-lg flex items-center justify-center font-bold font-mono text-sm flex-shrink-0 ${isTop3 ? `${tc.text} bg-dark-950/60` : 'text-dark-400 bg-dark-800/70'}`}>
                  {rank}
                </div>

                <div className="w-9 h-9 rounded-full bg-dark-800 flex items-center justify-center overflow-hidden flex-shrink-0">
                  {entry.avatar_url ? (
                    <img src={entry.avatar_url} alt="" className="w-full h-full object-cover" />
                  ) : (
                    <span className="text-sm font-bold text-dark-400">{displayName(entry, false)[0]?.toUpperCase() || '?'}</span>
                  )}
                </div>

                <div className="flex-1 min-w-0">
                  <span className={`font-semibold text-sm truncate block ${roleStyle(entry.role).text}`} style={nameColorStyle(entry)}>{displayName(entry)}</span>
                  <div className="flex items-center gap-2 text-[10px] font-mono text-dark-500 mt-0.5">
                    <span>{t('lb.posts_count', { n: entry.post_count || 0 })}</span>
                    <span className="text-dark-600">·</span>
                    <span>{t('lb.threads_count', { n: entry.thread_count || 0 })}</span>
                    <span className="text-dark-600">·</span>
                    <span className="text-neon-400/70">{t('lb.rep_count', { n: entry.rep_received || 0 })}</span>
                  </div>
                </div>

                <div className="text-right flex-shrink-0">
                  <span className={`font-bold font-mono text-sm ${isTop3 ? tc.text : 'text-dark-200'}`}>
                    {(entry.value || 0).toLocaleString()}
                  </span>
                  <span className="block text-[10px] font-mono text-dark-500">{t('lb.pts')}</span>
                  {isTop3 && rank <= XP_REWARDS.length && (
                    <span className={`text-[9px] font-mono ${tc.text}`}>+{XP_REWARDS[rank - 1]} XP</span>
                  )}
                </div>
              </Link>
            )
          })}
        </div>
      )}

      {hasMore && !loading && (
        <Button
          variant="secondary"
          size="sm"
          onClick={handleLoadMore}
          disabled={loadingMore}
          className="w-full"
        >
          {loadingMore ? t('lb.loading_btn') : t('lb.load_more')}
        </Button>
      )}

      {!hasMore && entries.length > 0 && !loading && (
        <p className="text-center font-mono text-dark-600 text-xs py-2">{t('lb.end')}</p>
      )}
    </div>
  )
}
