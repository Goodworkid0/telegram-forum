import { useState, useEffect } from 'react'
import { AlertTriangle } from 'lucide-react'
import api from '../../lib/api'
import { t as tr } from '../../lib/i18n'
import BadgeIcon from '../../components/BadgeIcon'
import IconPicker from '../../components/admin/IconPicker'
import { Card, SectionHeader, Button, FormInput, FormSelect, Toggle, EmptyState } from '../../components/admin/ui'
import {
  ACHIEVEMENT_TEMPLATES,
  CRITERIA_FIELDS,
  CRITERIA_FIELD_MAP,
  fillTemplateText,
} from '../../lib/achievementTemplates'

const EMPTY_FORM = {
  name: '', description: '', color: '#6366f1', icon_url: '', icon: '', icon_style: 'default',
  price: 0, is_purchasable: false, auto_award_criteria: '', reward_xp: 0, reward_balance: 0,
}

// Build the auto_award_criteria JSON string from a single field + threshold.
const buildCriteriaJSON = (field, threshold) => {
  if (!field) return ''
  const n = Number(threshold)
  return JSON.stringify({ [field]: Number.isFinite(n) ? n : 0 })
}

// Parse an existing criteria string back into {field, threshold} when it's a
// single-key rule the builder can represent; otherwise null (advanced/custom).
const parseCriteria = (raw) => {
  if (!raw) return null
  try {
    const obj = JSON.parse(raw)
    const keys = Object.keys(obj)
    if (keys.length === 1 && CRITERIA_FIELD_MAP[keys[0]]) {
      return { field: keys[0], threshold: obj[keys[0]] }
    }
  } catch {}
  return null
}

