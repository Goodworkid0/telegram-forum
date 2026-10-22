import { useState, useEffect } from 'react'
import { Search, Trash2 } from 'lucide-react'
import api from '../../lib/api'
import { t } from '../../lib/i18n'
import { parseDate } from '../../lib/utils'
import { Card, Button, FormInput, StatusBadge, EmptyState, LoadingState } from '../../components/admin/ui'

export default function AdminContent({ showToast, showConfirm }) {
  const [contentItems, setContentItems] = useState([])
  const [contentTotal, setContentTotal] = useState(0)
  const [contentType, setContentType] = useState('all')
  const [contentSearch, setContentSearch] = useState('')
  const [contentPage, setContentPage] = useState(1)
  const [loading, setLoading] = useState(true)

  const loadContent = async (overrides = {}) => {
    const type = overrides.contentType ?? contentType
    const page = overrides.contentPage ?? contentPage
    const q = overrides.contentSearch ?? contentSearch
    setLoading(true)
    try {
      const { data } = await api.get('/api/admin/content', {
        params: { q, content_type: type, page, per_page: 30 }
      })
      setContentItems(data.items)
      setContentTotal(data.total)
    } catch { showToast(t('common.load_failed'), 'error') } finally { setLoading(false) }
  }

  useEffect(() => { loadContent() }, [contentType, contentPage])

  const handleDeleteContent = (type, id) => {
    showConfirm(
      `Delete this ${type}?`,
      async () => {
        try {
          await api.delete(`/api/admin/content/${type}/${id}`)
          showToast(`${type} deleted`, 'success')
          loadContent()
        } catch (err) { showToast(err.response?.data?.detail || 'Failed', 'error') }
      }
    )
  }

  return (
    <div className="space-y-4">
      <Card className="flex flex-wrap gap-3 items-end">
        <div className="flex gap-1">
          {['all', 'threads', 'posts'].map(t => (
            <Button key={t} size="sm" variant={contentType === t ? 'primary' : 'secondary'}
              onClick={() => { setContentPage(1); setContentType(t) }}>
              {t.charAt(0).toUpperCase() + t.slice(1)}
            </Button>
          ))}
        </div>
        <FormInput
          label="search"
          type="text"
          placeholder="Search..."
          value={contentSearch}
          onChange={e => setContentSearch(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') { setContentPage(1); loadContent({ contentPage: 1 }) } }}
          className="flex-1 min-w-[200px]"
        />
        <Button icon={Search} variant="primary"
          onClick={() => { setContentPage(1); loadContent({ contentPage: 1 }) }}>
          Search
        </Button>
      </Card>

      {loading ? (
        <LoadingState label="loading_content" />
      ) : contentItems.length === 0 ? (
        <EmptyState>no_content_found</EmptyState>
      ) : (
        <div className="space-y-2">
          {contentItems.map(item => (
            <Card key={`${item.type}-${item.id}`} className="flex items-start justify-between gap-3">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className={`text-[10px] font-bold font-mono px-1.5 py-0.5 rounded ${item.type === 'thread' ? 'bg-primary-500/20 text-primary-400' : 'bg-dark-600 text-dark-300'}`}>
                    {item.type.toUpperCase()}
                  </span>
                  <span className="font-medium text-sm truncate">{item.title}</span>
                  {item.is_deleted && <StatusBadge status="deleted" />}
                </div>
                <p className="text-xs text-dark-400 mt-1 truncate">{item.content_preview}</p>
                <div className="flex items-center gap-3 text-[10px] font-mono text-dark-500 mt-1">
                  {item.author && <span>@{item.author}</span>}
                  {item.board_name && <span>{item.board_name}</span>}
                  {item.created_at && <span>{parseDate(item.created_at).toLocaleDateString()}</span>}
                </div>
              </div>
              <Button variant="danger" size="xs" icon={Trash2}
                onClick={() => handleDeleteContent(item.type, item.id)}>Delete</Button>
            </Card>
          ))}
          {contentTotal > 30 && (
            <div className="flex justify-center items-center gap-2 pt-2">
              <Button variant="secondary" size="sm"
                onClick={() => setContentPage(p => Math.max(1, p - 1))}
                disabled={contentPage <= 1}>Prev</Button>
              <span className="text-sm font-mono text-dark-400 self-center">Page {contentPage}</span>
              <Button variant="secondary" size="sm"
                onClick={() => setContentPage(p => p + 1)}>Next</Button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
