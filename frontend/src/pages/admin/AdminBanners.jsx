import { useState, useEffect } from 'react'
import api from '../../lib/api'
import { Card, SectionHeader, Button, FormInput, FormSelect, Toggle, EmptyState } from '../../components/admin/ui'

export default function AdminBanners({ showToast, showConfirm }) {
  const [bannersList, setBannersList] = useState([])
  const [bannerForm, setBannerForm] = useState({ title: '', subtitle: '', link: '', link_text: '', gradient_from: '#6366f1', gradient_to: '#8b5cf6', position: 'home_row_1', is_active: true, sort_order: 0 })
  const [editingBannerId, setEditingBannerId] = useState(null)

  const loadBanners = async () => {
    try {
      const res = await api.get('/api/banners/admin/all')
      setBannersList(res.data)
    } catch (err) { import.meta.env.DEV && console.error(err) }
  }

  useEffect(() => { loadBanners() }, [])

  const resetBannerForm = () => {
    setBannerForm({ title: '', subtitle: '', link: '', link_text: '', gradient_from: '#6366f1', gradient_to: '#8b5cf6', position: 'home_row_1', is_active: true, sort_order: 0 })
    setEditingBannerId(null)
  }

  const handleBannerSubmit = async (e) => {
    e.preventDefault()
    try {
      if (editingBannerId) {
        await api.put(`/api/banners/admin/${editingBannerId}`, bannerForm)
        showToast('Banner updated', 'success')
      } else {
        await api.post('/api/banners/admin', bannerForm)
        showToast('Banner created', 'success')
      }
      resetBannerForm()
      loadBanners()
    } catch (err) { showToast(err.response?.data?.detail || 'Failed', 'error') }
  }

  const handleEditBanner = (banner) => {
    setBannerForm({
      title: banner.title || '',
      subtitle: banner.subtitle || '',
      link: banner.link || '',
      link_text: banner.link_text || '',
      gradient_from: banner.gradient_from || '#6366f1',
      gradient_to: banner.gradient_to || '#8b5cf6',
      position: banner.position || 'home_row_1',
      is_active: banner.is_active,
      sort_order: banner.sort_order ?? 0
    })
    setEditingBannerId(banner.id)
  }

  const handleDeleteBanner = (id) => {
    showConfirm(
      'Delete this banner?',
      async () => {
        try {
          await api.delete(`/api/banners/admin/${id}`)
          showToast('Banner deleted', 'success')
          loadBanners()
        } catch (err) {
          showToast(err.response?.data?.detail || 'Failed', 'error')
        }
      }
    )
  }

  const handleBannerImageUpload = async (bannerId, e) => {
    const file = e.target.files?.[0]
    if (!file) return
    const formData = new FormData()
    formData.append('file', file)
    try {
      await api.post(`/api/banners/admin/${bannerId}/upload`, formData, { headers: { 'Content-Type': 'multipart/form-data' } })
      showToast('Banner image uploaded', 'success')
      loadBanners()
    } catch (err) { showToast(err.response?.data?.detail || 'Failed', 'error') }
  }

  return (
    <div className="space-y-6">
      <Card>
        <SectionHeader>{editingBannerId ? 'Edit Banner' : 'Create Banner'}</SectionHeader>
        <form onSubmit={handleBannerSubmit} className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <FormInput label="Title" placeholder="Title" value={bannerForm.title} onChange={e => setBannerForm({ ...bannerForm, title: e.target.value })} required />
          <FormInput label="Subtitle" placeholder="Subtitle" value={bannerForm.subtitle} onChange={e => setBannerForm({ ...bannerForm, subtitle: e.target.value })} />
          <FormInput label="Link URL" placeholder="Link URL" value={bannerForm.link} onChange={e => setBannerForm({ ...bannerForm, link: e.target.value })} />
          <FormInput label="Link Text" placeholder="Link Text" value={bannerForm.link_text} onChange={e => setBannerForm({ ...bannerForm, link_text: e.target.value })} />
          <FormSelect label="Position" value={bannerForm.position} onChange={e => setBannerForm({ ...bannerForm, position: e.target.value })}>
            <option value="home_row_1">Position: Row 1</option>
            <option value="home_row_2">Position: Row 2</option>
            <option value="home_row_3">Position: Row 3</option>
            <option value="home_row_4">Position: Row 4</option>
          </FormSelect>
          <div className="flex items-end gap-4">
            <div>
              <label className="mb-1 block font-mono text-[10px] uppercase tracking-widest text-primary-400/70">From</label>
              <input type="color" value={bannerForm.gradient_from} onChange={e => setBannerForm({ ...bannerForm, gradient_from: e.target.value })} className="w-10 h-10 rounded cursor-pointer bg-transparent" />
            </div>
            <div>
              <label className="mb-1 block font-mono text-[10px] uppercase tracking-widest text-primary-400/70">To</label>
              <input type="color" value={bannerForm.gradient_to} onChange={e => setBannerForm({ ...bannerForm, gradient_to: e.target.value })} className="w-10 h-10 rounded cursor-pointer bg-transparent" />
            </div>
          </div>
          <div className="flex items-end gap-4">
            <FormInput label="Sort Order" type="number" placeholder="Sort Order" value={bannerForm.sort_order} onChange={e => setBannerForm({ ...bannerForm, sort_order: parseInt(e.target.value) || 0 })} className="w-28" />
            <Toggle checked={bannerForm.is_active} onChange={e => setBannerForm({ ...bannerForm, is_active: e.target.checked })} label="Active" className="pb-2.5" />
          </div>
          <div className="md:col-span-2 flex items-center gap-3">
            <Button type="submit" variant="primary">
              {editingBannerId ? 'Update Banner' : 'Create Banner'}
            </Button>
            {editingBannerId && (
              <Button type="button" variant="ghost" onClick={resetBannerForm}>
                Cancel
              </Button>
            )}
          </div>
        </form>
      </Card>
      <div className="space-y-3">
        {bannersList.map(b => (
          <Card key={b.id} className="flex items-center gap-4">
            {b.image_url ? (
              <img src={b.image_url} alt={b.title} className="w-24 h-14 object-cover rounded-lg" />
            ) : (
              <div className="w-24 h-14 rounded-lg" style={{ background: `linear-gradient(to right, ${b.gradient_from || '#6366f1'}, ${b.gradient_to || '#8b5cf6'})` }} />
            )}
            <div className="flex-1 min-w-0">
              <p className="font-medium text-sm">{b.title}</p>
              {b.subtitle && <p className="text-dark-400 text-sm truncate">{b.subtitle}</p>}
              <p className="text-dark-500 text-xs font-mono">Order: {b.sort_order} | {b.position || '—'} | {b.is_active ? 'Active' : 'Inactive'}</p>
            </div>
            <div className="flex items-center gap-2">
              <Button variant="secondary" size="sm" onClick={() => handleEditBanner(b)}>Edit</Button>
              <label className="inline-flex items-center gap-1.5 rounded-lg bg-dark-800/80 border border-primary-500/20 px-3 py-1.5 text-xs hover:border-primary-500/40 cursor-pointer">
                Upload Image
                <input type="file" accept="image/*" className="hidden" onChange={e => handleBannerImageUpload(b.id, e)} />
              </label>
              <Button variant="danger" size="sm" onClick={() => handleDeleteBanner(b.id)}>Delete</Button>
            </div>
          </Card>
        ))}
        {bannersList.length === 0 && <EmptyState>no_banners</EmptyState>}
      </div>
    </div>
  )
}
