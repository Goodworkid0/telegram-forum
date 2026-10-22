import { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Shield, Plus, X, ShieldCheck, AlertTriangle, User, Ticket, Copy, Check } from 'lucide-react'
import api from '../lib/api'
import { useAuthStore } from '../store/authStore'
import { useToast } from '../components/Toast'
import { timeAgo } from '../lib/utils'
import { motion, AnimatePresence } from 'framer-motion'
import BannerRows from '../components/BannerRows'
import { Card, PageHeading, Button, StatusBadge, Tag, FormInput, FormSelect, FormTextarea, EmptyState, LoadingState } from '../components/ui'
import { useT } from '../lib/i18n'

const HOLD_LABEL_KEYS = { 1: 'escrow.hold_short_24h', 2: 'escrow.hold_short_48h', 7: 'escrow.hold_short_7d', 14: 'escrow.hold_short_14d', 30: 'escrow.hold_short_30d' }

export default function Escrow() {
  const t = useT()
  const [deals, setDeals] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [maxDeals, setMaxDeals] = useState(false)
  const [showInvite, setShowInvite] = useState(false)
  const [inviteForm, setInviteForm] = useState({ role: 'buyer', title: '', description: '', amount: '' })
  const [inviteHold, setInviteHold] = useState(0)
  const [createdInvite, setCreatedInvite] = useState(null)
  const [inviteBusy, setInviteBusy] = useState(false)
  const [codeCopied, setCodeCopied] = useState(false)
  const [redeemCode, setRedeemCode] = useState('')
  const [redeemPreview, setRedeemPreview] = useState(null)
  const [redeemBusy, setRedeemBusy] = useState(false)
  const navigate = useNavigate()
  const { showToast } = useToast()
  const { user, isVerified } = useAuthStore()

  useEffect(() => { loadDeals() }, [])

  const loadDeals = async () => {
    try {
      const [dealsRes, walletRes] = await Promise.all([
        api.get('/api/escrow/deals'),
        api.get('/api/wallet'),
      ])
      const dealsList = Array.isArray(dealsRes.data) ? dealsRes.data : dealsRes.data.deals || []
      setDeals(dealsList)
      const maxEscrow = walletRes.data?.max_escrow_deals || 3
      const activeStatuses = ['pending', 'accepted', 'funded', 'delivered', 'disputed']
      const activeCount = dealsList.filter(d => activeStatuses.includes(d.status)).length
      setMaxDeals(activeCount >= maxEscrow)
      setError(null)
    } catch {
      setError('escrow.load_error')
    } finally { setLoading(false) }
  }

  const handleCreateInvite = async (e) => {
    e.preventDefault()
    if (!inviteForm.title || !inviteForm.amount) return
    setInviteBusy(true)
    try {
      const { data } = await api.post('/api/escrow/invites', {
        ...inviteForm,
        amount: parseFloat(inviteForm.amount),
        hold_days: inviteHold > 0 ? inviteHold : null,
      })
      setCreatedInvite(data)
      setInviteForm({ role: 'buyer', title: '', description: '', amount: '' })
      setInviteHold(0)
    } catch (err) {
      showToast(err.response?.data?.detail || t('escrow.invite_create_failed'), 'error')
    } finally { setInviteBusy(false) }
  }

  const copyInviteCode = async () => {
    try {
      await navigator.clipboard.writeText(createdInvite.code)
      setCodeCopied(true)
      setTimeout(() => setCodeCopied(false), 2000)
    } catch { showToast(createdInvite.code, 'info') }
  }

  const handlePreviewInvite = async () => {
    const code = redeemCode.trim().toUpperCase()
    if (!code) return
    setRedeemBusy(true)
    try {
      const { data } = await api.get(`/api/escrow/invites/${code}`)
      setRedeemPreview(data)
    } catch (err) {
      setRedeemPreview(null)
      showToast(err.response?.data?.detail || t('escrow.invite_invalid'), 'error')
    } finally { setRedeemBusy(false) }
  }

  const handleAcceptInvite = async () => {
    setRedeemBusy(true)
    try {
      const { data } = await api.post(`/api/escrow/invites/${redeemPreview.code}/accept`)
      showToast(t('escrow.invite_accepted'), 'success')
      navigate(`/escrow/${data.id}`)
    } catch (err) {
      showToast(err.response?.data?.detail || t('escrow.invite_accept_failed'), 'error')
    } finally { setRedeemBusy(false) }
  }

  const activeDeals = deals.filter(d => ['pending', 'accepted', 'funded', 'delivered', 'disputed'].includes(d.status))
  const completedDeals = deals.filter(d => ['completed'].includes(d.status))
  const totalInEscrow = activeDeals
    .filter(d => d.status === 'funded' && d.buyer_id === user?.id)
    .reduce((sum, d) => sum + (d.amount || 0), 0)

  return (
    <div className="max-w-4xl mx-auto px-4 py-6 space-y-5">
      <BannerRows />

      {/* Header + Stats */}
      <Card>
        <PageHeading
          icon={Shield}
          title={t('escrow.title')}
          subtitle={t('escrow.subtitle')}
        />

        {/* Stats Row */}
        {deals.length > 0 && (
          <div className="grid grid-cols-3 gap-3 mt-4">
            <div className="bg-dark-950/60 rounded-xl p-3 text-center border border-primary-500/10">
              <p className="text-lg font-bold font-mono text-amber-400">{activeDeals.length}</p>
              <p className="text-[10px] text-dark-400 uppercase tracking-widest">{t('escrow.stat_active')}</p>
            </div>
            <div className="bg-dark-950/60 rounded-xl p-3 text-center border border-primary-500/10">
              <p className="text-lg font-bold font-mono text-neon-400">{completedDeals.length}</p>
              <p className="text-[10px] text-dark-400 uppercase tracking-widest">{t('escrow.stat_completed')}</p>
            </div>
            <div className="bg-dark-950/60 rounded-xl p-3 text-center border border-primary-500/10">
              <p className="text-lg font-bold font-mono text-primary-400">${totalInEscrow.toFixed(2)}</p>
              <p className="text-[10px] text-dark-400 uppercase tracking-widest">{t('escrow.stat_in_escrow')}</p>
            </div>
          </div>
        )}
      </Card>

      {/* Max deals warning */}
      {isVerified() && maxDeals && (
        <Card className="!border-amber-500/30 bg-amber-500/10">
          <div className="flex items-center gap-2 text-sm text-amber-300">
            <AlertTriangle size={16} />
            {t('escrow.max_deals_warning')}
          </div>
        </Card>
      )}

      {/* Trial notice */}
      {!isVerified() && (
        <Card className="p-8 text-center">
          <ShieldCheck size={40} className="mx-auto text-primary-500/40 mb-3" />
          <p className="text-dark-200 font-semibold text-lg">{t('escrow.verified_required')}</p>
          <p className="text-dark-500 text-sm mt-1 mb-4">{t('escrow.verified_required_detail')}</p>
          <Link to="/shop">
            <Button variant="primary">{t('escrow.upgrade_account')}</Button>
          </Link>
        </Card>
      )}

      {/* Invite codes: share a code instead of addressing someone by @handle */}
      {isVerified() && (
        <Card className="space-y-4">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <Ticket size={18} className="text-primary-400" />
              <h3 className="font-semibold">{t('escrow.invite_heading')}</h3>
            </div>
            {!maxDeals && (
              <Button variant="ghost" size="sm" icon={showInvite ? X : Plus} onClick={() => { setShowInvite(!showInvite); setCreatedInvite(null) }}>
                {showInvite ? t('common.cancel') : t('escrow.invite_create_btn')}
              </Button>
            )}
          </div>
          <p className="text-xs text-dark-400 -mt-2">{t('escrow.invite_hint')}</p>

          {/* Redeem a code — hidden while the user is creating their own invite */}
          {!showInvite && (
          <div className="flex gap-2">
            <FormInput
              placeholder={t('escrow.invite_code_ph')}
              value={redeemCode}
              onChange={e => { setRedeemCode(e.target.value.toUpperCase()); setRedeemPreview(null) }}
              maxLength={8}
              className="flex-1"
              inputClassName="uppercase tracking-widest"
            />
            <Button variant="secondary" onClick={handlePreviewInvite} disabled={redeemBusy || redeemCode.trim().length < 8}>
              {t('escrow.invite_check')}
            </Button>
          </div>
          )}

          {!showInvite && redeemPreview && (
            <div className="bg-dark-950/60 border border-primary-500/15 rounded-xl p-4 space-y-2">
              <p className="text-sm">
                <span className="font-semibold">@{redeemPreview.creator_name}</span>{' '}
                {redeemPreview.creator_role === 'buyer' ? t('escrow.invite_role_buyer') : t('escrow.invite_role_seller')}
              </p>
              <p className="text-sm text-dark-200 font-medium">{redeemPreview.title}</p>
              {redeemPreview.description && <p className="text-xs text-dark-400">{redeemPreview.description}</p>}
              <p className="text-lg font-bold font-mono text-primary-400">${redeemPreview.amount.toFixed(2)}</p>
              <Button variant="primary" className="w-full" onClick={handleAcceptInvite} disabled={redeemBusy}>
                {redeemBusy ? t('escrow.creating') : t('escrow.invite_accept_btn', { role: redeemPreview.creator_role === 'buyer' ? t('escrow.invite_as_seller') : t('escrow.invite_as_buyer') })}
              </Button>
            </div>
          )}

          {/* Create an invite */}
          <AnimatePresence>
            {showInvite && !createdInvite && (
              <motion.form
                initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }}
                className="overflow-hidden space-y-3"
                onSubmit={handleCreateInvite}
              >
                <FormSelect label={t('escrow.invite_your_role')} value={inviteForm.role} onChange={e => setInviteForm({ ...inviteForm, role: e.target.value })}>
                  <option value="buyer">{t('escrow.invite_i_buy')}</option>
                  <option value="seller">{t('escrow.invite_i_sell')}</option>
                </FormSelect>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <FormInput label={t('escrow.deal_title')} placeholder={t('escrow.deal_title_ph')} value={inviteForm.title}
                    onChange={e => setInviteForm({ ...inviteForm, title: e.target.value })} required />
                  <FormInput label={t('escrow.amount_usd')} placeholder="0.00" type="number" step="0.01" min="0.01" value={inviteForm.amount}
                    onChange={e => setInviteForm({ ...inviteForm, amount: e.target.value })} required />
                </div>
                <FormSelect label={t('escrow.hold_period')} value={inviteHold} onChange={e => setInviteHold(parseInt(e.target.value))}>
                  <option value={0}>{t('escrow.hold_none')}</option>
                  <option value={1}>{t('escrow.hold_24h')}</option>
                  <option value={2}>{t('escrow.hold_48h')}</option>
                  <option value={7}>{t('escrow.hold_7d')}</option>
                  <option value={14}>{t('escrow.hold_14d')}</option>
                  <option value={30}>{t('escrow.hold_30d')}</option>
                </FormSelect>
                <FormTextarea label={t('escrow.description_optional')} placeholder={t('escrow.description_ph')} value={inviteForm.description}
                  onChange={e => setInviteForm({ ...inviteForm, description: e.target.value })} rows={2} />
                <Button type="submit" variant="primary" className="w-full" disabled={inviteBusy}>
                  {inviteBusy ? t('escrow.creating') : t('escrow.invite_generate_btn')}
                </Button>
              </motion.form>
            )}
          </AnimatePresence>

          {createdInvite && (
            <div className="bg-primary-500/10 border border-primary-500/30 rounded-xl p-4 text-center space-y-2">
              <p className="text-xs text-dark-300">{t('escrow.invite_share_hint')}</p>
              <p className="text-2xl font-bold font-mono tracking-[0.3em] text-primary-300">{createdInvite.code}</p>
              <div className="flex justify-center gap-2">
                <Button variant="secondary" size="sm" icon={codeCopied ? Check : Copy} onClick={copyInviteCode}>
                  {codeCopied ? t('escrow.invite_copied') : t('escrow.invite_copy')}
                </Button>
                <Button variant="ghost" size="sm" onClick={() => setCreatedInvite(null)}>{t('common.close')}</Button>
              </div>
              <p className="text-[10px] text-dark-500">{t('escrow.invite_expires')}</p>
            </div>
          )}
        </Card>
      )}

      {/* Deal List */}
      {loading ? (
        <LoadingState label={t('escrow.loading_deals')} />
      ) : error && deals.length === 0 ? (
        <Card className="text-center py-16">
          <p className="text-dark-500 text-sm mb-4">{t(error)}</p>
          <Button variant="primary" onClick={() => { setError(null); setLoading(true); loadDeals() }}>{t('common.retry')}</Button>
        </Card>
      ) : deals.length === 0 ? (
        <Card className="text-center py-16">
          <EmptyState icon={Shield}>{t('escrow.empty')}</EmptyState>
          <p className="text-dark-500 text-sm">{t('escrow.empty_hint')}</p>
        </Card>
      ) : (
        <div className="space-y-2">
          {deals.map(deal => {
            const myRole = deal.buyer_id === user?.id ? 'buyer' : deal.seller_id === user?.id ? 'seller' : null
            return (
              <Link key={deal.id} to={`/escrow/${deal.id}`} className="block">
                <Card className="hover:border-primary-500/30">
                  <div className="flex items-start gap-3">
                    {/* Role badge */}
                    <div className={`flex-shrink-0 w-9 h-9 rounded-xl flex items-center justify-center ${
                      myRole === 'buyer' ? 'bg-blue-500/10 text-blue-400' :
                      myRole === 'seller' ? 'bg-purple-500/10 text-purple-400' :
                      'bg-dark-700 text-dark-400'
                    }`}>
                      <User size={16} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-0.5">
                        <h3 className="font-semibold text-sm truncate">{deal.title}</h3>
                        <StatusBadge status={deal.status} />
                        {myRole && (
                          <Tag tone={myRole === 'buyer' ? 'cyan' : 'purple'}>{t(`escrow.role_${myRole}`)}</Tag>
                        )}
                      </div>
                      <p className="text-xs text-dark-400">
                        {deal.buyer_id === user?.id ? t('escrow.you') : `@${deal.buyer_username}`} → {deal.seller_id === user?.id ? t('escrow.you_lc') : `@${deal.seller_username}`}
                        <span className="text-dark-600 mx-1.5">·</span>
                        {timeAgo(deal.created_at)}
                        {deal.hold_days > 0 && (
                          <span className="text-amber-500/80 ml-1">· {t('escrow.hold_tag', { label: HOLD_LABEL_KEYS[deal.hold_days] ? t(HOLD_LABEL_KEYS[deal.hold_days]) : `${deal.hold_days}d` })}</span>
                        )}
                      </p>
                    </div>
                    <div className="text-right flex-shrink-0">
                      <p className="font-bold font-mono text-primary-400 text-sm">${deal.amount.toFixed(2)}</p>
                      {deal.fee_amount > 0 && (
                        <p className="text-[10px] text-dark-500">{t('escrow.fee_tag', { fee: `$${deal.fee_amount.toFixed(2)}` })}</p>
                      )}
                    </div>
                  </div>
                </Card>
              </Link>
            )
          })}
        </div>
      )}
    </div>
  )
}
