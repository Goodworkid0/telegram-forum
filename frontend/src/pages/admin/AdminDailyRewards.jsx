import { useState, useEffect } from 'react'
import api from '../../lib/api'
import { t } from '../../lib/i18n'
import { Card, SectionHeader, Button, FormInput, FormSelect, Toggle, EmptyState } from '../../components/admin/ui'

export default function AdminDailyRewards({ showToast, showConfirm }) {
  const [dailyRewardConfigs, setDailyRewardConfigs] = useState([])
  const [drForm, setDrForm] = useState({ day: '', xp_amount: 10, balance_amount: 0.10, badge_id: '', is_active: true })
  const [editingDrDay, setEditingDrDay] = useState(null)
  const [allBadges, setAllBadges] = useState([])

  const loadDailyRewardConfig = async () => {
    try { const { data } = await api.get('/api/admin/daily-rewards/config'); setDailyRewardConfigs(data) }
    catch { showToast(t('common.load_failed'), 'error') }
  }

  const loadAllBadges = async () => {
    try { const { data } = await api.get('/api/admin/badges'); setAllBadges(data) }
    catch { showToast(t('common.load_failed'), 'error') }
  }

  useEffect(() => { loadDailyRewardConfig(); loadAllBadges() }, [])

  const handleCreateDrConfig = async (e) => {
    e.preventDefault()
    try {
      await api.post('/api/admin/daily-rewards/config', {
        day: parseInt(drForm.day),
        xp_amount: drForm.xp_amount,
        balance_amount: drForm.balance_amount,
        badge_id: drForm.badge_id ? parseInt(drForm.badge_id) : null,
        is_active: drForm.is_active,
      })
      setDrForm({ day: '', xp_amount: 10, balance_amount: 0.10, badge_id: '', is_active: true })
      loadDailyRewardConfig()
      showToast('Daily reward config added', 'success')
    } catch (err) { showToast(err.response?.data?.detail || 'Failed', 'error') }
  }

  const handleUpdateDrConfig = async (day) => {
    try {
      await api.put(`/api/admin/daily-rewards/config/${day}`, {
        xp_amount: drForm.xp_amount,
        balance_amount: drForm.balance_amount,
        badge_id: drForm.badge_id ? parseInt(drForm.badge_id) : null,
        is_active: drForm.is_active,
      })
      setEditingDrDay(null)
      setDrForm({ day: '', xp_amount: 10, balance_amount: 0.10, badge_id: '', is_active: true })
      loadDailyRewardConfig()
      showToast('Daily reward config updated', 'success')
    } catch (err) { showToast(err.response?.data?.detail || 'Failed', 'error') }
  }

  const handleDeleteDrConfig = async (day) => {
    showConfirm(`Delete daily reward config for day ${day}?`, async () => {
      try {
        await api.delete(`/api/admin/daily-rewards/config/${day}`)
        loadDailyRewardConfig()
        showToast('Deleted', 'success')
      } catch (err) { showToast(err.response?.data?.detail || 'Failed', 'error') }
    })
  }

  return (
    <div className="space-y-6">
      <Card as="form" onSubmit={editingDrDay ? (e) => { e.preventDefault(); handleUpdateDrConfig(editingDrDay) } : handleCreateDrConfig} className="space-y-3">
        <SectionHeader>{editingDrDay ? `Edit Day ${editingDrDay}` : 'Add Day Reward'}</SectionHeader>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          {!editingDrDay && (
            <FormInput label="Day #" type="number" placeholder="Day #" value={drForm.day} onChange={e => setDrForm({ ...drForm, day: e.target.value })} required min="1" />
          )}
          <FormInput label="XP Amount" type="number" placeholder="XP Amount" value={drForm.xp_amount} onChange={e => setDrForm({ ...drForm, xp_amount: parseInt(e.target.value) || 0 })} min="0" />
          <FormInput label="Balance $" type="number" step="0.01" placeholder="Balance $" value={drForm.balance_amount} onChange={e => setDrForm({ ...drForm, balance_amount: parseFloat(e.target.value) || 0 })} min="0" />
          <FormSelect label="Badge" value={drForm.badge_id} onChange={e => setDrForm({ ...drForm, badge_id: e.target.value })}>
            <option value="">No badge</option>
            {allBadges.map(b => <option key={b.id} value={b.id}>{b.name}</option>)}
          </FormSelect>
          <Toggle checked={drForm.is_active} onChange={e => setDrForm({ ...drForm, is_active: e.target.checked })} label="Active" className="self-end pb-2.5" />
        </div>
        <div className="flex gap-2">
          <Button type="submit" variant="primary" size="sm">
            {editingDrDay ? 'Update' : 'Add'}
          </Button>
          {editingDrDay && (
            <Button type="button" variant="ghost" size="sm" onClick={() => { setEditingDrDay(null); setDrForm({ day: '', xp_amount: 10, balance_amount: 0.10, badge_id: '', is_active: true }) }}>
              Cancel
            </Button>
          )}
        </div>
      </Card>

      <div className="space-y-2">
        <SectionHeader>Reward Tiers</SectionHeader>
        {dailyRewardConfigs.length === 0 ? (
          <EmptyState>no_tiers</EmptyState>
        ) : (
          <Card className="!p-0 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left font-mono text-[10px] uppercase tracking-widest text-primary-400/70">
                  <th className="px-3 py-2">Day</th>
                  <th className="px-3 py-2">XP</th>
                  <th className="px-3 py-2">Balance</th>
                  <th className="px-3 py-2">Badge</th>
                  <th className="px-3 py-2">Active</th>
                  <th className="px-3 py-2">Actions</th>
                </tr>
              </thead>
              <tbody>
                {dailyRewardConfigs.map(cfg => (
                  <tr key={cfg.id} className="border-t border-primary-500/10 hover:bg-dark-800/50">
                    <td className="px-3 py-2 font-medium font-mono">Day {cfg.day}</td>
                    <td className="px-3 py-2 text-yellow-400 font-mono">+{cfg.xp_amount}</td>
                    <td className="px-3 py-2 text-green-400 font-mono">${cfg.balance_amount.toFixed(2)}</td>
                    <td className="px-3 py-2">{cfg.badge_name ? <span className="text-primary-400 text-xs">{cfg.badge_name}</span> : <span className="text-dark-500">-</span>}</td>
                    <td className="px-3 py-2">
                      <span className={`text-xs px-2 py-0.5 rounded ${cfg.is_active ? 'bg-green-500/20 text-green-400' : 'bg-dark-600 text-dark-400'}`}>
                        {cfg.is_active ? 'Yes' : 'No'}
                      </span>
                    </td>
                    <td className="px-3 py-2">
                      <div className="flex gap-2">
                        <Button variant="secondary" size="xs" onClick={() => { setEditingDrDay(cfg.day); setDrForm({ day: cfg.day, xp_amount: cfg.xp_amount, balance_amount: cfg.balance_amount, badge_id: cfg.badge_id || '', is_active: cfg.is_active }) }}>Edit</Button>
                        <Button variant="danger" size="xs" onClick={() => handleDeleteDrConfig(cfg.day)}>Delete</Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        )}
      </div>

      <div className="bg-dark-800/50 p-4 rounded-xl text-sm text-dark-400">
        <p><strong className="text-dark-300">How it works:</strong> When a user claims their daily reward on streak day N, they receive the config for the highest day less than or equal to N. For example, if day 7 gives 20 XP and day 30 gives 50 XP, a user on day 15 gets the day 7 reward (20 XP).</p>
      </div>
    </div>
  )
}
