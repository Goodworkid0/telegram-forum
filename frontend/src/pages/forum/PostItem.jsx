import { useState, useRef, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Star, Heart, Reply, Check, Edit3, Trash2, MessageSquare, User, Flag } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import api from '../../lib/api'
import { useToast } from '../../components/Toast'
import RoleBadge from '../../components/RoleBadge'
import BadgeIcon from '../../components/BadgeIcon'
import { timeAgo, formatDate, parseDate, displayName, realName, telegramHandle, nameColorStyle } from '../../lib/utils'
import { roleStyle } from '../../components/admin/ui'
import UserPanel from './UserPanel'
import MarkdownContent from './MarkdownContent'
import ReportModal from '../../components/ReportModal'
import { Tag } from '../../components/ui'
import { useT, getDateLocale } from '../../lib/i18n'

export default function PostItem({ post, postNumber, isLocked, user, canPost, onLike, onQuote, onEdit, onDelete, onRep, onShowLikes }) {
  const t = useT()
  const [showMobilePopup, setShowMobilePopup] = useState(false)
  const [showReport, setShowReport] = useState(false)
  const mobilePopupRef = useRef(null)
  const navigate = useNavigate()
  const { showToast } = useToast()

  const isStaff = ['ADMIN', 'MODERATOR'].includes(String(user?.role || '').toUpperCase())
  const canEditThis = user && (post.author?.id === user.id || isStaff)
  const canDeleteThis = user && (post.author?.id === user.id || isStaff)
  const author = post.author
  const repTotal = (author?.rep_positive || 0) - (author?.rep_negative || 0)
  const joinDate = author?.created_at ? parseDate(author.created_at).toLocaleDateString(getDateLocale(), { month: 'short', year: 'numeric' }) : null
  const isOwnProfile = user?.id === author?.id

  useEffect(() => {
    if (!showMobilePopup) return
    const handler = (e) => { if (mobilePopupRef.current && !mobilePopupRef.current.contains(e.target)) setShowMobilePopup(false) }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [showMobilePopup])

  const handleMobileStartDM = async () => {
    try {
      const { data } = await api.post('/api/dm/start', { user_id: author.id, message: 'Hey!' })
      setShowMobilePopup(false)
      navigate(`/messages/${data.conversation_id}`)
    } catch (err) {
      showToast(err.response?.data?.detail || t('forum.failed_start_dm'), 'error')
    }
  }

  return (
    <div
      id={`post-${post.id}`}
      className="bg-dark-900/60 border border-primary-500/10 rounded-xl scroll-mt-20"
    >
      {/* Post header bar — always visible */}
      <div className="bg-dark-800/50 border-b border-primary-500/10 rounded-t-xl px-3 sm:px-5 py-2 flex items-center justify-between gap-2">
        {/* Mobile: 2-row user header with spanning avatar */}
        <div className="sm:hidden relative flex items-center gap-2.5 flex-1 min-w-0">
          <button onClick={() => setShowMobilePopup(!showMobilePopup)}
            className="w-9 h-9 rounded-full bg-dark-700 flex items-center justify-center overflow-hidden flex-shrink-0 ring-1 ring-dark-600 self-start mt-0.5"
            style={author?.profile_theme ? (() => {
              try {
                const t = typeof author.profile_theme === 'string' ? JSON.parse(author.profile_theme) : author.profile_theme
                const border = t.avatar_border || null
                const glow = t.avatar_glow && border ? `0 0 8px ${border}` : ''
                const ring = border ? `0 0 0 1px ${border}` : ''
                return { boxShadow: [ring, glow].filter(Boolean).join(', ') || undefined }
              } catch { return {} }
            })() : {}}>
            {author?.avatar_url ? <img src={author.avatar_url} alt="" className="w-full h-full object-cover" /> :
              <span className="text-[10px] font-bold text-dark-400">{(author ? realName(author) : '?')[0]?.toUpperCase()}</span>}
          </button>
          <div className="flex flex-col gap-1 min-w-0 flex-1">
            {/* Row 1: name + role + date */}
            <div className="flex items-center gap-1">
              <button onClick={() => setShowMobilePopup(!showMobilePopup)}
                className={`text-xs font-semibold truncate hover:underline ${roleStyle(author?.role).text}`}
                style={nameColorStyle(author)}>
                {realName(author)}
              </button>
              {telegramHandle(author) && (
                <span className="text-[10px] font-mono text-dark-500 truncate flex-shrink-0">{telegramHandle(author)}</span>
              )}
              <RoleBadge role={author?.role} />
              <span className="text-[10px] text-dark-500 ml-auto flex-shrink-0">{formatDate(post.created_at)}</span>
            </div>
            {/* Row 2: stats + post# + actions */}
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] text-dark-400">{author?.post_count || 0}<span className="text-dark-600"> {t('forum.posts_suffix')}</span></span>
              <span className="text-dark-600 text-[10px]">·</span>
              <span className={`text-[10px] ${repTotal > 0 ? 'text-green-400' : repTotal < 0 ? 'text-red-400' : 'text-dark-400'}`}>{repTotal > 0 ? '+' : ''}{repTotal}<span className="text-dark-600"> {t('forum.rep_suffix')}</span></span>
              <a href={`#post-${post.id}`} className="text-[10px] font-mono text-dark-600 hover:text-primary-400 ml-auto flex-shrink-0">#{postNumber}</a>
            </div>
            {/* Row 3: badges */}
            {post.author_badges?.length > 0 && (
              <div className="flex items-center gap-0.5">
                {post.author_badges.slice(0, 6).map((b, i) => (
                  <div key={i} className="w-5 h-5 rounded-md flex items-center justify-center bg-dark-700/60" title={b.badge_name}>
                    <BadgeIcon icon={b.badge_icon} iconStyle={b.badge_icon_style} color={b.badge_color} size={11} />
                  </div>
                ))}
                {post.author_badges.length > 6 && (
                  <span className="text-[9px] text-dark-500">+{post.author_badges.length - 6}</span>
                )}
              </div>
            )}
          </div>

          {/* Mobile: user options popup (mirrors desktop UserPanel) */}
          {showMobilePopup && (
            <div
              ref={mobilePopupRef}
              className="absolute top-12 left-0 z-30 bg-dark-800 border border-dark-600 rounded-xl shadow-xl py-1.5 min-w-[180px]"
            >
              <div className="px-3 py-1.5 text-[10px] text-dark-500 uppercase tracking-wider font-semibold border-b border-dark-700/50">
                {displayName(author, false)}
              </div>
              <Link
                to={`/profile/${author?.id}`}
                onClick={() => setShowMobilePopup(false)}
                className="flex items-center gap-2.5 w-full text-left px-3 py-2 text-xs text-dark-200 hover:text-white hover:bg-dark-700/50 transition-colors"
              >
                <User className="w-3.5 h-3.5 text-dark-400" />
                {t('forum.view_profile')}
              </Link>
              {!isOwnProfile && user && (
                <button
                  onClick={handleMobileStartDM}
                  className="flex items-center gap-2.5 w-full text-left px-3 py-2 text-xs text-dark-200 hover:text-white hover:bg-dark-700/50 transition-colors"
                >
                  <MessageSquare className="w-3.5 h-3.5 text-dark-400" />
                  {t('forum.send_message')}
                </button>
              )}
              {!isOwnProfile && user && onRep && (
                <button
                  onClick={() => { setShowMobilePopup(false); onRep(post) }}
                  className="flex items-center gap-2.5 w-full text-left px-3 py-2 text-xs text-dark-200 hover:text-white hover:bg-dark-700/50 transition-colors"
                >
                  <Star className="w-3.5 h-3.5 text-dark-400" />
                  {t('forum.give_reputation')}
                </button>
              )}
            </div>
          )}
        </div>

        {/* Desktop: date + badges */}
        <div className="hidden sm:flex items-center gap-2">
          <span className="text-xs text-dark-400">{formatDate(post.created_at)}</span>
          {post.is_best_answer && (
            <Tag tone="green" icon={Check}>{t('forum.best_answer')}</Tag>
          )}
          {post.is_edited && (
            <span className="text-[10px] text-dark-500">{t('forum.edited_ago', { time: timeAgo(post.edited_at) })}</span>
          )}
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          {/* Mobile: best answer badge */}
          {post.is_best_answer && (
            <Tag tone="green" icon={Check} className="sm:hidden">{t('forum.best')}</Tag>
          )}
          <a href={`#post-${post.id}`} className="hidden sm:inline text-[10px] text-dark-500 font-mono hover:text-primary-400 transition-colors">
            #{postNumber}
          </a>

        </div>
      </div>

      <div className="flex p-3 sm:p-4 gap-3 sm:gap-4">
        {/* Desktop sidebar — hidden on mobile */}
        <div className="hidden sm:block flex-shrink-0">
          <UserPanel author={author} currentUser={user} post={post} onRep={onRep} authorBadges={post.author_badges} />
        </div>

        <div className="flex-1 min-w-0 flex flex-col">
          {post.parent_id && (
            <a
              href={`#post-${post.parent_id}`}
              onClick={(e) => {
                e.preventDefault()
                const el = document.getElementById(`post-${post.parent_id}`)
                if (el) {
                  el.scrollIntoView({ behavior: 'smooth', block: 'center' })
                  el.classList.add('ring-2', 'ring-primary-500/40')
                  setTimeout(() => el.classList.remove('ring-2', 'ring-primary-500/40'), 3000)
                }
              }}
              className="text-[11px] text-dark-500 mb-2 flex items-center gap-1 hover:text-primary-400 transition-colors group cursor-pointer"
            >
              <Reply size={12} />
              <span>
                {t('forum.in_reply_to')}{' '}
                <span className="text-primary-400 group-hover:text-primary-300 font-medium">
                  {displayName(post.parent_author)}
                </span>
                {post.parent_preview && (
                  <span className="text-dark-600 ml-1">— "{post.parent_preview.length > 60 ? post.parent_preview.slice(0, 60) + '...' : post.parent_preview}"</span>
                )}
              </span>
            </a>
          )}

          {post.is_deleted ? (
            <div className="text-dark-500 italic text-sm py-4">
              [{t('forum.post_deleted_notice')}{post.delete_reason ? `: ${post.delete_reason}` : ''}]
            </div>
          ) : (
            <div className="flex-1">
              <MarkdownContent content={post.content} />
            </div>
          )}

          {!post.is_deleted && post.author?.signature && (
            <div className="mt-4 pt-3 border-t border-dark-700/30">
              {post.author.is_premium ? (
                <div className="text-[11px] text-dark-400">
                  <ReactMarkdown
                    className="prose prose-invert max-w-none prose-p:my-0 prose-p:text-[11px] prose-img:inline-block prose-img:max-h-12 prose-img:rounded prose-a:text-primary-400"
                    components={{ a: ({ node, ...props }) => <a {...props} target="_blank" rel="noopener noreferrer" /> }}
                  >
                    {post.author.signature}
                  </ReactMarkdown>
                </div>
              ) : (
                <p className="text-[11px] text-dark-500 italic whitespace-pre-wrap">{post.author.signature}</p>
              )}
            </div>
          )}

          {!post.is_deleted && (
            <div className="flex items-center gap-2 mt-4 pt-3 border-t border-dark-700/30">
              <button
                onClick={() => onLike(post.id)}
                className={`flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg transition-all ${
                  post.user_liked || post.is_liked
                    ? 'text-primary-400 bg-primary-500/10'
                    : 'text-dark-400 hover:text-white hover:bg-dark-700/50'
                }`}
              >
                <Heart size={16} fill={(post.user_liked || post.is_liked) ? 'currentColor' : 'none'} />
                {post.like_count || 0}
              </button>
              {(post.like_count || 0) > 0 && onShowLikes && (
                <button
                  onClick={() => onShowLikes(post.id)}
                  className="text-[11px] font-medium text-dark-500 hover:text-primary-300 px-1.5 py-1 rounded transition-colors"
                >
                  {t('forum.who_liked')}
                </button>
              )}
              {canPost() && !isLocked && (
                <button
                  onClick={() => onQuote(post)}
                  className="flex items-center gap-1.5 text-xs font-medium text-dark-400 hover:text-white hover:bg-dark-700/50 px-3 py-1.5 rounded-lg transition-all"
                >
                  <Reply size={16} />
                  {t('forum.quote')}
                </button>
              )}
              {canEditThis && !post.is_deleted && (
                <button
                  onClick={() => onEdit(post)}
                  className="flex items-center gap-1.5 text-xs font-medium text-dark-400 hover:text-white hover:bg-dark-700/50 px-3 py-1.5 rounded-lg transition-all"
                >
                  <Edit3 size={14} />
                  {t('common.edit')}
                </button>
              )}
              {canDeleteThis && !post.is_deleted && (
                <button
                  onClick={() => onDelete(post)}
                  className="flex items-center gap-1.5 text-xs font-medium text-dark-400 hover:text-red-400 hover:bg-red-500/10 px-3 py-1.5 rounded-lg transition-all"
                >
                  <Trash2 size={14} />
                  {t('common.delete')}
                </button>
              )}
              {user && post.author?.id !== user.id && onRep && (
                <button
                  onClick={() => onRep(post)}
                  className="flex items-center gap-1.5 text-xs font-medium text-dark-400 hover:text-yellow-400 hover:bg-yellow-500/10 px-3 py-1.5 rounded-lg transition-all ml-auto"
                >
                  <Star size={16} />
                  {t('forum.rep_button')}
                </button>
              )}
              {user && post.author?.id !== user.id && (
                <button
                  onClick={() => setShowReport(true)}
                  title={t('forum.report_post_tooltip')}
                  className="flex items-center gap-1.5 text-xs font-medium text-dark-500 hover:text-red-400 hover:bg-red-500/10 px-2 py-1.5 rounded-lg transition-all"
                >
                  <Flag size={14} />
                </button>
              )}
            </div>
          )}
          <ReportModal
            open={showReport}
            onClose={() => setShowReport(false)}
            reportType="post"
            targetId={post.id}
            targetLabel={t('forum.report_target', { n: postNumber, name: displayName(author) })}
          />
        </div>
      </div>
    </div>
  )
}
