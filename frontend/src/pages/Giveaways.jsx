import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { Gift, Calendar, CheckCircle, Wallet, Users } from 'lucide-react'
import api from '../lib/api'
import { useAuthStore } from '../store/authStore'
import { useToast } from '../components/Toast'
import BannerRows from '../components/BannerRows'
import { Card, PageHeading, Button, Tag, EmptyState, LoadingState } from '../components/ui'
import { parseDate } from '../lib/utils'
import { useT, getDateLocale } from '../lib/i18n'

const fmt = (iso) => {
  if (!iso) return ''
  try {
    const d = parseDate(iso)
    return d ? d.toLocaleString(getDateLocale()) : ''
  } catch {
    return ''
  }
}

export default function Giveaways() {
  const { user } = useAuthStore()
  const { addToast } = useToast()
  const t = useT()
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [enteringId, setEnteringId] = useState(null)
  const [entered, setEntered] = useState({}) // giveawayId -> true

  const load = async () => {
    setLoading(true)
    try {
      // Users are always registered; use auth endpoint to get already_entered.
      const { data } = await api.get('/api/giveaways/for-user')
      const list = data || []
      setItems(list)
      const enteredMap = {}
      for (const g of list) {
        if (g?.already_entered) enteredMap[g.id] = true
      }
      setEntered(enteredMap)
    } catch {
      setItems([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const enter = async (g) => {
    if (enteringId) return
    setEnteringId(g.id)
    try {
      if (!user) {
        addToast(t('ga.login_required'), { type: 'error' })
        return
      }
      const { data } = await api.post(`/api/giveaways/${g.id}/enter`, {})
      if (data?.ok) {
        setEntered(prev => ({ ...prev, [g.id]: true }))
        addToast(t('ga.entered_toast'), { type: 'success', title: t('ga.entered_title') })
      }
    } catch (e) {
      addToast(e.response?.data?.detail || t('ga.enter_failed'), { type: 'error' })
    } finally {
      setEnteringId(null)
    }
  }

  return (
    <div className="space-y-4">
      <BannerRows />
      <PageHeading icon={Gift} title={t('ga.title')} subtitle={t('ga.subtitle')} />

      {loading ? (
        <LoadingState label={t('ga.loading')} />
      ) : items.length === 0 ? (
        <EmptyState icon={Gift}>{t('ga.empty')}</EmptyState>
      ) : (
        <div className="space-y-2">
          {items.map((g, i) => {
            const isEntered = !!entered[g.id]
            const isEntering = enteringId === g.id
            return (
              <Card
                as={motion.div}
                key={g.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.03 }}
              >
                <div className="flex items-start gap-3">
                  <div className="w-10 h-10 rounded-xl bg-primary-500/15 border border-primary-500/25 flex items-center justify-center shrink-0">
                    <Gift size={18} className="text-primary-400" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-2">
                      <h3 className="text-sm font-semibold truncate">{g.title}</h3>
                      {g.deposit_required ? (
                        <Tag tone="amber" icon={Wallet}>{t('ga.deposit_required')}</Tag>
                      ) : (
                        <Tag tone="neutral">{t('ga.all_users')}</Tag>
                      )}
                    </div>

                    {g.winner?.display_name && (
                      <div className="mt-1.5">
                        <Tag tone="green">{t('ga.winner', { name: g.winner.display_name })}</Tag>
                        {g.winner.picked_at ? (
                          <span className="text-[11px] text-dark-500 ml-1.5 font-mono">{fmt(g.winner.picked_at)}</span>
                        ) : null}
                      </div>
                    )}
                    {g.prize && (
                      <p className="text-xs text-primary-300 mt-1">{t('ga.prize', { prize: g.prize })}</p>
                    )}
                    {g.description && (
                      <p className="text-xs text-dark-300 mt-1 leading-relaxed whitespace-pre-wrap">{g.description}</p>
                    )}
                    {(g.starts_at || g.ends_at) && (
                      <p className="text-[11px] text-dark-500 mt-2 inline-flex items-center gap-1 font-mono">
                        <Calendar size={11} />
                        {g.starts_at ? t('ga.starts', { date: fmt(g.starts_at) }) : ''}
                        {g.ends_at ? `${g.starts_at ? ' • ' : ''}${t('ga.ends', { date: fmt(g.ends_at) })}` : ''}
                      </p>
                    )}

                  </div>
                </div>

                <div className="mt-3 pt-3 border-t border-primary-500/10">
                  <div className="flex items-center justify-between text-[11px] text-dark-400 mb-2">
                    <span className="inline-flex items-center gap-1"><Users size={12} /> {t('ga.participants')}</span>
                    <span className="text-dark-500 font-mono">{g.participant_count || 0}</span>
                  </div>
                  {(g.participants || []).length === 0 ? (
                    <p className="text-xs text-dark-500">{t('ga.no_participants')}</p>
                  ) : (
                    <div className="flex flex-wrap gap-1.5">
                      {(g.participants || []).slice(0, 30).map((p, idx) => (
                        <Tag key={idx} tone="neutral" className="normal-case tracking-normal">
                          {p.display_name}
                        </Tag>
                      ))}
                      {(g.participants || []).length > 30 && (
                        <Tag key="more" tone="neutral">+{(g.participants || []).length - 30}</Tag>
                      )}
                    </div>
                  )}
                </div>

                <div className="mt-3">
                  <Button
                    variant="primary"
                    onClick={() => enter(g)}
                    disabled={isEntering || isEntered}
                    icon={isEntered ? CheckCircle : Gift}
                    className="w-full py-2.5"
                  >
                    {isEntered ? t('ga.entered') : (isEntering ? t('ga.entering') : t('ga.enter'))}
                  </Button>
                </div>
              </Card>
            )
          })}
        </div>
      )}
    </div>
  )
}
