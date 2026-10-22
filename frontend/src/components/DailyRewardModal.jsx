import { Flame, Zap, Wallet, Award } from 'lucide-react'
import { useT } from '../lib/i18n'

export default function DailyRewardModal({ show, onClose, onClaim, claiming, xpInfo }) {
  const t = useT()
  if (!show) return null

  return (
    <div className="fixed inset-0 bg-black/60 z-[70] flex items-center justify-center p-4">
      <div className="bg-dark-800 rounded-2xl border border-dark-700 w-full max-w-sm p-6 space-y-5 animate-in fade-in zoom-in">
        <div className="text-center">
          <div className="w-16 h-16 bg-gradient-to-br from-yellow-400 to-orange-500 rounded-2xl flex items-center justify-center mx-auto mb-4">
            <Flame size={32} className="text-white" />
          </div>
          <h2 className="font-display font-bold text-xl">{t('modals.daily.title')}</h2>
          <p className="text-dark-400 text-sm mt-1">
            {xpInfo?.login_streak > 1
              ? t('modals.daily.streak_line', { n: xpInfo.login_streak })
              : t('modals.daily.come_back')}
          </p>
        </div>

        <div className="bg-dark-900/60 rounded-xl p-4 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Zap size={16} className="text-yellow-400" />
              <span className="text-sm">{t('modals.daily.xp_bonus')}</span>
            </div>
            <span className="text-sm font-semibold text-primary-400">
              +{xpInfo?.daily_xp_preview || 0} XP
            </span>
          </div>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Wallet size={16} className="text-green-400" />
              <span className="text-sm">{t('modals.daily.balance_bonus')}</span>
            </div>
            <span className="text-sm font-semibold text-green-400">
              +${(xpInfo?.daily_balance_preview || 0).toFixed(2)}
            </span>
          </div>
          {xpInfo?.daily_badge_preview && (
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Award size={16} className="text-purple-400" />
                <span className="text-sm">{t('modals.daily.badge')}</span>
              </div>
              <span className="text-sm font-semibold text-purple-400">
                {xpInfo.daily_badge_preview}
              </span>
            </div>
          )}
          {xpInfo?.login_streak > 0 && (
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Flame size={16} className="text-orange-400" />
                <span className="text-sm">{t('modals.daily.streak')}</span>
              </div>
              <span className="text-sm font-semibold text-orange-400">
                {t('modals.daily.day_n', { n: xpInfo.login_streak })}
              </span>
            </div>
          )}
        </div>

        <button
          onClick={onClaim}
          disabled={claiming}
          className="w-full py-3 rounded-xl font-semibold bg-gradient-to-r from-yellow-500 to-orange-500 text-white hover:from-yellow-400 hover:to-orange-400 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {claiming ? t('modals.daily.claiming') : t('modals.daily.claim')}
        </button>

        <button
          onClick={onClose}
          className="w-full text-xs text-dark-400 hover:text-dark-300 transition-colors"
        >
          {t('modals.maybe_later')}
        </button>
      </div>
    </div>
  )
}
