import { Link } from 'react-router-dom'
import { ShieldCheck } from 'lucide-react'
import { useT } from '../lib/i18n'

export default function TrialWelcomeModal({ show, onClose }) {
  const t = useT()
  if (!show) return null

  const dismiss = () => {
    localStorage.setItem('trial_welcome_dismissed', '1')
    onClose()
  }

  return (
    <div className="fixed inset-0 bg-black/70 z-[80] flex items-center justify-center p-4">
      <div className="bg-dark-800 rounded-2xl border border-blue-500/20 w-full max-w-md p-6 space-y-5">
        <div className="text-center">
          <div className="w-16 h-16 bg-gradient-to-br from-blue-400 to-purple-500 rounded-2xl flex items-center justify-center mx-auto mb-4">
            <ShieldCheck size={32} className="text-white" />
          </div>
          <h2 className="font-display font-bold text-xl">{t('modals.trial.title')}</h2>
          <p className="text-dark-300 text-sm mt-2">
            {t('modals.trial.intro_before')}<span className="text-blue-400 font-semibold">{t('modals.trial.intro_mode')}</span>{t('modals.trial.intro_after')}
          </p>
        </div>

        <div className="bg-dark-900/60 rounded-xl p-4 space-y-3 text-sm">
          <div className="flex items-start gap-3">
            <span className="text-lg flex-shrink-0">1</span>
            <div>
              <p className="font-medium text-white">{t('modals.trial.step1_title')}</p>
              <p className="text-dark-400 text-xs mt-0.5">
                {t('modals.trial.step1_before')}<strong className="text-primary-400">{t('modals.trial.step1_board')}</strong>{t('modals.trial.step1_after')}
              </p>
            </div>
          </div>
          <div className="flex items-start gap-3">
            <span className="text-lg flex-shrink-0">2</span>
            <div>
              <p className="font-medium text-white">{t('modals.trial.step2_title')}</p>
              <p className="text-dark-400 text-xs mt-0.5">
                {t('modals.trial.step2_desc')}
              </p>
            </div>
          </div>
          <div className="flex items-start gap-3">
            <span className="text-lg flex-shrink-0">3</span>
            <div>
              <p className="font-medium text-white">{t('modals.trial.step3_title')}</p>
              <p className="text-dark-400 text-xs mt-0.5">
                {t('modals.trial.step3_before')}<strong className="text-white">{t('modals.trial.step3_strong')}</strong>{t('modals.trial.step3_after')}
              </p>
            </div>
          </div>
        </div>

        <div className="flex gap-2">
          <Link
            to="/board/request-access"
            onClick={dismiss}
            className="flex-1 py-3 rounded-xl font-semibold text-center bg-gradient-to-r from-blue-500 to-purple-500 text-white hover:from-blue-400 hover:to-purple-400 transition-all"
          >
            {t('modals.trial.request_access')}
          </Link>
          <Link
            to="/shop"
            onClick={dismiss}
            className="flex-1 py-3 rounded-xl font-semibold text-center bg-gradient-to-r from-amber-500 to-orange-500 text-white hover:from-amber-400 hover:to-orange-400 transition-all"
          >
            {t('modals.trial.purchase_premium')}
          </Link>
        </div>
        <button
          onClick={dismiss}
          className="w-full text-xs text-dark-400 hover:text-dark-300 transition-colors"
        >
          {t('modals.maybe_later')}
        </button>
      </div>
    </div>
  )
}
