import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Send, ArrowLeft, AlertTriangle, Clock, User, DollarSign, CheckCircle, XCircle, Info, MessageSquare } from 'lucide-react'
import api from '../lib/api'
import { useToast } from '../components/Toast'
import { useAuthStore } from '../store/authStore'
import { timeAgo, parseDate } from '../lib/utils'
import { Card, Button, StatusBadge, FormInput, FormTextarea, LoadingState } from '../components/ui'
import { globalConfirm } from '../components/ConfirmModal'
import { useT } from '../lib/i18n'

const PROGRESS_STEPS = ['pending', 'accepted', 'funded', 'delivered', 'completed']
const STEP_LABEL_KEYS = { pending: 'escrow.step_pending', accepted: 'escrow.step_accepted', funded: 'escrow.step_funded', delivered: 'escrow.step_delivered', completed: 'escrow.step_completed' }

export default function EscrowDeal() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { user, isModerator } = useAuthStore()
  const { showToast } = useToast()
  const t = useT()
  const [deal, setDeal] = useState(null)
  const [loading, setLoading] = useState(true)
  const [message, setMessage] = useState('')
  const [sending, setSending] = useState(false)
  const [disputeReason, setDisputeReason] = useState('')
  const [showDispute, setShowDispute] = useState(false)
  const [resolveNote, setResolveNote] = useState('')
  const [repComment, setRepComment] = useState('')
  const [repGiven, setRepGiven] = useState(false)
  const [countdown, setCountdown] = useState('')
  const [busy, setBusy] = useState(false)
  const messagesEndRef = useRef(null)

  useEffect(() => { loadDeal() }, [id])
  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [deal?.messages])
  useEffect(() => {
    if (deal?.status !== 'funded' || !deal?.hold_ends_at) return
    const timer = setInterval(() => {
      const now = Date.now()
      const end = parseDate(deal.hold_ends_at).getTime()
      const diff = end - now
      if (diff <= 0) { setCountdown('expired'); clearInterval(timer); return }
      const d = Math.floor(diff / 86400000)
      const h = Math.floor((diff % 86400000) / 3600000)
      const m = Math.floor((diff % 3600000) / 60000)
      setCountdown(`${d}d ${h}h ${m}m`)
    }, 1000)
    return () => clearInterval(timer)
  }, [deal])

  const loadDeal = async () => {
    try {
      const res = await api.get(`/api/escrow/deals/${id}`)
      setDeal(res.data)
    } catch (err) {
      showToast(t('escrow.toast_not_found'), 'error')
      navigate("/escrow")
    } finally { setLoading(false) }
  }

  const doAction = async (action, { body = null, confirm = null } = {}) => {
    if (busy) return
    if (confirm && !(await globalConfirm(confirm))) return
    setBusy(true)
    try {
      await api.post(`/api/escrow/deals/${id}/${action}`, body)
      showToast(t('escrow.toast_action_done'), 'success')
      await loadDeal()
    } catch (err) {
      showToast(err.response?.data?.detail || t('escrow.toast_action_failed'), 'error')
    } finally {
      setBusy(false)
    }
  }

  const handleSendMessage = async (e) => {
    e.preventDefault()
    if (!message.trim()) return
    setSending(true)
    try {
      await api.post(`/api/escrow/deals/${id}/messages`, { content: message.trim() })
      setMessage('')
      loadDeal()
    } catch (err) {
      showToast(err.response?.data?.detail || t('escrow.toast_send_failed'), 'error')
    } finally { setSending(false) }
  }

  const giveRep = async (isPositive) => {
    if (busy) return
    const targetId = user?.id === deal.buyer_id ? deal.seller_id : deal.buyer_id
    setBusy(true)
    try {
      await api.post(`/api/reputation/users/${targetId}`, {
        is_positive: isPositive,
        comment: repComment.trim() || null,
        deal_id: deal.id,
      })
      setRepGiven(true)
      showToast(isPositive ? t('escrow.toast_rep_pos') : t('escrow.toast_rep_neg'), 'success')
    } catch (err) {
      showToast(err.response?.data?.detail || t('escrow.toast_rep_failed'), 'error')
    } finally {
      setBusy(false)
    }
  }

  const handleDispute = async () => {
    if (!disputeReason.trim()) return
    await doAction('dispute', { body: { content: disputeReason.trim() } })
    setShowDispute(false)
    setDisputeReason('')
  }

  if (loading) return <LoadingState label={t('escrow.loading_deal')} />
  if (!deal) return null

  const isBuyer = user?.id === deal.buyer_id
  const isSeller = user?.id === deal.seller_id
  const isClosed = ['completed', 'cancelled', 'refunded'].includes(deal.status)
  const currentStep = PROGRESS_STEPS.indexOf(deal.status)
  const net = deal.amount - (deal.fee_amount || 0)

  return (
    <div className="max-w-4xl mx-auto px-4 py-6 space-y-5">
      <button onClick={() => navigate("/escrow")} className="flex items-center gap-2 text-dark-400 hover:text-dark-200 text-sm transition-colors">
        <ArrowLeft size={16} /> {t('escrow.back_to_deals')}
      </button>

      {/* Deal Header Card */}
      <Card className="!p-0 overflow-hidden">
        <div className="p-5 space-y-4">
          {/* Title + Status */}
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <div className={`w-8 h-8 rounded-xl flex items-center justify-center ${isBuyer ? 'bg-blue-500/10 text-blue-400' : isSeller ? 'bg-purple-500/10 text-purple-400' : 'bg-dark-700 text-dark-400'}`}>
                  <User size={15} />
                </div>
                <h1 className="text-lg font-bold">{deal.title}</h1>
              </div>
              {deal.description && <p className="text-dark-400 text-sm ml-10">{deal.description}</p>}
            </div>
            <StatusBadge status={deal.status} className="!px-3 !py-1.5 !text-xs whitespace-nowrap" />
          </div>

          {/* Meta info row */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="bg-dark-950/60 rounded-xl p-3 border border-primary-500/10">
              <p className="text-[10px] text-dark-500 uppercase tracking-widest mb-0.5">{t('escrow.meta_deal_id')}</p>
              <p className="text-sm font-mono text-dark-300">#{deal.id}</p>
            </div>
            <div className="bg-dark-950/60 rounded-xl p-3 border border-primary-500/10">
              <p className="text-[10px] text-dark-500 uppercase tracking-widest mb-0.5">{t('escrow.meta_created')}</p>
              <p className="text-sm text-dark-300">{timeAgo(deal.created_at)}</p>
            </div>
            <div className="bg-dark-950/60 rounded-xl p-3 border border-primary-500/10">
              <p className="text-[10px] text-dark-500 uppercase tracking-widest mb-0.5">{t('escrow.meta_buyer')}</p>
              <p className="text-sm font-medium">@{deal.buyer_username} {isBuyer && <span className="text-[10px] text-blue-400 ml-1">{t('escrow.you_paren')}</span>}</p>
            </div>
            <div className="bg-dark-950/60 rounded-xl p-3 border border-primary-500/10">
              <p className="text-[10px] text-dark-500 uppercase tracking-widest mb-0.5">{t('escrow.meta_seller')}</p>
              <p className="text-sm font-medium">@{deal.seller_username} {isSeller && <span className="text-[10px] text-purple-400 ml-1">{t('escrow.you_paren')}</span>}</p>
            </div>
          </div>

          {/* Amount section */}
          <div className="bg-dark-950/60 rounded-xl p-4 border border-primary-500/10 font-mono">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-[10px] text-dark-500 uppercase tracking-widest mb-0.5">{t('escrow.amount_label')}</p>
                <p className="text-2xl font-bold text-primary-400">${deal.amount.toFixed(2)}</p>
              </div>
              <div className="text-right">
                {deal.fee_amount > 0 && (
                  <>
                    <p className="text-xs text-dark-500">{t('escrow.platform_fee', { fee: `$${deal.fee_amount.toFixed(2)}` })}</p>
                    <p className="text-sm font-semibold text-green-400">{t('escrow.seller_receives', { net: `$${net.toFixed(2)}` })}</p>
                  </>
                )}
                {deal.hold_days > 0 && deal.status === 'funded' && (
                  <p className="text-xs text-amber-400 mt-1">{t('escrow.locked_for', { days: deal.hold_days })}</p>
                )}
              </div>
            </div>
          </div>

          {/* Progress bar */}
          <div>
            <p className="text-[10px] text-dark-500 uppercase tracking-widest mb-2">{t('escrow.progress')}</p>
            <div className="flex items-center gap-1">
              {PROGRESS_STEPS.map((step, i) => {
                const done = i <= currentStep && currentStep >= 0
                const active = i === currentStep
                return (
                  <div key={step} className="flex items-center flex-1 last:flex-none">
                    <div className={`w-3 h-3 rounded-full flex-shrink-0 ${done ? 'bg-primary-500' : 'bg-dark-700'} ${active ? 'ring-2 ring-primary-500/40' : ''}`} />
                    {i < PROGRESS_STEPS.length - 1 && (
                      <div className={`flex-1 h-0.5 mx-0.5 ${done ? 'bg-primary-500/60' : 'bg-dark-700'}`} />
                    )}
                  </div>
                )
              })}
            </div>
            <div className="flex justify-between mt-1">
              {PROGRESS_STEPS.map((step, i) => (
                <span key={step} className={`text-[9px] ${i <= currentStep ? 'text-primary-400' : 'text-dark-600'}`}>{t(STEP_LABEL_KEYS[step])}</span>
              ))}
            </div>
          </div>

          {/* Status message */}
          <div className="flex items-center gap-2 text-sm">
            {deal.status === 'completed' ? (
              <CheckCircle size={16} className="text-green-400" />
            ) : deal.status === 'cancelled' ? (
              <XCircle size={16} className="text-dark-400" />
            ) : deal.status === 'disputed' ? (
              <AlertTriangle size={16} className="text-red-400" />
            ) : deal.status === 'refunded' ? (
              <XCircle size={16} className="text-orange-400" />
            ) : (
              <Clock size={16} className="text-primary-400" />
            )}
            <span className="text-dark-300">
              {deal.status === 'funded' && deal.hold_days
                ? t('escrow.status_funded_hold', { days: deal.hold_days })
                : {
                    pending: t('escrow.status_pending'),
                    accepted: t('escrow.status_accepted'),
                    funded: t('escrow.status_funded'),
                    delivered: t('escrow.status_delivered'),
                    completed: t('escrow.status_completed', { net: `$${net.toFixed(2)}` }),
                    disputed: t('escrow.status_disputed'),
                    cancelled: t('escrow.status_cancelled'),
                    refunded: t('escrow.status_refunded', { net: `$${net.toFixed(2)}` }),
                  }[deal.status]}
            </span>
          </div>

          {/* Hold countdown */}
          {countdown && (
            <div className={`flex items-center gap-2 text-sm rounded-xl px-4 py-2.5 ${countdown === 'expired' ? 'bg-green-500/10 text-green-400 border border-green-500/30' : 'bg-amber-500/10 text-amber-400 border border-amber-500/30'}`}>
              <Clock size={15} />
              <span className="font-medium">{countdown === 'expired' ? t('escrow.hold_expired') : t('escrow.hold_remaining', { time: countdown })}</span>
            </div>
          )}

          {/* Dispute info */}
          {deal.dispute_reason && (
            <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-3">
              <p className="text-xs text-red-400 font-semibold mb-1">{t('escrow.dispute_reason_label')}</p>
              <p className="text-sm text-red-300">{deal.dispute_reason}</p>
              {deal.dispute_by_id && (
                <p className="text-xs text-red-400/70 mt-1">{t('escrow.dispute_opened_by', { user: deal.dispute_by_id === deal.buyer_id ? deal.buyer_username : deal.seller_username })}</p>
              )}
            </div>
          )}

          {/* Admin resolution */}
          {deal.resolution_note && (
            <div className="bg-blue-500/10 border border-blue-500/30 rounded-xl p-3">
              <p className="text-xs text-blue-400 font-semibold mb-1">{t('escrow.admin_resolution')}</p>
              <p className="text-sm text-blue-300">{deal.resolution_note}</p>
            </div>
          )}

          {/* Rate your counterparty after the deal closes with money moved */}
          {['completed', 'refunded'].includes(deal.status) && (isBuyer || isSeller) && !repGiven && (
            <div className="bg-dark-950/60 border border-primary-500/15 rounded-xl p-4 space-y-3">
              <p className="text-sm font-semibold text-dark-200">
                {t('escrow.rate_user', { user: isBuyer ? deal.seller_username : deal.buyer_username })}
              </p>
              <p className="text-xs text-dark-400">{t('escrow.rate_hint')}</p>
              <FormInput
                placeholder={t('escrow.rep_comment_ph')}
                value={repComment}
                onChange={e => setRepComment(e.target.value)}
                maxLength={200}
              />
              <div className="flex gap-2">
                <Button onClick={() => giveRep(true)} disabled={busy} variant="secondary">{t('escrow.rep_plus')}</Button>
                <Button onClick={() => giveRep(false)} disabled={busy} variant="warn">{t('escrow.rep_minus')}</Button>
              </div>
            </div>
          )}

          {/* Action Buttons */}
          {!isClosed && (
            <div className="flex flex-wrap gap-2 pt-1">
              {isBuyer && deal.status === 'accepted' && (
                <Button onClick={() => doAction('fund', { confirm: t('escrow.fund_confirm', { amount: `$${deal.amount.toFixed(2)}` }) })} disabled={busy} variant="primary" icon={DollarSign}>{t('escrow.fund_btn', { amount: `$${deal.amount.toFixed(2)}` })}</Button>
              )}
              {isSeller && deal.status === 'funded' && (
                <Button onClick={() => doAction('deliver')} disabled={busy} variant="secondary">{t('escrow.mark_delivered')}</Button>
              )}
              {isBuyer && deal.status === 'delivered' && (
                <Button onClick={() => doAction('complete', { confirm: t('escrow.release_confirm', { net: `$${net.toFixed(2)}`, user: deal.seller_username }) })} disabled={busy} variant="neon" icon={CheckCircle}>{t('escrow.release_btn', { net: `$${net.toFixed(2)}` })}</Button>
              )}
              {(isBuyer || isSeller) && ['funded', 'delivered'].includes(deal.status) && (
                <Button onClick={() => setShowDispute(!showDispute)} disabled={busy} variant="warn" icon={AlertTriangle}>{t('escrow.dispute_btn')}</Button>
              )}
              {(isBuyer || isSeller) && ['pending', 'accepted'].includes(deal.status) && (
                <Button onClick={() => doAction('cancel', { confirm: t('escrow.cancel_confirm') })} disabled={busy} variant="ghost">{t('escrow.cancel_deal')}</Button>
              )}
            </div>
          )}

          {/* Moderator dispute resolution */}
          {deal.status === 'disputed' && isModerator() && (
            <div className="bg-blue-500/10 border border-blue-500/30 rounded-xl p-4 space-y-3">
              <div className="flex items-center gap-2">
                <AlertTriangle size={16} className="text-blue-400" />
                <p className="text-sm text-blue-400 font-semibold">{t('escrow.resolve_title')}</p>
              </div>
              <FormTextarea
                placeholder={t('escrow.resolve_note_ph')}
                value={resolveNote}
                onChange={e => setResolveNote(e.target.value)}
                rows={2}
              />
              <div className="flex flex-wrap gap-2">
                <Button
                  onClick={() => doAction('resolve', {
                    body: { release_to: 'seller', note: resolveNote.trim() || null },
                    confirm: t('escrow.release_seller_confirm', { net: `$${net.toFixed(2)}`, user: deal.seller_username }),
                  })}
                  disabled={busy} variant="primary" icon={CheckCircle}
                >
                  {t('escrow.release_to_seller')}
                </Button>
                <Button
                  onClick={() => doAction('resolve', {
                    body: { release_to: 'buyer', note: resolveNote.trim() || null },
                    confirm: t('escrow.refund_buyer_confirm', { amount: `$${deal.amount.toFixed(2)}`, user: deal.buyer_username }),
                  })}
                  disabled={busy} variant="warn" icon={XCircle}
                >
                  {t('escrow.refund_buyer')}
                </Button>
              </div>
            </div>
          )}

          {/* Dispute form */}
          {showDispute && (
            <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 space-y-3">
              <div className="flex items-center gap-2">
                <AlertTriangle size={16} className="text-red-400" />
                <p className="text-sm text-red-400 font-semibold">{t('escrow.open_dispute')}</p>
              </div>
              <FormTextarea
                placeholder={t('escrow.dispute_ph')}
                value={disputeReason}
                onChange={e => setDisputeReason(e.target.value)}
                rows={3}
              />
              <div className="flex gap-2">
                <Button onClick={handleDispute} disabled={!disputeReason.trim()} variant="danger">{t('escrow.submit_dispute')}</Button>
                <Button onClick={() => { setShowDispute(false); setDisputeReason('') }} variant="ghost">{t('common.cancel')}</Button>
              </div>
            </div>
          )}
        </div>
      </Card>

      {/* Messages */}
      <Card className="!p-0 overflow-hidden">
        <div className="px-5 py-3 border-b border-primary-500/15 flex items-center gap-2">
          <MessageSquare size={16} className="text-primary-400" />
          <h3 className="font-medium text-sm">{t('escrow.deal_chat')}</h3>
          <span className="text-[10px] text-dark-500 ml-auto">{t('escrow.messages_count', { count: deal.messages?.length || 0 })}</span>
        </div>
        <div className="p-4 space-y-3 max-h-96 overflow-y-auto">
          {(!deal.messages || deal.messages.length === 0) && (
            <div className="text-center py-8">
              <Info size={24} className="mx-auto text-dark-600 mb-2" />
              <p className="text-dark-500 text-sm">{t('escrow.no_messages')}</p>
            </div>
          )}
          {deal.messages?.map(msg => (
            <div key={msg.id} className={msg.is_system ? 'text-center' : ''}>
              {msg.is_system ? (
                <div className="flex items-center justify-center gap-2">
                  <div className="flex-1 h-px bg-dark-700/50 max-w-12" />
                  <p className="text-[11px] text-dark-500 italic px-2">{msg.content}</p>
                  <div className="flex-1 h-px bg-dark-700/50 max-w-12" />
                </div>
              ) : (
                <div className={`flex ${msg.sender_id === user?.id ? 'justify-end' : 'justify-start'}`}>
                  <div className={`max-w-[75%] rounded-xl px-4 py-2.5 ${msg.sender_id === user?.id ? 'bg-primary-500/15 border border-primary-500/20' : 'bg-dark-800/80 border border-primary-500/10'}`}>
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-[11px] font-semibold text-dark-400">@{msg.sender_username}</span>
                      <span className="text-[9px] text-dark-600">{parseDate(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                    </div>
                    <p className="text-sm leading-relaxed whitespace-pre-wrap break-words">{msg.content}</p>
                  </div>
                </div>
              )}
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>

        {!isClosed && (
          <form onSubmit={handleSendMessage} className="p-3 border-t border-primary-500/15 flex gap-2">
            <FormInput
              value={message}
              onChange={e => setMessage(e.target.value)}
              placeholder={t('escrow.message_ph')}
              className="flex-1"
              maxLength={2000}
            />
            <Button type="submit" disabled={sending || !message.trim()} variant="primary" icon={Send} className="flex-shrink-0" />
          </form>
        )}
      </Card>
    </div>
  )
}
