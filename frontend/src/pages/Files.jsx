import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { FileText, Download, Search, Image, Film, Music, Mic, File as FileIcon } from 'lucide-react'
import api from '../lib/api'
import { useToast } from '../components/Toast'
import { timeAgo, displayName, nameColorStyle } from '../lib/utils'
import { Card, PageHeading, Button, FormInput, EmptyState, LoadingState, roleStyle } from '../components/ui'
import { useT } from '../lib/i18n'

const KIND_ICON = { photo: Image, video: Film, audio: Music, voice: Mic, document: FileText }

function humanSize(bytes) {
  if (!bytes && bytes !== 0) return ''
  const u = ['B', 'KB', 'MB', 'GB']
  let n = bytes, i = 0
  while (n >= 1024 && i < u.length - 1) { n /= 1024; i++ }
  return `${n.toFixed(n < 10 && i > 0 ? 1 : 0)} ${u[i]}`
}

export default function Files() {
  const t = useT()
  const { showToast } = useToast()
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [q, setQ] = useState('')
  const [cat, setCat] = useState(null)   // null = all, 0 = uncategorized, id = category
  const [categories, setCategories] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [sending, setSending] = useState(null)
  const [openId, setOpenId] = useState(null)   // tapped-open row (mobile has no hover)
  const perPage = 24

  const load = async (pageVal, query, catVal, append) => {
    if (!append) setLoading(true)
    try {
      const res = await api.get('/api/files', { params: {
        page: pageVal, per_page: perPage,
        q: query || undefined,
        category_id: catVal === null ? undefined : catVal,
      } })
      const list = res.data.items || []
      setItems(prev => append ? [...prev, ...list] : list)
      setTotal(res.data.total || 0)
      setPage(pageVal)
      setError(null)
    } catch {
      if (!append) setError('files.load_error')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    api.get('/api/files/categories').then(r => setCategories(r.data || [])).catch(() => {})
  }, [])

  useEffect(() => {
    const id = setTimeout(() => load(1, q, cat, false), q ? 300 : 0)
    return () => clearTimeout(id)
  }, [q, cat])

  const download = async (file) => {
    setSending(file.id)
    try {
      await api.post(`/api/files/${file.id}/download`)
      showToast(t('files.sent'), 'success')
      setItems(prev => prev.map(f => f.id === file.id ? { ...f, download_count: (f.download_count || 0) + 1 } : f))
    } catch (err) {
      const status = err.response?.status
      showToast(status === 409 ? t('files.not_started') : (err.response?.data?.detail || t('files.download_failed')), 'error')
    } finally {
      setSending(null)
    }
  }

  const hasMore = items.length < total
  const chipCls = (active) => `px-3 py-1.5 rounded-lg text-xs font-medium transition-colors whitespace-nowrap ${active ? 'bg-primary-500 text-dark-950' : 'bg-dark-800 text-dark-300 hover:bg-dark-700'}`

  return (
    <div className="max-w-4xl mx-auto px-4 py-6 space-y-5">
      <Card>
        <PageHeading icon={FileText} title={t('files.title')} subtitle={t('files.subtitle')} />
        <div className="mt-4 relative">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-dark-500 pointer-events-none" />
          <FormInput
            placeholder={t('files.search_ph')}
            value={q}
            onChange={e => setQ(e.target.value)}
            inputClassName="pl-9"
          />
        </div>
        {categories.length > 0 && (
          <div className="mt-3 flex gap-2 overflow-x-auto pb-1">
            <button className={chipCls(cat === null)} onClick={() => setCat(null)}>{t('files.all_categories')}</button>
            {categories.map(c => (
              <button key={c.id} className={chipCls(cat === c.id)} onClick={() => setCat(c.id)}>{c.name}</button>
            ))}
            <button className={chipCls(cat === 0)} onClick={() => setCat(0)}>{t('files.uncategorized')}</button>
          </div>
        )}
      </Card>

      {loading ? (
        <LoadingState />
      ) : error && items.length === 0 ? (
        <Card className="text-center py-16">
          <p className="text-dark-500 text-sm mb-4">{t(error)}</p>
          <Button variant="primary" onClick={() => load(1, q, cat, false)}>{t('common.retry')}</Button>
        </Card>
      ) : items.length === 0 ? (
        <Card className="text-center py-16">
          <EmptyState icon={FileText}>{t('files.empty')}</EmptyState>
          <p className="text-dark-500 text-sm">{t('files.empty_hint')}</p>
        </Card>
      ) : (
        <>
          <div className="border border-dark-800 rounded-xl overflow-hidden divide-y divide-dark-800">
            {items.map(f => {
              const Icon = KIND_ICON[f.kind] || FileIcon
              return (
                <div key={f.id} className="group bg-dark-900/30 hover:bg-dark-800/40 transition-colors">
                  {/* Minimal row: icon · name · size · Get on Telegram. Tapping the
                      row toggles details (mobile has no hover); the button doesn't. */}
                  <div className="flex items-center gap-3 px-4 py-2.5 cursor-pointer" onClick={() => setOpenId(id => id === f.id ? null : f.id)}>
                    <Icon size={17} className="text-primary-400 flex-shrink-0" />
                    <span className="flex-1 min-w-0 text-sm text-white truncate" title={f.file_name}>{f.file_name}</span>
                    {f.category_name && (
                      <span className="hidden sm:inline text-[10px] font-medium text-primary-300 bg-primary-500/10 border border-primary-500/20 px-1.5 py-0.5 rounded flex-shrink-0">
                        {f.category_name}
                      </span>
                    )}
                    {f.file_size != null && (
                      <span className="hidden sm:inline text-[11px] font-mono text-dark-500 flex-shrink-0 w-16 text-right">{humanSize(f.file_size)}</span>
                    )}
                    <Button
                      variant="primary"
                      size="sm"
                      icon={Download}
                      disabled={sending === f.id}
                      onClick={(e) => { e.stopPropagation(); download(f) }}
                      className="flex-shrink-0"
                    >
                      {sending === f.id ? t('files.sending') : t('files.download')}
                    </Button>
                  </div>
                  {/* Details: revealed on hover (desktop) or tap (mobile) */}
                  <div className={`overflow-hidden transition-all duration-200 group-hover:max-h-48 group-hover:opacity-100 ${openId === f.id ? 'max-h-48 opacity-100' : 'max-h-0 opacity-0'}`}>
                    <div className="px-4 pb-3 pl-11 text-[11px] font-mono text-dark-400 space-y-1">
                      <div className="text-dark-200 break-all">{f.file_name}</div>
                      <div className="flex flex-wrap gap-x-3 gap-y-0.5">
                        <span>{f.kind}</span>
                        {f.file_size != null && <span>{humanSize(f.file_size)}</span>}
                        <span>{timeAgo(f.created_at)}</span>
                        {f.category_name && <span>{f.category_name}</span>}
                        {f.download_count > 0 && <span>{f.download_count} {t('files.downloads')}</span>}
                        {f.uploader && (
                          <span>{t('files.by')}{' '}
                            <Link to={`/profile/${f.uploader.id}`} className={roleStyle(f.uploader.role).text} style={nameColorStyle(f.uploader)}>
                              {displayName(f.uploader)}
                            </Link>
                          </span>
                        )}
                      </div>
                      {f.caption && <div className="whitespace-pre-wrap break-words">{f.caption}</div>}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
          {hasMore && (
            <div className="text-center pt-1">
              <Button variant="secondary" onClick={() => load(page + 1, q, cat, true)}>{t('common.load_more')}</Button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
