import { useState, useEffect } from 'react'
import { Plus, Trophy, Users, Trash2, Pencil } from 'lucide-react'
import api from '../../lib/api'
import { Card, SectionHeader, Button, FormInput, FormTextarea, Toggle, StatusBadge, EmptyState, LoadingState, Modal } from '../../components/admin/ui'

export default function AdminGiveaways({ showToast, showConfirm }) {
  const [giveawaysList, setGiveawaysList] = useState([])
  const [giveawayEntries, setGiveawayEntries] = useState({})
  const [giveawayForm, setGiveawayForm] = useState({ title: '', description: '', prize: '', enabled: true, deposit_required: false })
  const [loading, setLoading] = useState(true)
  const [editForm, setEditForm] = useState(null) // {id, title, description, prize, enabled, deposit_required} | null
  const [editSaving, setEditSaving] = useState(false)

  const loadGiveaways = async () => {
    setLoading(true)
    try {
      const res = await api.get('/api/giveaways/admin')
      setGiveawaysList(res.data)
    } catch (err) { import.meta.env.DEV && console.error(err) } finally { setLoading(false) }
  }

  useEffect(() => { loadGiveaways() }, [])

  const handleCreateGiveaway = async (e) => {
    e.preventDefault()
    try {
      await api.post('/api/giveaways/admin', giveawayForm)
      showToast('Giveaway created', 'success')
      setGiveawayForm({ title: '', description: '', prize: '', enabled: true, deposit_required: false })
      loadGiveaways()
    } catch (err) { showToast(err.response?.data?.detail || 'Failed', 'error') }
  }

  const handleDeleteGiveaway = (id) => {
    showConfirm(
      'Delete this giveaway?',
      async () => {
        try {
          await api.delete(`/api/giveaways/admin/${id}`)
          showToast('Giveaway deleted', 'success')
          loadGiveaways()
        } catch (err) {
          showToast(err.response?.data?.detail || 'Failed', 'error')
        }
      }
    )
  }

  const handlePickWinner = async (id) => {
    try {
      const res = await api.post(`/api/giveaways/admin/${id}/pick-winner`)
      showToast(`Winner: ${res.data.winner?.username || res.data.winner?.first_name || 'picked'}`, 'success')
      loadGiveaways()
    } catch (err) { showToast(err.response?.data?.detail || 'Failed', 'error') }
  }

  const handleSaveEdit = async () => {
    setEditSaving(true)
    try {
      const { id, ...payload } = editForm
      await api.put(`/api/giveaways/admin/${id}`, payload)
      showToast('Giveaway updated', 'success')
      setEditForm(null)
      loadGiveaways()
    } catch (err) {
      showToast(err.response?.data?.detail || 'Failed', 'error')
    } finally {
      setEditSaving(false)
    }
  }

  const loadGiveawayEntries = async (id) => {
    try {
      const res = await api.get(`/api/giveaways/admin/${id}/entries`)
      setGiveawayEntries(prev => ({ ...prev, [id]: res.data }))
    } catch (err) { import.meta.env.DEV && console.error(err) }
  }

  return (
    <div className="space-y-6">
      <Card>
        <SectionHeader>NEW_GIVEAWAY</SectionHeader>
        <form onSubmit={handleCreateGiveaway} className="space-y-3">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <FormInput label="title" type="text" placeholder="Title" value={giveawayForm.title} onChange={e => setGiveawayForm({ ...giveawayForm, title: e.target.value })} required />
            <FormInput label="prize" type="text" placeholder="Prize" value={giveawayForm.prize} onChange={e => setGiveawayForm({ ...giveawayForm, prize: e.target.value })} required />
            <div className="flex items-center gap-4 pt-5">
              <Toggle checked={giveawayForm.enabled} onChange={e => setGiveawayForm({ ...giveawayForm, enabled: e.target.checked })} label="Enabled" />
              <Toggle checked={giveawayForm.deposit_required} onChange={e => setGiveawayForm({ ...giveawayForm, deposit_required: e.target.checked })} label="Deposit Required" />
            </div>
          </div>
          <FormTextarea label="description" placeholder="Description" value={giveawayForm.description} onChange={e => setGiveawayForm({ ...giveawayForm, description: e.target.value })} rows={2} />
          <Button type="submit" variant="primary" size="sm" icon={Plus}>Create Giveaway</Button>
        </form>
      </Card>

      {loading ? (
        <LoadingState label="loading_giveaways" />
      ) : (
        <div className="space-y-3">
          {giveawaysList.map(g => (
            <Card key={g.id}>
              <div className="flex items-center justify-between mb-2">
                <div>
                  <h4 className="font-semibold text-sm">{g.title}</h4>
                  <p className="text-dark-400 text-xs font-mono">{g.prize} · {g.participant_count || 0} entries</p>
                </div>
                <div className="flex items-center gap-2">
                  <StatusBadge status={g.enabled ? 'active' : 'disabled'} />
                  {g.winner && <span className="text-xs font-mono bg-yellow-500/20 text-yellow-400 px-2 py-0.5 rounded">Winner: {g.winner.username || g.winner.first_name}</span>}
                </div>
              </div>
              <div className="flex gap-2">
                {!g.winner && <Button variant="neon" size="xs" icon={Trophy} onClick={() => handlePickWinner(g.id)}>Pick Winner</Button>}
                <Button
                  variant="secondary" size="xs" icon={Pencil}
                  onClick={() => setEditForm({
                    id: g.id,
                    title: g.title || '',
                    description: g.description || '',
                    prize: g.prize || '',
                    enabled: !!g.enabled,
                    deposit_required: !!g.deposit_required,
                  })}
                >
                  Edit
                </Button>
                <Button variant="secondary" size="xs" icon={Users} onClick={() => loadGiveawayEntries(g.id)}>View Entries</Button>
                <Button variant="danger" size="xs" icon={Trash2} onClick={() => handleDeleteGiveaway(g.id)}>Delete</Button>
              </div>
              {giveawayEntries[g.id] && (
                <div className="mt-3 pt-3 border-t border-dark-700/50">
                  <p className="text-xs font-mono text-dark-400 mb-1">{giveawayEntries[g.id].length} entries:</p>
                  <div className="flex flex-wrap gap-2">
                    {giveawayEntries[g.id].map(e => (
                      <span key={e.id} className="bg-dark-800/60 border border-primary-500/15 rounded px-2 py-1 font-mono text-xs">{e.display_name || e.username}</span>
                    ))}
                  </div>
                </div>
              )}
            </Card>
          ))}
          {giveawaysList.length === 0 && <EmptyState>no_giveaways</EmptyState>}
        </div>
      )}

      {/* Edit modal */}
      <Modal open={!!editForm} onClose={() => setEditForm(null)} title="EDIT_GIVEAWAY">
        {editForm && (
          <div className="space-y-3">
            <FormInput label="title" type="text" value={editForm.title} onChange={e => setEditForm({ ...editForm, title: e.target.value })} />
            <FormInput label="prize" type="text" value={editForm.prize} onChange={e => setEditForm({ ...editForm, prize: e.target.value })} />
            <FormTextarea label="description" value={editForm.description} onChange={e => setEditForm({ ...editForm, description: e.target.value })} rows={2} />
            <div className="flex items-center gap-4">
              <Toggle checked={editForm.enabled} onChange={e => setEditForm({ ...editForm, enabled: e.target.checked })} label="Enabled" />
              <Toggle checked={editForm.deposit_required} onChange={e => setEditForm({ ...editForm, deposit_required: e.target.checked })} label="Deposit Required" />
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="ghost" size="sm" onClick={() => setEditForm(null)}>Cancel</Button>
              <Button variant="primary" size="sm" onClick={handleSaveEdit} disabled={editSaving || !editForm.title.trim()}>
                {editSaving ? 'Saving…' : 'Save'}
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}