export default function AdminBadges({ showToast, showConfirm }) {
  const [badges, setBadges] = useState([])
  const [badgeForm, setBadgeForm] = useState(EMPTY_FORM)
  const [editingBadge, setEditingBadge] = useState(null)
  const [criteriaField, setCriteriaField] = useState('')
  const [criteriaThreshold, setCriteriaThreshold] = useState(0)
  const [activeTemplate, setActiveTemplate] = useState(null)
  const [showAdvanced, setShowAdvanced] = useState(false)

  const loadBadges = async () => {
    try {
      const { data } = await api.get('/api/admin/badges')
      setBadges(data)
    } catch { showToast(tr('common.load_failed'), 'error') }
  }

  useEffect(() => { loadBadges() }, [])

  const resetForm = () => {
    setBadgeForm(EMPTY_FORM)
    setCriteriaField('')
    setCriteriaThreshold(0)
    setActiveTemplate(null)
    setShowAdvanced(false)
    setEditingBadge(null)
  }

  const applyTemplate = (t) => {
    setActiveTemplate(t.id)
    setCriteriaField(t.field || '')
    setCriteriaThreshold(t.threshold || 0)
    setBadgeForm(prev => ({
      ...prev,
      name: t.name || prev.name,
      description: fillTemplateText(t.description, t.threshold),
      icon: t.icon,
      color: t.color,
      icon_style: t.icon_style,
      reward_xp: t.reward_xp || 0,
      auto_award_criteria: buildCriteriaJSON(t.field, t.threshold),
    }))
  }

  const changeCriteriaField = (field) => {
    setCriteriaField(field)
    setActiveTemplate(null)
    setBadgeForm(prev => ({ ...prev, auto_award_criteria: buildCriteriaJSON(field, criteriaThreshold) }))
  }

  const changeCriteriaThreshold = (val) => {
    setCriteriaThreshold(val)
    setBadgeForm(prev => ({ ...prev, auto_award_criteria: buildCriteriaJSON(criteriaField, val) }))
  }

  const handleBadgeIconUpload = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    const formData = new FormData()
    formData.append('file', file)
    try {
      const { data } = await api.post('/api/badges/upload-icon', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
      setBadgeForm(prev => ({ ...prev, icon_url: data.url }))
      showToast('Icon uploaded', 'success')
    } catch (err) {
      showToast(err.response?.data?.detail || 'Upload failed', 'error')
    }
  }

  const handleSubmitBadge = async (e) => {
    e.preventDefault()
    try {
      const payload = { ...badgeForm, auto_award_criteria: badgeForm.auto_award_criteria || null }
      if (editingBadge) {
        await api.put(`/api/badges/${editingBadge.id}`, payload)
        showToast('Badge updated', 'success')
      } else {
        await api.post('/api/admin/badges', payload)
        showToast('Badge created', 'success')
      }
      resetForm()
      await loadBadges()
    } catch (err) {
      showToast(err.response?.data?.detail || 'Failed', 'error')
    }
  }

  const startEdit = (b) => {
    const parsed = parseCriteria(b.auto_award_criteria)
    setEditingBadge(b)
    setActiveTemplate(null)
    setCriteriaField(parsed?.field || '')
    setCriteriaThreshold(parsed?.threshold ?? 0)
    setShowAdvanced(!!b.auto_award_criteria && !parsed)
    setBadgeForm({
      name: b.name, description: b.description || '', color: b.color || '#6366f1',
      icon_url: b.icon_url || '', icon: b.icon || '', icon_style: b.icon_style || 'default',
      price: b.price || 0, is_purchasable: b.is_purchasable || false,
      auto_award_criteria: b.auto_award_criteria || '', reward_xp: b.reward_xp || 0,
      reward_balance: b.reward_balance || 0,
    })
  }

  const handleDeleteBadge = (id) => {
    showConfirm('Delete this badge?', async () => {
      try {
        await api.delete(`/api/admin/badges/${id}`)
        showToast('Badge deleted', 'success')
        await loadBadges()
      } catch (err) {
        showToast(err.response?.data?.detail || 'Failed', 'error')
      }
    })
  }

  const selectedFieldMeta = CRITERIA_FIELD_MAP[criteriaField]
  const isStreak = criteriaField === 'login_streak'

  return (
    <div className="space-y-6">
      {/* Template gallery */}
      <Card className="space-y-3">
        <SectionHeader>start_from_template</SectionHeader>
        <p className="text-xs text-dark-400">Pick a template to prefill the form, then tweak anything below.</p>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
          {ACHIEVEMENT_TEMPLATES.map(t => (
            <button
              key={t.id}
              type="button"
              onClick={() => applyTemplate(t)}
              className={
                'flex items-center gap-2.5 rounded-lg border p-2.5 text-left transition-all ' +
                (activeTemplate === t.id
                  ? 'border-primary-500/60 bg-primary-500/10'
                  : 'border-primary-500/15 bg-dark-950/40 hover:border-primary-500/35 hover:bg-dark-800/50')
              }
            >
              <BadgeIcon icon={t.icon} iconStyle={t.icon_style} color={t.color} size={20} />
              <span className="min-w-0">
                <span className="block truncate text-sm font-medium text-white">{t.label}</span>
                <span className="block text-[10px] uppercase tracking-wider text-primary-400/60">{t.category}</span>
              </span>
            </button>
          ))}
        </div>
      </Card>

      {/* Badge editor */}
      <Card as="form" onSubmit={handleSubmitBadge} className="space-y-4">
        <SectionHeader>{editingBadge ? 'edit_badge' : 'new_badge'}</SectionHeader>

        {/* Live preview */}
        <div className="flex items-center gap-3 rounded-lg border border-primary-500/15 bg-dark-950/40 p-3">
          {badgeForm.icon_url
            ? <img src={badgeForm.icon_url} alt="" className="h-8 w-8 rounded object-cover" />
            : <BadgeIcon icon={badgeForm.icon} iconStyle={badgeForm.icon_style} color={badgeForm.color} size={28} />}
          <div className="min-w-0">
            <div className="truncate font-medium text-white">{badgeForm.name || 'Badge preview'}</div>
            <div className="truncate text-xs text-dark-400">{badgeForm.description || 'Description appears here'}</div>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <FormInput
            label="Name" type="text" placeholder="Name" value={badgeForm.name}
            onChange={e => setBadgeForm({ ...badgeForm, name: e.target.value })} required
          />
          <FormInput
            label="Description" type="text" placeholder="Description" value={badgeForm.description}
            onChange={e => setBadgeForm({ ...badgeForm, description: e.target.value })}
          />
        </div>

        {/* Visual icon picker */}
        <IconPicker
          value={badgeForm.icon}
          onChange={icon => setBadgeForm({ ...badgeForm, icon })}
          color={badgeForm.color}
          iconStyle={badgeForm.icon_style}
        />

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="mb-1 block font-mono text-[10px] uppercase tracking-widest text-primary-400/70">Color</label>
            <input
              type="color" value={badgeForm.color}
              onChange={e => setBadgeForm({ ...badgeForm, color: e.target.value })}
              className="h-10 w-full rounded-lg border border-primary-500/15 bg-dark-950/60"
            />
          </div>
          <FormSelect
            label="Icon Style" value={badgeForm.icon_style}
            onChange={e => setBadgeForm({ ...badgeForm, icon_style: e.target.value })}
          >
            <option value="default">Style: default</option>
            <option value="ring">Style: ring</option>
            <option value="glow">Style: glow</option>
            <option value="pulse">Style: pulse</option>
            <option value="sparkle">Style: sparkle</option>
          </FormSelect>
        </div>

        {/* Custom image upload (optional, overrides the Lucide icon) */}
        <div className="flex items-center gap-2">
          <label className="cursor-pointer rounded-lg border border-primary-500/20 bg-dark-800/80 px-3 py-2 text-sm text-dark-200 transition-all hover:border-primary-500/40 hover:bg-dark-700">
            Upload custom image
            <input type="file" accept="image/*" onChange={handleBadgeIconUpload} className="hidden" />
          </label>
          {badgeForm.icon_url && (
            <>
              <img src={badgeForm.icon_url} alt="" className="h-8 w-8 rounded object-cover" />
              <Button type="button" size="xs" variant="ghost" onClick={() => setBadgeForm({ ...badgeForm, icon_url: '' })}>
                Remove
              </Button>
            </>
          )}
        </div>

        {/* Auto-award criteria builder */}
        <div className="mt-3 border-t border-primary-500/15 pt-3">
          <h4 className="mb-2 font-mono text-xs uppercase tracking-widest text-primary-400/70">Auto-Award Rule</h4>
          <div className="grid grid-cols-2 gap-3">
            <FormSelect
              label="When user reaches…" value={criteriaField}
              onChange={e => changeCriteriaField(e.target.value)}
            >
              <option value="">No auto-award (manual / purchasable)</option>
              {CRITERIA_FIELDS.map(f => (
                <option key={f.value} value={f.value}>{f.label}</option>
              ))}
            </FormSelect>
            <FormInput
              label={`Threshold${selectedFieldMeta ? ` (${selectedFieldMeta.unit})` : ''}`}
              type="number" step="any" placeholder="0" value={criteriaThreshold}
              disabled={!criteriaField}
              onChange={e => changeCriteriaThreshold(e.target.value)}
            />
          </div>

          {criteriaField && (
            <p className="mt-2 text-[11px] text-primary-400/70">
              Awards automatically when <span className="text-primary-300">{selectedFieldMeta?.label}</span> ≥{' '}
              <span className="text-primary-300">{criteriaThreshold || 0}</span>. Granted once per user (checked every ~5 min).
            </p>
          )}

          {isStreak && (
            <p className="mt-2 flex items-start gap-1.5 text-[11px] text-amber-400/80">
              <AlertTriangle size={13} className="mt-0.5 shrink-0" />
              Login streak resets if the user misses a day — this means “{criteriaThreshold || 0} days in a row”, not total membership days.
            </p>
          )}

          {/* Advanced raw JSON escape hatch */}
          <button
            type="button"
            onClick={() => setShowAdvanced(v => !v)}
            className="mt-2 text-[11px] text-dark-400 underline-offset-2 hover:text-primary-300 hover:underline"
          >
            {showAdvanced ? 'Hide' : 'Advanced:'} raw JSON criteria
          </button>
          {showAdvanced && (
            <FormInput
              className="mt-2"
              label="Criteria (JSON) — for multi-condition rules"
              type="text" placeholder='{"post_count": 100, "like_count": 50}'
              value={badgeForm.auto_award_criteria}
              onChange={e => { setBadgeForm({ ...badgeForm, auto_award_criteria: e.target.value }); setActiveTemplate(null) }}
            />
          )}
        </div>

        {/* Rewards */}
        <div className="mt-3 border-t border-primary-500/15 pt-3">
          <h4 className="mb-2 font-mono text-xs uppercase tracking-widest text-primary-400/70">Rewards on Earn</h4>
          <div className="grid grid-cols-2 gap-3">
            <FormInput
              label="Reward XP" type="number" placeholder="0" value={badgeForm.reward_xp}
              onChange={e => setBadgeForm({ ...badgeForm, reward_xp: parseInt(e.target.value) || 0 })}
            />
            <FormInput
              label="Reward Balance $" type="number" step="0.01" placeholder="0.00" value={badgeForm.reward_balance}
              onChange={e => setBadgeForm({ ...badgeForm, reward_balance: parseFloat(e.target.value) || 0 })}
            />
          </div>
        </div>

        {/* Shop settings */}
        <div className="mt-3 grid grid-cols-2 items-end gap-3 border-t border-primary-500/15 pt-3">
          <Toggle
            checked={badgeForm.is_purchasable}
            onChange={e => setBadgeForm({ ...badgeForm, is_purchasable: e.target.checked })}
            label="Purchasable in shop"
          />
          {badgeForm.is_purchasable && (
            <FormInput
              label="Price $" type="number" step="0.01" placeholder="Price $" value={badgeForm.price}
              onChange={e => setBadgeForm({ ...badgeForm, price: parseFloat(e.target.value) || 0 })}
            />
          )}
        </div>

        <div className="flex gap-2">
          <Button type="submit" variant="primary">{editingBadge ? 'Update Badge' : 'Create'}</Button>
          {editingBadge && (
            <Button type="button" variant="ghost" onClick={resetForm}>Cancel</Button>
          )}
        </div>
      </Card>

      {/* Existing badges */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        {badges.length === 0 && <EmptyState className="col-span-2 md:col-span-4">no_badges</EmptyState>}
        {badges.map(b => (
          <Card key={b.id}>
            <div className="mb-2 flex items-center gap-2">
              {b.icon_url ? <img src={b.icon_url} alt="" className="h-5 w-5 rounded" /> : <BadgeIcon icon={b.icon} iconStyle={b.icon_style} color={b.color} size={16} />}
              <span className="font-medium">{b.name}</span>
            </div>
            <p className="mb-1 text-sm text-dark-400">{b.description}</p>
            {b.auto_award_criteria && (
              <p className="mb-1 truncate font-mono text-[10px] text-primary-400/70" title={b.auto_award_criteria}>
                {b.auto_award_criteria}
              </p>
            )}
            {(b.reward_xp > 0 || b.reward_balance > 0) && (
              <p className="mb-1 text-[10px] text-green-400/70">
                {b.reward_xp > 0 && `+${b.reward_xp} XP `}
                {b.reward_balance > 0 && `+$${b.reward_balance.toFixed(2)}`}
              </p>
            )}
            <div className="mt-2 flex items-center justify-between border-t border-primary-500/15 pt-2">
              <span className="text-sm">{b.is_purchasable ? `$${b.price}` : `${b.is_active ? 'Active' : 'Inactive'}`}</span>
              <div className="flex gap-2">
                <Button size="xs" variant="secondary" onClick={() => startEdit(b)}>Edit</Button>
                <Button size="xs" variant="danger" onClick={() => handleDeleteBadge(b.id)}>Delete</Button>
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  )
}
