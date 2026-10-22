import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { Copy, Check, Users, UserPlus, Link2, Sparkles, TrendingUp } from 'lucide-react'
import api from '../lib/api'
import { useToast } from '../components/Toast'
import { timeAgo } from '../lib/utils'
import { Card, SectionHeader, PageHeading, Button, StatTile, EmptyState, LoadingState } from '../components/ui'
import { useT } from '../lib/i18n'

export default function Referrals() {
  const [referrals, setReferrals] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [copied, setCopied] = useState(false)
  const { addToast } = useToast()
  const t = useT()

  useEffect(() => {
    loadReferrals()
  }, [])

  const loadReferrals = async () => {
    try {
      const { data } = await api.get('/api/users/me/referrals')
      setReferrals(data)
      setError(false)
    } catch {
      setError(true)
    } finally {
      setLoading(false)
    }
  }

  const handleCopy = async () => {
    if (!referrals?.referral_link) return
    try {
      await navigator.clipboard.writeText(referrals.referral_link)
      setCopied(true)
      addToast(t('ref.link_copied'), { type: 'success', title: t('ref.copied_title') })
      setTimeout(() => setCopied(false), 2000)
    } catch {
      addToast(t('ref.copy_failed'), { type: 'error' })
    }
  }

  if (loading) {
    return <LoadingState label={t('ref.loading')} className="min-h-[50vh] flex flex-col justify-center" />
  }

  if (error && !referrals) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-20 text-center">
        <div className="text-dark-500 text-lg mb-4">{t('ref.load_failed')}</div>
        <Button variant="primary" onClick={() => { setError(false); setLoading(true); loadReferrals() }}>{t('common.retry')}</Button>
      </div>
    )
  }

  const hasReferrals = referrals && (referrals.direct_referrals > 0 || referrals.indirect_referrals > 0)
  const earnings = referrals?.referral_earnings || 0
  const directCount = referrals?.direct_referrals || 0
  const indirectCount = referrals?.indirect_referrals || 0
  const recentCommissions = referrals?.recent_commissions || []

  return (
    <div className="space-y-4">
      {/* Header */}
      <PageHeading
        icon={Users}
        title={t('ref.title')}
        subtitle={t('ref.subtitle')}
      />

      {/* Stats Cards - 3 columns */}
      <div className="grid grid-cols-3 gap-3">
        <StatTile label={t('ref.total_earnings')} value={`$${earnings.toFixed(2)}`} accent={earnings > 0 ? 'amber' : 'default'} />
        <StatTile label={t('ref.direct')} value={directCount} accent="cyan" />
        <StatTile label={t('ref.indirect')} value={indirectCount} accent="purple" />
      </div>

      {/* Commission Rates & Referral Link Row */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Commission Rates Card */}
        <Card as={motion.div} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
          <SectionHeader>
            <TrendingUp size={16} className="text-primary-400" />
            {t('ref.commission_rates')}
          </SectionHeader>
          <div className="space-y-3">
            <div className="flex items-center justify-between p-3 bg-dark-950/60 rounded-lg border border-primary-500/10">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-lg bg-primary-500/15 flex items-center justify-center">
                  <UserPlus size={14} className="text-primary-400" />
                </div>
                <div>
                  <p className="text-sm font-medium text-white">{t('ref.level1')}</p>
                  <p className="text-[10px] text-dark-400">{t('ref.level1_desc')}</p>
                </div>
              </div>
              <span className="text-lg font-bold font-mono text-primary-400">
                {referrals?.level1_percent ?? 3}%
              </span>
            </div>
            <div className="flex items-center justify-between p-3 bg-dark-950/60 rounded-lg border border-primary-500/10">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-lg bg-purple-500/15 flex items-center justify-center">
                  <Users size={14} className="text-purple-300" />
                </div>
                <div>
                  <p className="text-sm font-medium text-white">{t('ref.level2')}</p>
                  <p className="text-[10px] text-dark-400">{t('ref.level2_desc')}</p>
                </div>
              </div>
              <span className="text-lg font-bold font-mono text-purple-300">
                {referrals?.level2_percent ?? 5}%
              </span>
            </div>
          </div>
        </Card>

        {/* Referral Link Card */}
        <Card as={motion.div} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.25 }}>
          <SectionHeader>
            <Link2 size={16} className="text-primary-400" />
            {t('ref.your_link')}
          </SectionHeader>
          <p className="text-xs text-dark-400 mb-3">
            {t('ref.share_hint')}
          </p>
          <div className="flex items-center gap-2">
            <input
              type="text"
              readOnly
              value={referrals?.referral_link || ''}
              className="flex-1 bg-dark-950/60 border border-primary-500/15 rounded-lg px-3 py-2.5 text-xs text-dark-200 font-mono truncate focus:outline-none focus:border-primary-500/50"
              onClick={(e) => e.target.select()}
            />
            <Button
              variant="secondary"
              icon={copied ? Check : Copy}
              onClick={handleCopy}
              className={copied ? 'text-neon-400' : ''}
            >
              {copied ? t('ref.copied') : t('ref.copy')}
            </Button>
          </div>
          {referrals?.referral_code && (
            <p className="text-[10px] text-dark-500 mt-2">
              {t('ref.code')} <span className="text-dark-300 font-mono">{referrals.referral_code}</span>
            </p>
          )}
        </Card>
      </div>

      {/* Recent Commissions */}
      <Card as={motion.div} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }} className="!p-0 overflow-hidden">
        <div className="p-4 border-b border-primary-500/10">
          <SectionHeader className="mb-0">
            <Sparkles size={16} className="text-primary-400" />
            {t('ref.recent_commissions')}
          </SectionHeader>
        </div>

        {recentCommissions.length === 0 ? (
          !hasReferrals ? (
            <div className="p-8">
              <EmptyState icon={Users}>{t('ref.no_referrals')}</EmptyState>
              <div className="max-w-sm mx-auto text-center space-y-2 mt-2">
                <p className="text-dark-400 text-sm">
                  {t('ref.empty_text', { p1: referrals?.level1_percent ?? 3, p2: referrals?.level2_percent ?? 5 })}
                </p>
                <p className="text-dark-500 text-xs">
                  {t('ref.empty_hint')}
                </p>
              </div>
            </div>
          ) : (
            <EmptyState icon={Sparkles}>{t('ref.no_activity')}</EmptyState>
          )
        ) : (
          <div className="divide-y divide-primary-500/10">
            {recentCommissions.slice(0, 20).map((commission) => (
              <div
                key={commission.id}
                className="p-4 hover:bg-dark-800/40 transition-colors"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-white">{commission.title}</p>
                    {commission.body && (
                      <p className="text-xs text-dark-400 mt-1 line-clamp-2">{commission.body}</p>
                    )}
                  </div>
                  <span className="text-xs text-dark-500 flex-shrink-0 mt-1 font-mono">
                    {timeAgo(commission.created_at)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  )
}
