import { useState, useEffect } from 'react'
import api from '../../lib/api'
import { t } from '../../lib/i18n'
import { Card, Button, StatusBadge, EmptyState, LoadingState } from '../../components/admin/ui'

export default function AdminReports({ showToast, showConfirm }) {
  const [reportsData, setReportsData] = useState({ items: [], total: 0 })
  const [reportFilter, setReportFilter] = useState('pending')
  const [reportTypeFilter, setReportTypeFilter] = useState('all')
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const PER_PAGE = 50

  const loadReports = async (pageVal = 1, append = false) => {
    if (append) setLoadingMore(true)
    else setLoading(true)
    try {
      const params = { status: reportFilter, page: pageVal, per_page: PER_PAGE }
      if (reportTypeFilter !== 'all') params.report_type = reportTypeFilter
      const { data } = await api.get('/api/mod/reports', { params })
      setReportsData(prev => append
        ? { ...data, items: [...prev.items, ...(data.items || [])] }
        : data)
      setPage(pageVal)
    } catch { if (!append) showToast(t('common.load_failed'), 'error') }
    finally { setLoading(false); setLoadingMore(false) }
  }

  useEffect(() => { loadReports(1, false) }, [reportFilter, reportTypeFilter])

  const handleResolveReport = (reportId, action) => {
    showConfirm(
      `Resolve report #${reportId} as "${action}"?`,
      async () => {
        try {
          await api.put(`/api/mod/reports/${reportId}/resolve?action=${action}`)
          showToast('Report resolved', 'success')
          loadReports()
        } catch (err) { showToast(err.response?.data?.detail || 'Failed', 'error') }
      }
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        {['pending', 'resolved', 'dismissed'].map(s => (
          <Button key={s} variant={reportFilter === s ? 'primary' : 'secondary'} size="sm"
            className="capitalize" onClick={() => setReportFilter(s)}>{s}</Button>
        ))}
        <span className="w-px h-5 bg-primary-500/20" />
        {['all', 'thread', 'post', 'user'].map(t => (
          <Button key={t} variant={reportTypeFilter === t ? 'primary' : 'secondary'} size="sm"
            className="capitalize" onClick={() => setReportTypeFilter(t)}>{t}</Button>
        ))}
      </div>
      {loading ? (
        <LoadingState label="loading reports" />
      ) : reportsData.items?.length === 0 ? (
        <EmptyState>no_reports_found</EmptyState>
      ) : (
        <div className="space-y-2">
          {reportsData.items?.map(r => (
            <Card key={r.id}>
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <StatusBadge status={r.status} />
                    <span className="text-[10px] bg-dark-700 text-dark-300 px-1.5 py-0.5 rounded font-mono">{r.report_type}</span>
                    <span className="font-medium text-sm">{r.reason}</span>
                  </div>
                  {r.description && <p className="text-xs text-dark-400 mt-1">{r.description}</p>}
                  <div className="text-[10px] text-dark-500 mt-1">
                    Reported by @{r.reporter?.username || '?'} • {r.reported_user ? `User: @${r.reported_user?.username}` : ''}
                    {r.thread && ` • Thread: ${r.thread.title?.slice(0, 40)}`}
                  </div>
                </div>
                {r.status === 'pending' && (
                  <div className="flex gap-1 flex-shrink-0">
                    <Button variant="secondary" size="xs" onClick={() => handleResolveReport(r.id, 'dismissed')}>Dismiss</Button>
                    <Button variant="warn" size="xs" onClick={() => handleResolveReport(r.id, 'warned')}>Warn</Button>
                    <Button variant="danger" size="xs" onClick={() => handleResolveReport(r.id, 'content_removed')}>Remove</Button>
                    <Button variant="danger" size="xs" onClick={() => handleResolveReport(r.id, 'user_banned')}>Ban</Button>
                  </div>
                )}
              </div>
            </Card>
          ))}
          {reportsData.items?.length < (reportsData.total || 0) && (
            <div className="text-center pt-1">
              <Button variant="secondary" size="sm" disabled={loadingMore} onClick={() => loadReports(page + 1, true)}>
                {loadingMore ? 'Loading…' : `Load more (${reportsData.items.length}/${reportsData.total})`}
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
