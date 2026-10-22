import { useState, useEffect } from 'react'
import { ChevronUp, ChevronDown } from 'lucide-react'
import api from '../../lib/api'
import { Card, Button, FormInput, FormSelect, Toggle, RoleBadge, EmptyState, LoadingState, Modal } from '../../components/admin/ui'

export default function AdminStructure({ showToast, showConfirm }) {
  const [tabs, setTabs] = useState([])
  const [sections, setSections] = useState([])
  const [boards, setBoards] = useState([])
  const [badges, setBadges] = useState([])
  const [loading, setLoading] = useState(true)

  const [tabForm, setTabForm] = useState({ name: '', slug: '', icon: '', sort_order: 0, min_role: 'TRIAL', required_badge_id: '', is_default: false })
  const [sectionForm, setSectionForm] = useState({ name: '', slug: '', description: '', sort_order: 0, tab_id: '', min_role: 'TRIAL' })
  const [boardForm, setBoardForm] = useState({ section_id: '', parent_id: '', name: '', slug: '', description: '', board_type: 'forum', link_target: '', sort_order: 0, min_role: 'TRIAL', min_role_to_post: 'USER', min_role_to_create_thread: 'USER' })
  const [editingTab, setEditingTab] = useState(null)
  const [editingSection, setEditingSection] = useState(null)
  const [editingBoard, setEditingBoard] = useState(null)
  const [addBoardSectionId, setAddBoardSectionId] = useState(null)
  const [activeStructureForm, setActiveStructureForm] = useState(null)
  const [structureModal, setStructureModal] = useState(null)

  const loadData = async () => {
    setLoading(true)
    try {
      const [tabsRes, sectionsRes, boardsRes, badgesRes] = await Promise.all([
        api.get('/api/admin/tabs'),
        api.get('/api/admin/sections'),
        api.get('/api/admin/boards'),
        api.get('/api/badges')
      ])
      setTabs(tabsRes.data)
      setSections(sectionsRes.data)
      setBoards(boardsRes.data)
      setBadges(badgesRes.data || [])
    } catch (err) {
      showToast('Failed to load structure data', 'error')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadData() }, [])

  const handleCreateTab = async (e) => {
    e.preventDefault()
    try {
      await api.post('/api/admin/tabs', { ...tabForm, required_badge_id: tabForm.required_badge_id ? Number(tabForm.required_badge_id) : null })
      showToast('Tab created', 'success')
      setTabForm({ name: '', slug: '', icon: '', sort_order: 0, min_role: 'TRIAL', required_badge_id: '', is_default: false })
      await loadData()
    } catch (err) {
      showToast(err.response?.data?.detail || 'Failed to create tab', 'error')
    }
  }

  const handleUpdateTab = async (e) => {
    e.preventDefault()
    try {
      await api.put(`/api/admin/tabs/${editingTab.id}`, { ...tabForm, required_badge_id: tabForm.required_badge_id ? Number(tabForm.required_badge_id) : null })
      showToast('Tab updated', 'success')
      setEditingTab(null)
      setTabForm({ name: '', slug: '', icon: '', sort_order: 0, min_role: 'TRIAL', required_badge_id: '', is_default: false })
      await loadData()
    } catch (err) {
      showToast(err.response?.data?.detail || 'Failed to update tab', 'error')
    }
  }

  const handleDeleteTab = (id) => {
    showConfirm(
      'Delete this tab? Sections will become unassigned.',
      async () => {
        try {
          await api.delete(`/api/admin/tabs/${id}`)
          showToast('Tab deleted', 'success')
          await loadData()
        } catch (err) {
          showToast(err.response?.data?.detail || 'Failed to delete tab', 'error')
        }
      }
    )
  }

  const handleCreateSection = async (e) => {
    e.preventDefault()
    try {
      const data = { ...sectionForm, tab_id: sectionForm.tab_id ? parseInt(sectionForm.tab_id) : null }
      await api.post('/api/admin/sections', data)
      showToast('Section created', 'success')
      setSectionForm({ name: '', slug: '', description: '', sort_order: 0, tab_id: '', min_role: 'TRIAL' })
      await loadData()
    } catch (err) {
      showToast(err.response?.data?.detail || 'Failed', 'error')
    }
  }

  const handleUpdateSection = async (e) => {
    e.preventDefault()
    try {
      const data = { ...sectionForm, tab_id: sectionForm.tab_id ? parseInt(sectionForm.tab_id) : null }
      await api.put(`/api/admin/sections/${editingSection.id}`, data)
      showToast('Section updated', 'success')
      setEditingSection(null)
      setSectionForm({ name: '', slug: '', description: '', sort_order: 0, tab_id: '', min_role: 'TRIAL' })
      await loadData()
    } catch (err) {
      showToast(err.response?.data?.detail || 'Failed', 'error')
    }
  }

  const handleDeleteSection = (id) => {
    showConfirm(
      'Delete this section? (Must have no boards)',
      async () => {
        try {
          await api.delete(`/api/admin/sections/${id}`)
          showToast('Section deleted', 'success')
          await loadData()
        } catch (err) {
          showToast(err.response?.data?.detail || 'Failed to delete section', 'error')
        }
      }
    )
  }

  const handleCreateBoard = async (e) => {
    e.preventDefault()
    try {
      await api.post('/api/admin/boards', { ...boardForm, section_id: parseInt(boardForm.section_id), parent_id: boardForm.parent_id ? parseInt(boardForm.parent_id) : null })
      showToast('Board created', 'success')
      setBoardForm({ section_id: '', parent_id: '', name: '', slug: '', description: '', board_type: 'forum', link_target: '', sort_order: 0, min_role: 'TRIAL', min_role_to_post: 'USER', min_role_to_create_thread: 'USER' })
      await loadData()
    } catch (err) {
      showToast(err.response?.data?.detail || 'Failed', 'error')
    }
  }

  const handleUpdateBoard = async (e) => {
    e.preventDefault()
    try {
      await api.put(`/api/admin/boards/${editingBoard.id}`, { ...boardForm, section_id: parseInt(boardForm.section_id), parent_id: boardForm.parent_id ? parseInt(boardForm.parent_id) : null })
      showToast('Board updated', 'success')
      setEditingBoard(null)
      setBoardForm({ section_id: '', parent_id: '', name: '', slug: '', description: '', board_type: 'forum', link_target: '', sort_order: 0, min_role: 'TRIAL', min_role_to_post: 'USER', min_role_to_create_thread: 'USER' })
      await loadData()
    } catch (err) {
      showToast(err.response?.data?.detail || 'Failed', 'error')
    }
  }

  const handleDeleteBoard = (id) => {
    showConfirm(
      'Delete this board?',
      async () => {
        try {
          await api.delete(`/api/admin/boards/${id}`)
          showToast('Board deleted', 'success')
          await loadData()
        } catch (err) {
          showToast(err.response?.data?.detail || 'Failed', 'error')
        }
      }
    )
  }

  const handleMoveItem = async (type, items, id, direction) => {
    const idx = items.findIndex(i => i.id === id)
    if (idx === -1) return
    const swapIdx = direction === 'up' ? idx - 1 : idx + 1
    if (swapIdx < 0 || swapIdx >= items.length) return

    const reordered = [...items]
    const tmp = reordered[idx]
    reordered[idx] = reordered[swapIdx]
    reordered[swapIdx] = tmp

    const itemIds = reordered.map(i => i.id)
    try {
      const endpointMap = { tabs: '/api/admin/tabs', sections: '/api/admin/sections', boards: '/api/admin/boards' }
      await api.put(`${endpointMap[type]}/reorder`, { item_ids: itemIds })
      showToast('Reordered', 'success')
      loadData()
    } catch (err) { showToast('Failed', 'error') }
  }

  const closeTabForm = () => {
    setEditingTab(null)
    setActiveStructureForm(null)
    setTabForm({ name: '', slug: '', icon: '', sort_order: 0, min_role: 'TRIAL', required_badge_id: '', is_default: false })
  }

  const closeSectionModal = () => {
    setStructureModal(null)
    setEditingSection(null)
    setSectionForm({ name: '', slug: '', description: '', sort_order: 0, tab_id: '', min_role: 'TRIAL' })
  }

  const closeBoardModal = () => {
    setStructureModal(null)
    setEditingBoard(null)
    setAddBoardSectionId(null)
    setBoardForm({ section_id: '', parent_id: '', name: '', slug: '', description: '', board_type: 'forum', link_target: '', sort_order: 0, min_role: 'TRIAL', min_role_to_post: 'USER', min_role_to_create_thread: 'USER' })
  }

  if (loading) {
    return <LoadingState />
  }

  return (
    <div className="space-y-6">
      {/* Quick actions bar */}
      {!activeStructureForm && !structureModal && (
        <div className="flex gap-2">
          <Button variant="primary" size="sm" onClick={() => setActiveStructureForm('tab')}>+ New Tab</Button>
        </div>
      )}

      {/* Tab Create/Edit Form — unified through the same Modal pattern */}
      <Modal
        open={activeStructureForm === 'tab'}
        onClose={closeTabForm}
        title={editingTab ? 'edit_tab' : 'new_tab'}
        maxWidth="max-w-lg"
      >
        <form onSubmit={editingTab ? handleUpdateTab : handleCreateTab} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <FormInput label="Name" placeholder="Name" value={tabForm.name} onChange={e => setTabForm({ ...tabForm, name: e.target.value })} required />
            <FormInput label="Slug" placeholder="Slug" value={tabForm.slug} onChange={e => setTabForm({ ...tabForm, slug: e.target.value })} required />
            <FormInput label="Icon" placeholder="Icon (emoji or URL)" value={tabForm.icon} onChange={e => setTabForm({ ...tabForm, icon: e.target.value })} />
            <FormSelect label="Min Role" value={tabForm.min_role} onChange={e => setTabForm({ ...tabForm, min_role: e.target.value })}>
              <option value="TRIAL">Trial (All Users)</option>
              <option value="USER">Member Only</option>
              <option value="MODERATOR">Mod Only</option>
              <option value="ADMIN">Admin Only</option>
            </FormSelect>
            <FormSelect label="Required Badge" value={tabForm.required_badge_id} onChange={e => setTabForm({ ...tabForm, required_badge_id: e.target.value })}>
              <option value="">None (no badge gate)</option>
              {badges.map(b => <option key={b.id} value={b.id}>{b.name}</option>)}
            </FormSelect>
          </div>
          <p className="text-[11px] text-dark-500 -mt-2">
            Set <span className="text-dark-300">Min Role → Admin Only</span> for an admin-only tab, or pick a <span className="text-dark-300">Required Badge</span> so only users you've given that badge can see this tab. Admins always see every tab.
          </p>
          <Toggle
            checked={tabForm.is_default}
            onChange={e => setTabForm({ ...tabForm, is_default: e.target.checked })}
            label="Default for trial users"
          />
          <div className="flex gap-2 pt-2">
            <Button type="submit" variant="primary" className="flex-1">{editingTab ? 'Update' : 'Create Tab'}</Button>
            <Button type="button" variant="ghost" onClick={closeTabForm}>Cancel</Button>
          </div>
        </form>
      </Modal>

      {/* Section Create/Edit Modal */}
      <Modal
        open={!!structureModal && structureModal.type === 'section'}
        onClose={closeSectionModal}
        title={structureModal?.editing ? 'edit_section' : 'new_section'}
        maxWidth="max-w-lg"
      >
        {structureModal?.contextTabName && (
          <p className="-mt-2 mb-3 font-mono text-[10px] uppercase tracking-widest text-primary-400/70">Tab: {structureModal.contextTabName}</p>
        )}
        <form onSubmit={async (e) => { e.preventDefault(); if (editingSection) { await handleUpdateSection(e) } else { await handleCreateSection(e) }; setStructureModal(null) }} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <FormInput label="Name" placeholder="Name" value={sectionForm.name} onChange={e => setSectionForm({ ...sectionForm, name: e.target.value })} required autoFocus />
            <FormInput label="Slug" placeholder="Slug" value={sectionForm.slug} onChange={e => setSectionForm({ ...sectionForm, slug: e.target.value })} required />
          </div>
          <FormInput label="Description" placeholder="Description" value={sectionForm.description} onChange={e => setSectionForm({ ...sectionForm, description: e.target.value })} />
          <FormSelect label="Tab" value={sectionForm.tab_id} onChange={e => setSectionForm({ ...sectionForm, tab_id: e.target.value })}>
            <option value="">-- No Tab (hidden) --</option>
            {tabs.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
          </FormSelect>
          <FormSelect label="Min Role" value={sectionForm.min_role} onChange={e => setSectionForm({ ...sectionForm, min_role: e.target.value })}>
            <option value="TRIAL">Min Role: Trial</option>
            <option value="USER">Min Role: User</option>
            <option value="MODERATOR">Min Role: Mod</option>
            <option value="ADMIN">Min Role: Admin</option>
          </FormSelect>
          <div className="flex gap-2 pt-2">
            <Button type="submit" variant="primary" className="flex-1">{structureModal?.editing ? 'Update Section' : 'Create Section'}</Button>
            <Button type="button" variant="ghost" onClick={closeSectionModal}>Cancel</Button>
          </div>
        </form>
      </Modal>

      {/* Board Create/Edit Modal */}
      <Modal
        open={!!structureModal && structureModal.type === 'board'}
        onClose={closeBoardModal}
        title={structureModal?.editing ? 'edit_board' : 'new_board'}
        maxWidth="max-w-lg"
      >
        <p className="-mt-2 mb-3 font-mono text-[10px] uppercase tracking-widest text-neon-400/70">Section: {sections.find(s => s.id === (editingBoard ? editingBoard.section_id : addBoardSectionId))?.name}</p>
        <form onSubmit={async (e) => { e.preventDefault(); if (editingBoard) { await handleUpdateBoard(e) } else { await handleCreateBoard(e) }; setStructureModal(null) }} className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <FormSelect label="Type" value={boardForm.board_type} onChange={e => setBoardForm({ ...boardForm, board_type: e.target.value })}>
              <option value="forum">Forum (holds threads)</option>
              <option value="link">Link (shortcut to a page)</option>
            </FormSelect>
            <FormSelect label="Parent" value={boardForm.parent_id} onChange={e => setBoardForm({ ...boardForm, parent_id: e.target.value })}>
              <option value="">Top-level board (no parent)</option>
              {boards.filter(b => b.section_id === (editingBoard ? editingBoard.section_id : addBoardSectionId) && !b.parent_id && b.id !== (editingBoard?.id || 0)).map(b => (
                <option key={b.id} value={b.id}>{b.name} (/{b.slug})</option>
              ))}
            </FormSelect>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <FormInput label="Name" placeholder="Name" value={boardForm.name} onChange={e => setBoardForm({ ...boardForm, name: e.target.value })} required autoFocus />
            <FormInput label="Slug" placeholder="Slug" value={boardForm.slug} onChange={e => setBoardForm({ ...boardForm, slug: e.target.value })} required />
            <FormInput label="Description" placeholder="Description" value={boardForm.description} onChange={e => setBoardForm({ ...boardForm, description: e.target.value })} />
            <FormSelect label="Min Role" value={boardForm.min_role} onChange={e => setBoardForm({ ...boardForm, min_role: e.target.value })}>
              <option value="TRIAL">Min Role: Trial</option>
              <option value="USER">Min Role: User</option>
              <option value="MODERATOR">Min Role: Mod</option>
              <option value="ADMIN">Min Role: Admin</option>
            </FormSelect>
          </div>
          {boardForm.board_type === 'link' ? (
            <FormInput
              label="Link target"
              placeholder="/leaderboard, /giveaways, or https://…"
              value={boardForm.link_target}
              onChange={e => setBoardForm({ ...boardForm, link_target: e.target.value })}
              required
            />
          ) : (
            <div className="grid grid-cols-2 gap-3">
              <FormSelect label="Post" value={boardForm.min_role_to_post} onChange={e => setBoardForm({ ...boardForm, min_role_to_post: e.target.value })}>
                <option value="TRIAL">Post: Trial</option>
                <option value="USER">Post: User</option>
                <option value="MODERATOR">Post: Mod</option>
                <option value="ADMIN">Post: Admin</option>
              </FormSelect>
              <FormSelect label="Thread" value={boardForm.min_role_to_create_thread} onChange={e => setBoardForm({ ...boardForm, min_role_to_create_thread: e.target.value })}>
                <option value="TRIAL">Thread: Trial</option>
                <option value="USER">Thread: User</option>
                <option value="MODERATOR">Thread: Mod</option>
                <option value="ADMIN">Thread: Admin</option>
              </FormSelect>
            </div>
          )}
          <div className="flex gap-2 pt-2">
            <Button type="submit" variant="primary" className="flex-1">{structureModal?.editing ? 'Update Board' : 'Create Board'}</Button>
            <Button type="button" variant="ghost" onClick={closeBoardModal}>Cancel</Button>
          </div>
        </form>
      </Modal>

      {/* Hierarchy: Tab → Section → Board */}
      {tabs.length === 0 ? (
        <EmptyState>no_structure</EmptyState>
      ) : (
        <div className="space-y-4">
          {tabs.map((t, tabIdx) => {
            const tabSections = sections.filter(s => s.tab_id === t.id)
            return (
              <Card key={t.id} className="!p-0 overflow-hidden">
                <div className="flex items-center gap-3 px-4 py-3 bg-dark-800/60">
                  <div className="flex flex-col gap-0.5">
                    <Button variant="ghost" size="xs" icon={ChevronUp} onClick={() => handleMoveItem('tabs', tabs, t.id, 'up')} disabled={tabIdx === 0} className="!p-0.5" />
                    <Button variant="ghost" size="xs" icon={ChevronDown} onClick={() => handleMoveItem('tabs', tabs, t.id, 'down')} disabled={tabIdx === tabs.length - 1} className="!p-0.5" />
                  </div>
                  <span className="text-lg">{t.icon}</span>
                  <div className="flex-1 min-w-0">
                    <span className="font-bold">{t.name}</span>
                    <span className="text-dark-400 text-xs ml-2">/{t.slug}</span>
                    {t.is_default && <span className="ml-2 px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-400 text-[10px]">default</span>}
                  </div>
                  <RoleBadge role={t.min_role || 'TRIAL'} />
                  <span className="text-dark-500 text-xs">{tabSections.length} sections</span>
                  <Button variant="neon" size="xs" onClick={() => { setStructureModal({ type: 'section', editing: null, contextTabName: t.name }); setEditingSection(null); setSectionForm({ name: '', slug: '', description: '', sort_order: 0, tab_id: t.id, min_role: 'TRIAL' }) }}>+ Section</Button>
                  <Button variant="secondary" size="xs" onClick={() => { setEditingTab(t); setActiveStructureForm('tab'); setTabForm({ name: t.name, slug: t.slug, icon: t.icon || '', sort_order: t.sort_order, min_role: t.min_role || 'TRIAL', required_badge_id: t.required_badge_id || '', is_default: t.is_default || false }) }}>Edit</Button>
                  <Button variant="danger" size="xs" onClick={() => handleDeleteTab(t.id)}>Delete</Button>
                </div>

                {tabSections.length > 0 ? (
                  tabSections.map((s, sectionIdx) => {
                    const sectionBoards = boards.filter(b => b.section_id === s.id)
                    return (
                      <div key={s.id} className="border-t border-dark-700/50">
                        <div className="flex items-center gap-3 px-4 py-2.5 pl-10 bg-dark-900/40 hover:bg-dark-800/40 transition-colors">
                          <div className="flex flex-col gap-0.5">
                            <Button variant="ghost" size="xs" icon={ChevronUp} onClick={() => handleMoveItem('sections', tabSections, s.id, 'up')} disabled={sectionIdx === 0} className="!p-0.5" />
                            <Button variant="ghost" size="xs" icon={ChevronDown} onClick={() => handleMoveItem('sections', tabSections, s.id, 'down')} disabled={sectionIdx === tabSections.length - 1} className="!p-0.5" />
                          </div>
                          <div className="flex-1 min-w-0">
                            <span className="font-semibold text-sm">{s.name}</span>
                            <span className="text-dark-500 text-xs ml-2">/{s.slug}</span>
                          </div>
                          <RoleBadge role={s.min_role || 'TRIAL'} />
                          <span className="text-dark-500 text-xs">{sectionBoards.length} boards</span>
                          <Button variant="neon" size="xs" onClick={() => { setStructureModal({ type: 'board', editing: null, contextTabName: null }); setAddBoardSectionId(s.id); setEditingBoard(null); setBoardForm({ section_id: s.id, parent_id: '', name: '', slug: '', description: '', board_type: 'forum', link_target: '', sort_order: 0, min_role: 'TRIAL', min_role_to_post: 'USER', min_role_to_create_thread: 'USER' }) }}>+ Board</Button>
                          <Button variant="secondary" size="xs" onClick={() => { setStructureModal({ type: 'section', editing: s, contextTabName: null }); setEditingSection(s); setSectionForm({ name: s.name, slug: s.slug, description: s.description || '', sort_order: s.sort_order, tab_id: s.tab_id || '', min_role: s.min_role?.toUpperCase() || 'TRIAL' }) }}>Edit</Button>
                          <Button variant="danger" size="xs" onClick={() => handleDeleteSection(s.id)}>Delete</Button>
                        </div>

                        {(() => {
                          const topBoards = sectionBoards.filter(b => !b.parent_id)
                          const children = (parentId) => sectionBoards.filter(b => b.parent_id === parentId)
                          if (topBoards.length === 0 && sectionBoards.length === 0) {
                            return <EmptyState className="!py-2 border-t border-dark-700/30">No boards</EmptyState>
                          }
                          return topBoards.map((b, boardIdx) => (
                            <div key={b.id}>
                              <div className="flex items-center gap-3 px-4 py-2 pl-16 border-t border-dark-700/30 bg-dark-900/40 hover:bg-dark-800/40 transition-colors">
                                <div className="flex flex-col gap-0.5">
                                  <Button variant="ghost" size="xs" icon={ChevronUp} onClick={() => handleMoveItem('boards', topBoards, b.id, 'up')} disabled={boardIdx === 0} className="!p-0.5" />
                                  <Button variant="ghost" size="xs" icon={ChevronDown} onClick={() => handleMoveItem('boards', topBoards, b.id, 'down')} disabled={boardIdx === topBoards.length - 1} className="!p-0.5" />
                                </div>
                                <div className="flex-1 min-w-0">
                                  <span className="text-sm">{b.name}</span>
                                  <span className="text-dark-500 text-xs ml-2">/{b.slug}</span>
                                </div>
                                <RoleBadge role={b.min_role || 'TRIAL'} />
                                <Button variant="secondary" size="xs" onClick={() => { setStructureModal({ type: 'board', editing: b, contextTabName: null }); setEditingBoard(b); setAddBoardSectionId(null); setBoardForm({ section_id: b.section_id, parent_id: b.parent_id || '', name: b.name, slug: b.slug, description: b.description || '', board_type: b.board_type || 'forum', link_target: b.link_target || '', sort_order: b.sort_order, min_role: b.min_role?.toUpperCase() || 'TRIAL', min_role_to_post: (b.min_role_to_post || 'USER').toUpperCase(), min_role_to_create_thread: (b.min_role_to_create_thread || 'USER').toUpperCase() }) }}>Edit</Button>
                                <Button variant="danger" size="xs" onClick={() => handleDeleteBoard(b.id)}>Delete</Button>
                              </div>
                              {children(b.id).map(sub => (
                                <div key={sub.id} className="flex items-center gap-3 px-4 py-2 pl-20 border-t border-dark-700/20 bg-dark-900/40 hover:bg-dark-800/40 transition-colors">
                                  <span className="text-dark-600 text-[10px]">└</span>
                                  <div className="flex-1 min-w-0">
                                    <span className="text-xs">{sub.name}</span>
                                    <span className="text-dark-500 text-[10px] ml-2">/{sub.slug}</span>
                                  </div>
                                  <RoleBadge role={sub.min_role || 'TRIAL'} />
                                  <Button variant="secondary" size="xs" onClick={() => { setStructureModal({ type: 'board', editing: sub, contextTabName: null }); setEditingBoard(sub); setAddBoardSectionId(null); setBoardForm({ section_id: sub.section_id, parent_id: sub.parent_id || '', name: sub.name, slug: sub.slug, description: sub.description || '', board_type: sub.board_type || 'forum', link_target: sub.link_target || '', sort_order: sub.sort_order, min_role: sub.min_role?.toUpperCase() || 'TRIAL', min_role_to_post: (sub.min_role_to_post || 'USER').toUpperCase(), min_role_to_create_thread: (sub.min_role_to_create_thread || 'USER').toUpperCase() }) }}>Edit</Button>
                                  <Button variant="danger" size="xs" onClick={() => handleDeleteBoard(sub.id)}>Delete</Button>
                                </div>
                              ))}
                            </div>
                          ))
                        })()}
                      </div>
                    )
                  })
                ) : (
                  <EmptyState className="!py-3 border-t border-dark-700/50">No sections in this tab</EmptyState>
                )}
              </Card>
            )
          })}
        </div>
      )}
    </div>
  )
}
