import { useState, useEffect } from 'react'
import { Link, useParams, useNavigate } from 'react-router-dom'
import api from '../lib/api'
import { useAuthStore } from '../store/authStore'
import { useToast } from '../components/Toast'
import { globalConfirm } from '../components/ConfirmModal'
import { timeAgo, formatDate, displayName, realName, telegramHandle } from '../lib/utils'
import { Card, Button, Tag, RoleBadge, StatTile, EmptyState, Modal, tabClass } from '../components/ui'
import { useT } from '../lib/i18n'
import { roleStyle } from '../components/admin/ui'
import Spinner from '../components/Spinner'
import { MessageSquare, Calendar, ThumbsUp, ThumbsDown, Users, Clock, Award, Plus, Minus, Star, Settings, Ban, MicOff, ShieldAlert, LogOut, Pencil, Flag } from 'lucide-react'
import BadgeIcon from '../components/BadgeIcon'
import UserListModal from '../components/UserListModal'
import ReportModal from '../components/ReportModal'

const MUTE_PRESETS = [
  { labelKey: 'profile.mute_1h', minutes: 60 },
  { labelKey: 'profile.mute_6h', minutes: 360 },
  { labelKey: 'profile.mute_1d', minutes: 1440 },
  { labelKey: 'profile.mute_7d', minutes: 10080 },
  { labelKey: 'profile.mute_permanent', minutes: null },
]

