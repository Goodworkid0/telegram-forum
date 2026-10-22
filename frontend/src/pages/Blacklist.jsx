import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { ShieldX, User, Calendar, AlertTriangle, Copy, Check } from 'lucide-react'
import api from '../lib/api'
import { formatDate, realName, telegramHandle } from '../lib/utils'
import { useT } from '../lib/i18n'

export default function Blacklist() {
  const t = useT()
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [copiedId, setCopiedId] = useState(null)

  useEffect(() => {
    loadBlacklist()
  }, [])

  const loadBlacklist = async () => {
    try {
      const { data } = await api.get('/api/admin/blacklist')
      setUsers(data)
    } catch (error) {
      console.error(error)
    } finally {
      setLoading(false)
    }
  }

  const copyToClipboard = (text, id) => {
    navigator.clipboard.writeText(text)
    setCopiedId(id)
    setTimeout(() => setCopiedId(null), 2000)
  }

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="card p-4 animate-pulse">
          <div className="h-8 bg-dark-700 rounded w-1/3 mb-4" />
          <div className="space-y-3">
            {[1, 2, 3].map(i => (
              <div key={i} className="h-20 bg-dark-800 rounded-xl" />
            ))}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-4 pb-20">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="card p-4"
      >
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-xl bg-red-500/10 flex items-center justify-center">
            <ShieldX size={24} className="text-red-400" />
          </div>
          <div>
            <h1 className="text-xl font-bold">{t('bl.title')}</h1>
            <p className="text-sm text-dark-400">
              {users.length === 1 ? t('bl.banned_one', { n: users.length }) : t('bl.banned_many', { n: users.length })}
            </p>
          </div>
        </div>
      </motion.div>

      {/* Banned Users List */}
      {users.length === 0 ? (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="card p-8 text-center"
        >
          <Check size={48} className="mx-auto text-emerald-400 mb-3" />
          <p className="text-dark-300 font-medium">{t('bl.no_banned')}</p>
          <p className="text-dark-500 text-sm mt-1">{t('bl.empty')}</p>
        </motion.div>
      ) : (
        <div className="space-y-3">
          {users.map((user, index) => (
            <motion.div
              key={user.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.05 * index }}
              className="card p-4"
            >
              <div className="flex items-start gap-3">
                {/* Avatar */}
                {user.avatar_url ? (
                  <img
                    src={user.avatar_url}
                    alt={realName(user)}
                    className="w-12 h-12 rounded-xl object-cover shrink-0"
                  />
                ) : (
                  <div className="w-12 h-12 rounded-xl bg-red-500/10 flex items-center justify-center shrink-0">
                    <User size={20} className="text-red-400" />
                  </div>
                )}

                {/* User Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-semibold text-dark-100">
                      {user.first_name || user.username || t('bl.unknown_user')}
                    </span>
                    {telegramHandle(user) && (
                      <span className="text-sm text-dark-400">{telegramHandle(user)}</span>
                    )}
                    {user.role && user.role !== 'buyer' && (
                      <span className={`text-xs px-2 py-0.5 rounded-full ${
                        user.role === 'seller' 
                          ? 'bg-blue-500/10 text-blue-400'
                          : 'bg-purple-500/10 text-purple-400'
                      }`}>
                        {user.role}
                      </span>
                    )}
                  </div>

                  {/* Telegram ID */}
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-xs text-dark-500">{t('bl.tg_id')}</span>
                    <code className="text-xs bg-dark-800 px-2 py-0.5 rounded font-mono text-dark-300">
                      {user.telegram_id}
                    </code>
                    <button
                      onClick={() => copyToClipboard(user.telegram_id, user.id)}
                      className="text-dark-500 hover:text-dark-300 transition-colors"
                    >
                      {copiedId === user.id ? (
                        <Check size={12} className="text-emerald-400" />
                      ) : (
                        <Copy size={12} />
                      )}
                    </button>
                  </div>

                  {/* Ban Date */}
                  <div className="flex items-center gap-1.5 mt-2 text-xs text-dark-500">
                    <Calendar size={12} />
                    <span>{t('bl.banned_at', { date: formatDate(user.banned_at, { time: true }) })}</span>
                  </div>

                  {/* Ban Reason */}
                  {user.ban_reason && (
                    <div className="mt-3 p-3 bg-red-500/5 border border-red-500/20 rounded-lg">
                      <div className="flex items-center gap-1.5 text-xs text-red-400 mb-1">
                        <AlertTriangle size={12} />
                        <span className="font-medium">{t('bl.reason')}</span>
                      </div>
                      <p className="text-sm text-dark-300 whitespace-pre-wrap">
                        {user.ban_reason}
                      </p>
                    </div>
                  )}
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  )
}
