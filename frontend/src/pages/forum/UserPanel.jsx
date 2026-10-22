import { useState, useRef, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { MessageSquare, Star, User } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import api from '../../lib/api'
import { useToast } from '../../components/Toast'
import RoleBadge from '../../components/RoleBadge'
import { roleStyle } from '../../components/admin/ui'
import BadgeIcon from '../../components/BadgeIcon'
import { displayName, realName, telegramHandle, parseDate, nameColorStyle } from '../../lib/utils'
import { useT, getDateLocale } from '../../lib/i18n'

export default function UserPanel({ author, currentUser, post, onRep, authorBadges }) {
  const t = useT()
  const [showPopup, setShowPopup] = useState(false)
  const popupRef = useRef(null)
  const navigate = useNavigate()
  const { showToast } = useToast()

  if (!author) return null
  const joinDate = author.created_at ? parseDate(author.created_at).toLocaleDateString(getDateLocale(), { month: 'short', year: 'numeric' }) : null
  const repTotal = (author.rep_positive || 0) - (author.rep_negative || 0)
  const isOwnProfile = currentUser?.id === author.id

  useEffect(() => {
    if (!showPopup) return
    const handler = (e) => {
      if (popupRef.current && !popupRef.current.contains(e.target)) {
        setShowPopup(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [showPopup])

  const handleStartDM = async () => {
    try {
      const { data } = await api.post('/api/dm/start', {
        user_id: author.id,
        message: 'Hey!'
      })
      setShowPopup(false)
      navigate(`/messages/${data.conversation_id}`)
    } catch (err) {
      showToast(err.response?.data?.detail || t('forum.failed_start_dm'), 'error')
    }
  }

  const handleGiveRep = () => {
    if (onRep && post) {
      setShowPopup(false)
      onRep(post)
    }
  }

  return (
    <div className="w-28 sm:w-36 flex-shrink-0 flex flex-col items-center text-center pt-1 relative">
      {/* Avatar button */}
      <button
        onClick={() => setShowPopup(!showPopup)}
        className="group relative cursor-pointer"
      >
        <div
          className="w-16 h-16 sm:w-20 sm:h-20 rounded-full bg-dark-700 flex items-center justify-center overflow-hidden ring-2 ring-dark-600 group-hover:ring-primary-500/50 transition-all"
          style={author.profile_theme ? (() => {
            try {
              const t = typeof author.profile_theme === 'string' ? JSON.parse(author.profile_theme) : author.profile_theme
              const border = t.avatar_border || null
              const glow = t.avatar_glow && border ? `0 0 14px ${border}` : ''
              const ring = border ? `0 0 0 2px ${border}` : ''
              return { boxShadow: [ring, glow].filter(Boolean).join(', ') || undefined }
            } catch { return {} }
          })() : {}}
        >
          {author.avatar_url ? (
            <img src={author.avatar_url} alt="" className="w-full h-full object-cover" />
          ) : (
            <span className="text-xl sm:text-2xl font-bold text-dark-400">
              {realName(author)[0]?.toUpperCase() || '?'}
            </span>
          )}
        </div>
        {author.last_seen_at && (Date.now() - parseDate(author.last_seen_at).getTime()) < 300000 && (
          <div className="absolute bottom-0 right-0 w-3.5 h-3.5 bg-green-500 rounded-full ring-2 ring-dark-800" />
        )}
      </button>

      {/* Username button */}
      <button
        onClick={() => setShowPopup(!showPopup)}
        className={`font-semibold text-sm mt-1.5 truncate max-w-full cursor-pointer ${roleStyle(author?.role).text}`}
        style={nameColorStyle(author)}
      >
        {realName(author)}
      </button>

      {telegramHandle(author) && (
        <span className="text-[10px] font-mono text-primary-400/60 truncate max-w-full">{telegramHandle(author)}</span>
      )}

      {author.custom_title && (
        <span className="text-[10px] text-dark-300 mt-0.5 italic truncate max-w-full">{author.custom_title}</span>
      )}

      <RoleBadge role={author.role} className="mt-1" />

      {authorBadges?.length > 0 && (
        <div className="flex flex-wrap justify-center gap-0.5 mt-1.5">
          {authorBadges.slice(0, 5).map((b, i) => (
            <div
              key={i}
              className="w-6 h-6 rounded-lg flex items-center justify-center bg-dark-700/60"
              title={b.badge_name}
            >
              <BadgeIcon icon={b.badge_icon} iconStyle={b.badge_icon_style} color={b.badge_color} size={13} />
            </div>
          ))}
          {authorBadges.length > 5 && (
            <span className="text-[9px] text-dark-500 leading-6">+{authorBadges.length - 5}</span>
          )}
        </div>
      )}

      <div className="grid grid-cols-2 gap-x-2 gap-y-0.5 mt-2 text-[10px] text-dark-400 w-full">
        <span>{t('forum.posts_stat')}</span>
        <span className="text-dark-200 font-medium">{author.post_count || 0}</span>
        <span>{t('forum.threads_stat')}</span>
        <span className="text-dark-200 font-medium">{author.thread_count || 0}</span>
        <span>{t('forum.likes_stat')}</span>
        <span className="text-dark-200 font-medium">{author.like_count || 0}</span>
        <span>{t('forum.rep_stat')}</span>
        <span className={`font-medium ${repTotal > 0 ? 'text-green-400' : repTotal < 0 ? 'text-red-400' : 'text-dark-200'}`}>
          {repTotal > 0 ? '+' : ''}{repTotal}
        </span>
      </div>

      {joinDate && (
        <div className="text-[10px] text-dark-500 mt-2">{t('forum.joined_date', { date: joinDate })}</div>
      )}

      {/* Popup */}
      <AnimatePresence>
        {showPopup && (
          <motion.div
            ref={popupRef}
            initial={{ opacity: 0, scale: 0.95, y: -4 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: -4 }}
            transition={{ duration: 0.12 }}
            className="absolute top-12 left-1/2 -translate-x-1/2 z-30 bg-dark-800 border border-dark-600 rounded-xl shadow-xl py-1.5 min-w-[180px]"
          >
            <div className="px-3 py-1.5 text-[10px] text-dark-500 uppercase tracking-wider font-semibold border-b border-dark-700/50">
              {displayName(author, false)}
            </div>

            <Link
              to={`/profile/${author.id}`}
              onClick={() => setShowPopup(false)}
              className="flex items-center gap-2.5 w-full text-left px-3 py-2 text-xs text-dark-200 hover:text-white hover:bg-dark-700/50 transition-colors"
            >
              <User className="w-3.5 h-3.5 text-dark-400" />
              {t('forum.view_profile')}
            </Link>

            {!isOwnProfile && currentUser && (
              <button
                onClick={handleStartDM}
                className="flex items-center gap-2.5 w-full text-left px-3 py-2 text-xs text-dark-200 hover:text-white hover:bg-dark-700/50 transition-colors"
              >
                <MessageSquare className="w-3.5 h-3.5 text-dark-400" />
                {t('forum.send_message')}
              </button>
            )}

            {!isOwnProfile && currentUser && onRep && (
              <button
                onClick={handleGiveRep}
                className="flex items-center gap-2.5 w-full text-left px-3 py-2 text-xs text-dark-200 hover:text-white hover:bg-dark-700/50 transition-colors"
              >
                <Star className="w-3.5 h-3.5 text-dark-400" />
                {t('forum.give_reputation')}
              </button>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
