import { useState } from 'react'
import { Flag } from 'lucide-react'
import api from '../lib/api'
import { useToast } from './Toast'
import { Modal, Button, FormSelect, FormTextarea } from './ui'
import { useT } from '../lib/i18n'

// `value` is the English string sent to POST /api/reports (moderators filter on
// it) — only the visible label is translated via `labelKey`.
const REASONS = [
  { value: 'Spam', labelKey: 'modals.report.reason_spam' },
  { value: 'Scam or fraud', labelKey: 'modals.report.reason_scam' },
  { value: 'Abusive behavior', labelKey: 'modals.report.reason_abuse' },
  { value: 'Illegal content', labelKey: 'modals.report.reason_illegal' },
  { value: 'Other', labelKey: 'modals.report.reason_other' },
]

const TARGET_KEYS = {
  post: 'modals.report.target_post',
  thread: 'modals.report.target_thread',
  user: 'modals.report.target_user',
}

/**
 * Report a post, thread, or user to the moderation queue.
 * reportType: 'post' | 'thread' | 'user'; targetId: id of that entity.
 */
export default function ReportModal({ open, onClose, reportType, targetId, targetLabel }) {
  const t = useT()
  const { showToast } = useToast()
  const [reason, setReason] = useState(REASONS[0].value)
  const [description, setDescription] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const submit = async () => {
    if (submitting) return
    setSubmitting(true)
    try {
      const body = { report_type: reportType, reason, description: description.trim() || null }
      if (reportType === 'post') body.post_id = targetId
      else if (reportType === 'thread') body.thread_id = targetId
      else body.reported_user_id = targetId
      await api.post('/api/reports', body)
      showToast(t('modals.report.submitted'), 'success')
      setDescription('')
      setReason(REASONS[0].value)
      onClose()
    } catch (err) {
      showToast(err.response?.data?.detail || t('modals.report.failed'), 'error')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal open={open} onClose={onClose} title={t('common.report')}>
      <div className="space-y-4">
        <p className="text-sm text-dark-300 flex items-center gap-2">
          <Flag size={15} className="text-red-400 flex-shrink-0" />
          <span>{t('modals.report.intro', { target: targetLabel || (TARGET_KEYS[reportType] ? t(TARGET_KEYS[reportType]) : reportType) })}</span>
        </p>
        <FormSelect label={t('modals.report.reason')} value={reason} onChange={e => setReason(e.target.value)}>
          {REASONS.map(r => <option key={r.value} value={r.value}>{t(r.labelKey)}</option>)}
        </FormSelect>
        <FormTextarea
          label={t('modals.report.details')}
          placeholder={t('modals.report.details_ph')}
          value={description}
          onChange={e => setDescription(e.target.value)}
          rows={3}
          maxLength={2000}
        />
        <div className="flex gap-2 justify-end">
          <Button variant="ghost" onClick={onClose}>{t('common.cancel')}</Button>
          <Button variant="danger" onClick={submit} disabled={submitting} icon={Flag}>
            {submitting ? t('modals.report.submitting') : t('modals.report.submit')}
          </Button>
        </div>
      </div>
    </Modal>
  )
}