export default function Profile() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { user: currentUser, isAdmin, isModerator, setUser } = useAuthStore()
  const { showToast } = useToast()
  const t = useT()
  
  const [profile, setProfile] = useState(null)
  const [threads, setThreads] = useState([])
  const [posts, setPosts] = useState([])
  const [threadsPage, setThreadsPage] = useState(1)
  const [postsPage, setPostsPage] = useState(1)
  const [threadsHasMore, setThreadsHasMore] = useState(false)
  const [postsHasMore, setPostsHasMore] = useState(false)
  const [contentLoadingMore, setContentLoadingMore] = useState(false)
  const [repHistory, setRepHistory] = useState(null)
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState('threads')
  const [following, setFollowing] = useState(false)
  const [followTab, setFollowTab] = useState(null) // null | 'followers' | 'following'
  const [showRepModal, setShowRepModal] = useState(false)
  const [showReportModal, setShowReportModal] = useState(false)
  const [repPositive, setRepPositive] = useState(true)
  const [repComment, setRepComment] = useState('')
  const [repSubmitting, setRepSubmitting] = useState(false)
  const [xpInfo, setXpInfo] = useState(null)
  const [modAction, setModAction] = useState(null) // 'ban' | 'mute' | 'warn'
  const [modReason, setModReason] = useState('')
  const [modBusy, setModBusy] = useState(false)
  const [showEdit, setShowEdit] = useState(false)
  const [editForm, setEditForm] = useState({ profile_bio: '', signature: '' })
  const [editTheme, setEditTheme] = useState({ name_color: '', avatar_border: '', avatar_glow: false })
  const [savingEdit, setSavingEdit] = useState(false)

  const openEdit = () => {
    setEditForm({ profile_bio: currentUser?.profile_bio || '', signature: currentUser?.signature || '' })
    let th = {}
    try { th = currentUser?.profile_theme ? JSON.parse(currentUser.profile_theme) : {} } catch { th = {} }
    setEditTheme({ name_color: th.name_color || '', avatar_border: th.avatar_border || '', avatar_glow: !!th.avatar_glow })
    setShowEdit(true)
  }

  const handleSaveEdit = async () => {
    setSavingEdit(true)
    try {
      const payload = { profile_bio: editForm.profile_bio, signature: editForm.signature }
      if (currentUser?.is_premium) {
        payload.profile_theme = JSON.stringify({
          name_color: editTheme.name_color || undefined,
          avatar_border: editTheme.avatar_border || undefined,
          avatar_glow: !!editTheme.avatar_glow,
        })
      }
      const { data } = await api.put('/api/auth/profile', payload)
      setUser(data)
      setShowEdit(false)
      loadProfile()
      showToast(t('profile.updated'), 'success')
    } catch (err) {
      showToast(err.response?.data?.detail || t('profile.update_failed'), 'error')
    } finally {
      setSavingEdit(false)
    }
  }

  useEffect(() => {
    loadProfile()
  }, [id])

  useEffect(() => {
    if (profile && currentUser?.id === profile.id) {
      api.get('/api/users/me/xp').then(({ data }) => setXpInfo(data)).catch(() => {})
    }
  }, [profile, currentUser])

  const loadProfile = async () => {
    try {
      setLoading(true)
      const [profileRes, threadsRes, postsRes] = await Promise.all([
        api.get(`/api/users/${id}`),
        api.get(`/api/users/${id}/threads`, { params: { page: 1, per_page: 20 } }),
        api.get(`/api/users/${id}/posts`, { params: { page: 1, per_page: 20 } })
      ])
      setProfile(profileRes.data)
      setThreads(threadsRes.data)
      setPosts(postsRes.data)
      // Bare-array endpoints have no total; infer "more" from a full page.
      setThreadsPage(1); setThreadsHasMore((threadsRes.data || []).length === 20)
      setPostsPage(1); setPostsHasMore((postsRes.data || []).length === 20)
      setFollowing(profileRes.data.is_following || false)
    } catch (err) {
      if (import.meta.env.DEV) console.error('Failed to load profile:', err)
    } finally {
      setLoading(false)
    }
  }

  const loadMoreContent = async (kind) => {
    setContentLoadingMore(true)
    try {
      if (kind === 'threads') {
        const next = threadsPage + 1
        const { data } = await api.get(`/api/users/${id}/threads`, { params: { page: next, per_page: 20 } })
        setThreads(prev => [...prev, ...(data || [])])
        setThreadsPage(next)
        setThreadsHasMore((data || []).length === 20)
      } else {
        const next = postsPage + 1
        const { data } = await api.get(`/api/users/${id}/posts`, { params: { page: next, per_page: 20 } })
        setPosts(prev => [...prev, ...(data || [])])
        setPostsPage(next)
        setPostsHasMore((data || []).length === 20)
      }
    } catch { /* keep current list */ } finally { setContentLoadingMore(false) }
  }

  const handleFollow = async () => {
    try {
      if (following) {
        await api.delete(`/api/users/${id}/follow`)
        setFollowing(false)
        setProfile(p => ({ ...p, follower_count: (p.follower_count || 1) - 1 }))
      } else {
        await api.post(`/api/users/${id}/follow`)
        setFollowing(true)
        setProfile(p => ({ ...p, follower_count: (p.follower_count || 0) + 1 }))
      }
    } catch (err) {
      showToast(t('profile.action_failed'), 'error')
    }
  }

  const handleMessage = async () => {
    try {
      const { data } = await api.post('/api/dm/start', {
        user_id: Number(id),
        message: 'Hey!'
      })
      navigate(`/messages/${data.conversation_id}`)
    } catch (err) {
      showToast(err.response?.data?.detail || t('profile.dm_failed'), 'error')
    }
  }

  const loadRepHistory = async () => {
    try {
      const res = await api.get(`/api/reputation/users/${id}`)
      setRepHistory(res.data)
    } catch (err) {
      if (import.meta.env.DEV) console.error('Failed to load reputation:', err)
    }
  }

  const handleGiveRep = async () => {
    if (!repComment.trim()) {
      showToast(t('profile.comment_required'), 'error')
      return
    }
    try {
      setRepSubmitting(true)
      await api.post(`/api/reputation/users/${id}`, {
        is_positive: repPositive,
        comment: repComment.trim()
      })
      showToast(repPositive ? t('profile.rep_given_pos') : t('profile.rep_given_neg'), 'success')
      setShowRepModal(false)
      setRepComment('')
      loadProfile()
      if (tab === 'reputation') loadRepHistory()
    } catch (err) {
      const msg = err.response?.data?.detail || t('profile.rep_failed')
      showToast(msg, 'error')
    } finally {
      setRepSubmitting(false)
    }
  }

  const closeMod = () => { setModAction(null); setModReason('') }

  const submitBan = async () => {
    if (!modReason.trim()) { showToast(t('profile.reason_required'), 'error'); return }
    try {
      setModBusy(true)
      await api.post(`/api/admin/users/${id}/ban`, null, { params: { reason: modReason.trim() } })
      showToast(t('profile.user_banned'), 'success'); closeMod(); loadProfile()
    } catch (err) { showToast(err.response?.data?.detail || t('profile.failed'), 'error') } finally { setModBusy(false) }
  }

  const handleUnban = async () => {
    if (!(await globalConfirm(t('profile.confirm_unban')))) return
    try {
      await api.post(`/api/admin/users/${id}/unban`)
      showToast(t('profile.user_unbanned'), 'success'); loadProfile()
    } catch (err) { showToast(err.response?.data?.detail || t('profile.failed'), 'error') }
  }

  const submitMute = async (minutes) => {
    if (!modReason.trim()) { showToast(t('profile.reason_required'), 'error'); return }
    try {
      setModBusy(true)
      await api.post(`/api/mod/mute/${id}`, null, {
        params: { reason: modReason.trim(), ...(minutes ? { duration_minutes: minutes } : {}) }
      })
      showToast(t('profile.user_muted'), 'success'); closeMod(); loadProfile()
    } catch (err) { showToast(err.response?.data?.detail || t('profile.failed'), 'error') } finally { setModBusy(false) }
  }

  const handleUnmute = async () => {
    if (!(await globalConfirm(t('profile.confirm_unmute')))) return
    try {
      await api.post(`/api/mod/unmute/${id}`)
      showToast(t('profile.user_unmuted'), 'success'); loadProfile()
    } catch (err) { showToast(err.response?.data?.detail || t('profile.failed'), 'error') }
  }

  const submitWarn = async () => {
    if (!modReason.trim()) { showToast(t('profile.reason_required'), 'error'); return }
    try {
      setModBusy(true)
      await api.post(`/api/mod/warn/${id}`, null, { params: { reason: modReason.trim() } })
      showToast(t('profile.user_warned'), 'success'); closeMod()
    } catch (err) { showToast(err.response?.data?.detail || t('profile.failed'), 'error') } finally { setModBusy(false) }
  }

  const handleForceLogout = async () => {
    if (!(await globalConfirm(t('profile.confirm_force_logout')))) return
    try {
      await api.post(`/api/admin/users/${id}/force-logout`)
      showToast(t('profile.user_logged_out'), 'success')
    } catch (err) { showToast(err.response?.data?.detail || t('profile.failed'), 'error') }
  }

  if (loading) {
    return <Spinner className="min-h-[60vh]" />
  }

  if (!profile) {
    return (
      <Card className="p-8 text-center">
        <EmptyState>{t('profile.user_not_found')}</EmptyState>
      </Card>
    )
  }

  const isOwnProfile = currentUser?.id === profile.id
  const reputation = (profile.rep_positive || 0) - (profile.rep_negative || 0)

  // Premium name color / avatar border to render on the header.
  const profileTheme = (() => {
    try {
      return profile.profile_theme
        ? (typeof profile.profile_theme === 'string' ? JSON.parse(profile.profile_theme) : profile.profile_theme)
        : null
    } catch { return null }
  })()
  const themeBorder = profileTheme?.avatar_border || null
  const avatarThemeStyle = themeBorder
    ? { boxShadow: [`0 0 0 2px ${themeBorder}`, profileTheme.avatar_glow ? `0 0 16px ${themeBorder}` : ''].filter(Boolean).join(', ') }
    : undefined

  // Moderation visibility — mirror backend staff-protection rules so no dead buttons appear.
  const targetRole = String(profile.role || '').toLowerCase().replace('userrole.', '')
  const viewerIsAdmin = isAdmin?.() || false
  const viewerIsMod = isModerator?.() || false
  const targetIsAdmin = targetRole === 'admin'
  const targetIsMod = targetRole === 'moderator'
  const canModerate = !isOwnProfile && !!currentUser && viewerIsMod && !targetIsAdmin && (viewerIsAdmin || !targetIsMod)

  return (
    <div className="space-y-4">
      {/* Profile Banner */}
      {profile.profile_banner_url && (
        <div className="relative h-32 rounded-xl overflow-hidden border border-primary-500/15">
          <img src={profile.profile_banner_url} alt="" className="w-full h-full object-cover" />
          <div className="pointer-events-none absolute inset-0 bg-gradient-to-t from-dark-950/60 to-transparent" />
        </div>
      )}

      {/* Profile Header */}
      <Card className="overflow-visible p-6">
          <div className="flex items-start gap-4">
            {/* Avatar — overlaps banner */}
            <div
              className={`w-20 h-20 rounded-xl bg-dark-800 flex items-center justify-center overflow-hidden flex-shrink-0 ring-4 ring-primary-500/20 border border-dark-950 avatar-glow ${profile.profile_banner_url ? '-mt-12' : ''}`}
              style={avatarThemeStyle}
            >
              {profile.avatar_url ? (
                <img src={profile.avatar_url} alt="" className="w-full h-full object-cover" />
              ) : (
                <span className="text-2xl font-bold text-primary-400">
                  {realName(profile)[0] || '?'}
                </span>
              )}
            </div>

            {/* Info */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <h1
                  className={`font-display text-xl font-bold ${profileTheme?.name_color ? '' : roleStyle(profile.role).text}`}
                  style={profileTheme?.name_color ? { color: profileTheme.name_color } : undefined}
                >
                  {profile.first_name || profile.username || t('profile.user_fallback')}
                </h1>
                {telegramHandle(profile) && (
                  <span className="text-sm font-mono text-primary-400/70">{telegramHandle(profile)}</span>
                )}
                {profile.custom_title && (
                  <Tag tone="cyan">{profile.custom_title}</Tag>
                )}
                {profile.role && profile.role !== 'user' && (
                  <RoleBadge role={profile.role} />
                )}
              </div>

              {profile.profile_bio && (
                <p className="text-dark-300 mt-2 text-sm">{profile.profile_bio}</p>
              )}

              {/* Online Status */}
              <div className="flex items-center gap-2 mt-2 text-xs text-dark-400 font-mono">
                <Clock size={12} />
                <span>{t('profile.last_seen', { time: timeAgo(profile.last_seen_at || profile.created_at) })}</span>
                <span>•</span>
                <Calendar size={12} />
                <span>{t('profile.joined', { date: formatDate(profile.created_at) })}</span>
              </div>
            </div>
          </div>

          {/* Stats Grid */}
          <div className="grid grid-cols-3 sm:grid-cols-6 gap-3 mt-4 pt-4 border-t border-primary-500/10">
            <StatTile label={t('profile.stat_threads')} value={profile.thread_count || 0} />
            <StatTile label={t('profile.stat_posts')} value={profile.post_count || 0} />
            <StatTile
              label={t('profile.stat_reputation')}
              value={`${reputation > 0 ? '+' : ''}${reputation}`}
              accent={reputation > 0 ? 'green' : reputation < 0 ? 'red' : 'default'}
            />
            <StatTile label={t('profile.stat_followers')} value={profile.follower_count || 0} onClick={() => setFollowTab('followers')} />
            <StatTile label={t('profile.stat_level')} value={profile.level || 1} accent="cyan" />
            <StatTile label={t('profile.stat_streak')} value={profile.login_streak || 0} accent="amber" />
          </div>

          {/* XP Progress Bar - own profile only */}
          {isOwnProfile && xpInfo && (
            <div className="mt-3">
              <div className="h-1.5 bg-dark-800 rounded-full overflow-hidden border border-primary-500/15">
                <div
                  className="h-full bg-gradient-to-r from-primary-400 to-neon-400 rounded-full transition-all duration-500"
                  style={{
                    width: `${xpInfo.xp_to_next_level > xpInfo.xp_for_current_level
                      ? ((xpInfo.xp - xpInfo.xp_for_current_level) / (xpInfo.xp_to_next_level - xpInfo.xp_for_current_level)) * 100
                      : 0}%`
                  }}
                />
              </div>
              <p className="text-[10px] text-dark-400 mt-0.5 text-center font-mono">
                {xpInfo.xp} / {xpInfo.xp_to_next_level} XP
              </p>
            </div>
          )}

          {/* Referral Earnings — own profile only */}
          {isOwnProfile && (profile.referral_earnings || 0) > 0 && (
            <Card className="!p-3 mt-3 !bg-amber-500/5 !border-amber-500/20 flex items-center gap-3">
              <div className="w-9 h-9 rounded-lg bg-amber-500/20 flex items-center justify-center flex-shrink-0">
                <Users size={17} className="text-amber-400" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-xs text-dark-400">{t('profile.referral_earnings')}</div>
                <div className="text-sm font-bold text-amber-400 font-mono">${(profile.referral_earnings || 0).toFixed(2)}</div>
              </div>
            </Card>
          )}

          {/* Actions */}
          {!isOwnProfile && currentUser && (
            <div className="flex gap-3 mt-4 pt-4 border-t border-primary-500/10">
              <Button
                variant={following ? 'primary' : 'secondary'}
                icon={Users}
                onClick={handleFollow}
                className="flex-1"
              >
                {following ? t('profile.following') : t('profile.follow')}
              </Button>
              <Button
                variant="secondary"
                icon={MessageSquare}
                onClick={handleMessage}
                className="flex-1"
              >
                {t('profile.message')}
              </Button>
              <Button
                variant="neon"
                icon={Star}
                onClick={() => setShowRepModal(true)}
                title={t('profile.give_rep_title')}
              >
                {t('profile.rep')}
              </Button>
              <Button
                variant="ghost"
                icon={Flag}
                onClick={() => setShowReportModal(true)}
                title={t('profile.report_user_title')}
                className="!px-3"
              />
            </div>
          )}
          <ReportModal
            open={showReportModal}
            onClose={() => setShowReportModal(false)}
            reportType="user"
            targetId={profile.id}
            targetLabel={t('profile.report_target', { username: displayName(profile, false) })}
          />

          {/* Staff moderation actions */}
          {canModerate && (
            <div className="mt-4 pt-4 border-t border-red-500/15">
              <p className="text-[10px] uppercase tracking-widest text-dark-500 font-mono mb-2">{t('profile.staff_actions')}</p>
              <div className="flex flex-wrap gap-2">
                {viewerIsAdmin && (
                  profile.is_banned ? (
                    <Button variant="secondary" icon={Ban} onClick={handleUnban}>{t('profile.unban')}</Button>
                  ) : (
                    <Button variant="danger" icon={Ban} onClick={() => { setModReason(''); setModAction('ban') }}>{t('profile.ban')}</Button>
                  )
                )}
                {profile.is_muted ? (
                  <Button variant="secondary" icon={MicOff} onClick={handleUnmute}>{t('profile.unmute')}</Button>
                ) : (
                  <Button variant="warn" icon={MicOff} onClick={() => { setModReason(''); setModAction('mute') }}>{t('profile.mute')}</Button>
                )}
                <Button variant="warn" icon={ShieldAlert} onClick={() => { setModReason(''); setModAction('warn') }}>{t('profile.warn')}</Button>
                {viewerIsAdmin && (
                  <Button variant="danger" icon={LogOut} onClick={handleForceLogout}>{t('profile.force_logout')}</Button>
                )}
              </div>
            </div>
          )}


          {isOwnProfile && (
            <div className="mt-4 pt-4 border-t border-primary-500/10 flex items-center gap-3 flex-wrap">
              <Button variant="primary" size="sm" icon={Pencil} onClick={openEdit}>
                {t('profile.edit_profile')}
              </Button>
              <Link
                to="/settings"
                className="inline-flex items-center gap-2 text-sm text-primary-400 hover:underline font-mono"
              >
                <Settings size={16} />
                {t('profile.more_settings')}
              </Link>
            </div>
          )}
      </Card>

      {/* Badges */}
      {profile.badges?.length > 0 && (
        <Card>
          <div className="flex items-center gap-2 mb-3">
            <Award size={16} className="text-primary-400" />
            <h2 className="font-mono text-sm font-bold uppercase tracking-widest text-primary-300">{t('profile.badges')}</h2>
          </div>
          <div className="flex flex-wrap gap-2">
            {profile.badges.map(ub => (
              <div key={ub.id} className="relative group">
                <div
                  className={`w-10 h-10 rounded-xl flex items-center justify-center transition-all duration-200 cursor-default
                    ${ub.is_primary
                      ? 'ring-2 ring-primary-400/60 ring-offset-1 ring-offset-dark-800 bg-primary-500/15'
                      : 'bg-dark-700/60 hover:bg-dark-600/80'
                    }`}
                  style={{ borderColor: ub.badge?.color || '#6366f1', borderWidth: ub.is_primary ? '1px' : '0' }}
                >
                  {ub.badge?.icon_url ? (
                    <img src={ub.badge.icon_url} alt="" className="w-6 h-6 object-contain" />
                  ) : (
                    <BadgeIcon icon={ub.badge?.icon} iconStyle={ub.badge?.icon_style} color={ub.badge?.color} size={16} />
                  )}
                </div>
                {ub.quantity > 1 && (
                  <span className="absolute -bottom-1 -right-1 min-w-[16px] h-[16px] px-1 rounded-full bg-dark-900 border border-primary-500/40 text-[9px] font-mono font-bold text-primary-300 flex items-center justify-center">
                    ×{ub.quantity}
                  </span>
                )}
                {/* Tooltip */}
                <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-1.5 bg-dark-900 border border-dark-600 rounded-lg shadow-xl opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-150 whitespace-nowrap z-50 pointer-events-none">
                  <p className="text-xs font-semibold text-dark-100">{ub.badge?.name}</p>
                  {ub.badge?.description && (
                    <p className="text-[10px] text-dark-400 mt-0.5">{ub.badge.description}</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Tabs — sticky */}
      <div className="sticky top-16 z-20 -mx-1 px-1 py-1 bg-dark-950/80 backdrop-blur-sm rounded-xl">
        <div className="flex gap-1 bg-dark-900/80 rounded-xl p-1 border border-primary-500/15">
          <button onClick={() => setTab('threads')} className={`flex-1 ${tabClass(tab === 'threads')}`}>
            {t('profile.tab_threads', { n: threads.length })}
          </button>
          <button onClick={() => setTab('posts')} className={`flex-1 ${tabClass(tab === 'posts')}`}>
            {t('profile.tab_posts', { n: posts.length })}
          </button>
          <button
            onClick={() => { setTab('reputation'); if (!repHistory) loadRepHistory() }}
            className={`flex-1 ${tabClass(tab === 'reputation')}`}
          >
            {t('profile.tab_reputation')}
          </button>
        </div>
      </div>

      {/* Content */}
      {tab === 'threads' && (
        <div className="space-y-2">
          {threads.length === 0 ? (
            <Card><EmptyState icon={MessageSquare}>{t('profile.no_threads')}</EmptyState></Card>
          ) : (
            threads.map(thread => (
              <Card key={thread.id} as={Link} to={`/thread/${thread.slug}`} className="block">
                <h3 className="font-semibold text-white">{thread.title}</h3>
                <div className="flex items-center gap-3 text-sm text-dark-400 mt-1 font-mono">
                  <span>{timeAgo(thread.created_at)}</span>
                  <span>•</span>
                  <span>{t('profile.replies_count', { n: thread.reply_count || 0 })}</span>
                  <span>•</span>
                  <span>{t('profile.views_count', { n: thread.view_count || 0 })}</span>
                </div>
              </Card>
            ))
          )}
          {threadsHasMore && (
            <Button variant="secondary" className="w-full" disabled={contentLoadingMore} onClick={() => loadMoreContent('threads')}>
              {contentLoadingMore ? '…' : t('common.load_more')}
            </Button>
          )}
        </div>
      )}

      {tab === 'posts' && (
        <div className="space-y-2">
          {posts.length === 0 ? (
            <Card><EmptyState icon={MessageSquare}>{t('profile.no_posts')}</EmptyState></Card>
          ) : (
            posts.map(post => (
              <Card key={post.id} as={Link} to={`/thread/${post.thread_slug}`} className="block">
                {post.thread_title && (
                  <div className="text-xs text-primary-400 mb-1 font-mono">{t('profile.in_thread', { title: post.thread_title })}</div>
                )}
                <p className="text-dark-300 text-sm">{post.content}</p>
                <div className="flex items-center gap-3 text-xs text-dark-400 mt-2 font-mono">
                  <span>{timeAgo(post.created_at)}</span>
                  {post.like_count > 0 && (
                    <>
                      <span>•</span>
                      <span className="flex items-center gap-1">
                        <ThumbsUp size={10} /> {post.like_count}
                      </span>
                    </>
                  )}
                </div>
              </Card>
            ))
          )}
          {postsHasMore && (
            <Button variant="secondary" className="w-full" disabled={contentLoadingMore} onClick={() => loadMoreContent('posts')}>
              {contentLoadingMore ? '…' : t('common.load_more')}
            </Button>
          )}
        </div>
      )}

      {tab === 'reputation' && (
        <div className="space-y-2">
          {repHistory ? (
            <>
              {/* Summary */}
              <Card className="flex items-center justify-center gap-6">
                <div className="flex items-center gap-2 text-neon-400">
                  <ThumbsUp size={16} /> <span className="font-bold text-lg font-mono">+{repHistory.total_positive || 0}</span>
                </div>
                <div className="flex items-center gap-2 text-red-400">
                  <ThumbsDown size={16} /> <span className="font-bold text-lg font-mono">-{repHistory.total_negative || 0}</span>
                </div>
              </Card>

              {/* Entries */}
              {(!repHistory.entries || repHistory.entries.length === 0) ? (
                <Card><EmptyState icon={Star}>{t('profile.no_reputation')}</EmptyState></Card>
              ) : (
                repHistory.entries.map(entry => (
                  <Card key={entry.id} className="flex items-start gap-3">
                    <div className={`mt-0.5 w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
                      entry.is_positive ? 'bg-neon-500/20' : 'bg-red-500/20'
                    }`}>
                      {entry.is_positive ? <Plus size={14} className="text-neon-400" /> : <Minus size={14} className="text-red-400" />}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 text-sm">
                        <Link
                          to={`/profile/${entry.from_user?.id}`}
                          className="font-semibold text-white hover:text-primary-400"
                        >
                          {entry.from_user ? displayName(entry.from_user) : t('profile.unknown')}
                        </Link>
                        <span className="text-dark-400 text-xs font-mono">{timeAgo(entry.created_at)}</span>
                      </div>
                      {entry.comment && (
                        <p className="text-dark-300 text-sm mt-1">{entry.comment}</p>
                      )}
                    </div>
                  </Card>
                ))
              )}
            </>
          ) : (
            <Spinner size="sm" className="py-8" />
          )}
        </div>
      )}

      {/* Followers / Following list */}
      <UserListModal
        open={!!followTab}
        onClose={() => setFollowTab(null)}
        url={followTab ? `/api/users/${id}/${followTab}` : null}
        title={
          <div className="flex gap-1.5 normal-case">
            {['followers', 'following'].map((ft) => (
              <button
                key={ft}
                onClick={() => setFollowTab(ft)}
                className={`rounded px-2.5 py-1 text-xs font-semibold capitalize transition-colors ${
                  followTab === ft
                    ? 'bg-primary-500/20 text-primary-200 border border-primary-500/40'
                    : 'text-dark-400 border border-transparent hover:text-dark-200'
                }`}
              >
                {ft === 'followers' ? t('profile.followers_tab') : t('profile.following_tab')} {ft === 'followers' ? (profile.follower_count || 0) : (profile.following_count || 0)}
              </button>
            ))}
          </div>
        }
      />

      {/* Rep Modal */}
      <Modal open={showRepModal} onClose={() => setShowRepModal(false)} title={t('profile.give_reputation')} maxWidth="max-w-md">
        <div className="space-y-4">
          <div className="flex gap-2">
            <button
              onClick={() => setRepPositive(true)}
              className={`flex-1 py-3 rounded-xl font-semibold flex items-center justify-center gap-2 transition-colors ${
                repPositive ? 'bg-neon-500/20 text-neon-400 ring-1 ring-neon-500/50' : 'bg-dark-800 text-dark-400'
              }`}
            >
              <ThumbsUp size={16} /> {t('profile.rep_plus')}
            </button>
            <button
              onClick={() => setRepPositive(false)}
              className={`flex-1 py-3 rounded-xl font-semibold flex items-center justify-center gap-2 transition-colors ${
                !repPositive ? 'bg-red-500/20 text-red-400 ring-1 ring-red-500/50' : 'bg-dark-800 text-dark-400'
              }`}
            >
              <ThumbsDown size={16} /> {t('profile.rep_minus')}
            </button>
          </div>

          <textarea
            value={repComment}
            onChange={e => setRepComment(e.target.value)}
            placeholder={t('profile.rep_comment_placeholder')}
            rows={3}
            className="w-full bg-dark-950/60 border border-primary-500/15 rounded-lg px-4 py-3 text-sm text-white font-mono placeholder:text-dark-500 focus:outline-none focus:border-primary-500/50 resize-none"
          />

          <Button
            variant="primary"
            onClick={handleGiveRep}
            disabled={repSubmitting || !repComment.trim()}
            className="w-full"
          >
            {repSubmitting ? t('profile.submitting') : t('profile.give_reputation_btn')}
          </Button>
        </div>
      </Modal>

      {/* Moderation Modal (ban / mute / warn) */}
      <Modal
        open={modAction !== null}
        onClose={closeMod}
        title={modAction === 'ban' ? t('profile.ban_user_title') : modAction === 'mute' ? t('profile.mute_user_title') : t('profile.warn_user_title')}
        maxWidth="max-w-md"
      >
        <div className="space-y-4">
          <textarea
            value={modReason}
            onChange={e => setModReason(e.target.value)}
            placeholder={t('profile.mod_reason_placeholder', { action: t(`profile.action_${modAction || 'warn'}`) })}
            rows={3}
            className="w-full bg-dark-950/60 border border-primary-500/15 rounded-lg px-4 py-3 text-sm text-white font-mono placeholder:text-dark-500 focus:outline-none focus:border-primary-500/50 resize-none"
          />

          {modAction === 'mute' ? (
            <div>
              <p className="text-[10px] uppercase tracking-widest text-dark-500 font-mono mb-2">{t('profile.duration')}</p>
              <div className="flex flex-wrap gap-2">
                {MUTE_PRESETS.map(p => (
                  <Button
                    key={p.labelKey}
                    variant={p.minutes === null ? 'danger' : 'warn'}
                    disabled={modBusy || !modReason.trim()}
                    onClick={() => submitMute(p.minutes)}
                  >{t(p.labelKey)}</Button>
                ))}
              </div>
            </div>
          ) : (
            <Button
              variant={modAction === 'ban' ? 'danger' : 'warn'}
              onClick={modAction === 'ban' ? submitBan : submitWarn}
              disabled={modBusy || !modReason.trim()}
              className="w-full"
            >
              {modBusy ? t('profile.submitting') : modAction === 'ban' ? t('profile.ban_user_btn') : t('profile.warn_user_btn')}
            </Button>
          )}
        </div>
      </Modal>

      {/* Edit own profile (bio, signature + premium appearance) */}
      <Modal open={showEdit} onClose={() => setShowEdit(false)} title={t('profile.edit_title')} maxWidth="max-w-md">
        <div className="space-y-4">
          <div>
            <label className="mb-1 block font-mono text-[10px] uppercase tracking-widest text-primary-400/70">{t('profile.bio')}</label>
            <textarea
              value={editForm.profile_bio}
              onChange={e => setEditForm(f => ({ ...f, profile_bio: e.target.value }))}
              rows={3} maxLength={2000}
              placeholder={t('profile.bio_placeholder')}
              className="w-full bg-dark-950/60 border border-primary-500/15 rounded-lg px-4 py-3 text-sm text-white placeholder:text-dark-500 focus:outline-none focus:border-primary-500/50 resize-none"
            />
          </div>
          <div>
            <label className="mb-1 block font-mono text-[10px] uppercase tracking-widest text-primary-400/70">{t('profile.signature')}</label>
            <textarea
              value={editForm.signature}
              onChange={e => setEditForm(f => ({ ...f, signature: e.target.value }))}
              rows={2} maxLength={500}
              placeholder={currentUser?.is_premium ? t('profile.sig_placeholder_premium') : t('profile.sig_placeholder')}
              className="w-full bg-dark-950/60 border border-primary-500/15 rounded-lg px-4 py-3 text-sm text-white placeholder:text-dark-500 focus:outline-none focus:border-primary-500/50 resize-none"
            />
          </div>

          {currentUser?.is_premium ? (
            <div className="rounded-xl border border-amber-500/25 bg-amber-500/5 p-4 space-y-3">
              <div className="flex items-center gap-2">
                <Star size={14} className="text-amber-400" />
                <h3 className="font-semibold text-amber-200 text-sm">{t('profile.premium_appearance')}</h3>
              </div>
              <div>
                <label className="mb-1 block font-mono text-[10px] uppercase tracking-widest text-primary-400/70">{t('profile.name_color')}</label>
                <div className="flex items-center gap-2">
                  <input type="color" value={editTheme.name_color || '#ffffff'} onChange={e => setEditTheme(t => ({ ...t, name_color: e.target.value }))} className="w-10 h-10 rounded-lg border border-dark-700 cursor-pointer bg-transparent" />
                  <input type="text" value={editTheme.name_color} onChange={e => setEditTheme(t => ({ ...t, name_color: e.target.value }))} placeholder={t('profile.color_placeholder_default')} className="flex-1 bg-dark-950/60 border border-primary-500/15 rounded-lg px-3 py-2 text-sm text-white" />
                </div>
              </div>
              <div>
                <label className="mb-1 block font-mono text-[10px] uppercase tracking-widest text-primary-400/70">{t('profile.avatar_border')}</label>
                <div className="flex items-center gap-2">
                  <input type="color" value={editTheme.avatar_border || '#00c8e6'} onChange={e => setEditTheme(t => ({ ...t, avatar_border: e.target.value }))} className="w-10 h-10 rounded-lg border border-dark-700 cursor-pointer bg-transparent" />
                  <input type="text" value={editTheme.avatar_border} onChange={e => setEditTheme(t => ({ ...t, avatar_border: e.target.value }))} placeholder={t('profile.color_placeholder_none')} className="flex-1 bg-dark-950/60 border border-primary-500/15 rounded-lg px-3 py-2 text-sm text-white" />
                </div>
              </div>
              <label className="flex items-center gap-2 text-sm text-dark-200 cursor-pointer">
                <input type="checkbox" checked={editTheme.avatar_glow} onChange={e => setEditTheme(t => ({ ...t, avatar_glow: e.target.checked }))} />
                {t('profile.avatar_glow')}
              </label>
              <div className="flex items-center gap-3 pt-1">
                <div className="w-12 h-12 rounded-xl bg-dark-700 flex items-center justify-center font-bold"
                  style={editTheme.avatar_border ? { boxShadow: [`0 0 0 2px ${editTheme.avatar_border}`, editTheme.avatar_glow ? `0 0 14px ${editTheme.avatar_border}` : ''].filter(Boolean).join(', ') } : undefined}>
                  <span className={editTheme.name_color ? '' : roleStyle(currentUser?.role).text} style={editTheme.name_color ? { color: editTheme.name_color } : undefined}>{(currentUser?.username || 'U')[0]?.toUpperCase()}</span>
                </div>
                <span className={`font-semibold ${editTheme.name_color ? '' : roleStyle(currentUser?.role).text}`} style={editTheme.name_color ? { color: editTheme.name_color } : undefined}>{currentUser?.username || 'username'}</span>
              </div>
            </div>
          ) : (
            <Link to="/shop" onClick={() => setShowEdit(false)} className="block text-xs text-amber-300/90 hover:underline">
              {t('profile.get_premium_link')}
            </Link>
          )}

          <div className="flex gap-2 pt-1">
            <Button variant="ghost" className="flex-1" onClick={() => setShowEdit(false)}>{t('common.cancel')}</Button>
            <Button variant="primary" className="flex-1" onClick={handleSaveEdit} disabled={savingEdit}>
              {savingEdit ? t('common.saving') : t('common.save')}
            </Button>
          </div>
          <p className="text-[10px] text-dark-500 text-center">
            {t('profile.edit_footer')} <Link to="/settings" className="text-primary-400 hover:underline" onClick={() => setShowEdit(false)}>{t('profile.edit_footer_settings')}</Link>.
          </p>
        </div>
      </Modal>
    </div>
  )
}
