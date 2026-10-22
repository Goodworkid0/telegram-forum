import { useState, useEffect, useCallback } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Shield, AlertTriangle, MessageSquare, User, CheckCircle, Clock, History } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import api from '../lib/api'
import { useAuthStore } from '../store/authStore'
import { useToast } from '../components/Toast'
import { timeAgo } from '../lib/utils'
import { Card, PageHeading, Button, Tag, StatusBadge, FormTextarea, EmptyState, LoadingState, tabClass } from '../components/ui'

const TYPE_ICON = {
  thread: MessageSquare,
  post: MessageSquare,
  user: User,
}

const ACTIONS = [
  { value: 'dismissed', label: 'Dismiss', variant: 'ghost' },
  { value: 'warned', label: 'Warn User', variant: 'warn' },
  { value: 'content_removed', label: 'Remove Content', variant: 'danger' },
  { value: 'user_banned', label: 'Ban User', variant: 'danger' },
]

export default function ModQueue() {
  const { user, isModerator } = useAuthStore()
  const { showToast } = useToast()
  const navigate = useNavigate()

  const [activeView, setActiveView] = useState('reports') // reports | actions
  const [reports, setReports] = useState([])
  const [actions, setActions] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState('pending')
  const [typeFilter, setTypeFilter] = useState('')
  const [resolveTarget, setResolveTarget] = useState(null)
  const [resolveAction, setResolveAction] = useState('dismissed')
  const [modNotes, setModNotes] = useState('')
  const [resolving, setResolving] = useState(false)

  const loadReports = useCallback(async () => {
    setLoading(true)
    try {
      const params = { page, per_page: 20 }
      if (statusFilter) params.status = statusFilter
      if (typeFilter) params.report_type = typeFilter
      const { data } = await api.get('/api/mod/reports', { params })
      setReports(data.items || [])
      setTotal(data.total || 0)
    } catch (err) {
      showToast('Failed to load reports', 'error')
    } finally {
      setLoading(false)
    }
  }, [page, statusFilter, typeFilter, showToast])

  const loadActions = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await api.get('/api/mod/actions', { params: { page, per_page: 30 } })
      // Endpoint is paginated ({items, total, page, per_page}); tolerate a bare array too.
      setActions(Array.isArray(data) ? data : data?.items || [])
    } catch (err) {
      showToast('Failed to load mod actions', 'error')
    } finally {
      setLoading(false)
    }
  }, [page, showToast])

  useEffect(() => {
    if (!isModerator?.()) return
    if (activeView === 'reports') loadReports()
    else loadActions()
  }, [activeView, loadReports, loadActions, isModerator])

  const handleResolve = async () => {
    if (!resolveTarget || resolving) return
    setResolving(true)
    try {
      await api.put(`/api/mod/reports/${resolveTarget.id}/resolve`, null, {
        params: { action: resolveAction, mod_notes: modNotes || undefined }
      })
      showToast('Report resolved', 'success')
      setResolveTarget(null)
      setModNotes('')
      loadReports()
    } catch (err) {
      showToast(err.response?.data?.detail || 'Failed to resolve', 'error')
    } finally {
      setResolving(false)
    }
  }

  if (!isModerator?.()) {
    return (
      <Card className="p-8 text-center">
        <Shield size={40} className="mx-auto text-dark-600 mb-3" />
        <p className="text-dark-400">Moderator access required</p>
      </Card>
    )
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <PageHeading
        icon={Shield}
        title={
          <span className="inline-flex items-center gap-2">
            Moderation
            {total > 0 && statusFilter === 'pending' && activeView === 'reports' && (
              <span className="bg-amber-500 text-xs font-bold px-2 py-0.5 rounded-full text-black">{total}</span>
            )}
          </span>
        }
        right={
          <Link to="/admin" className="text-xs text-dark-400 hover:text-white transition-colors">
            Admin Panel
          </Link>
        }
      />

      {/* View Toggle */}
      <div className="flex gap-2">
        <button
          onClick={() => { setActiveView('reports'); setPage(1) }}
          className={tabClass(activeView === 'reports') + ' flex items-center gap-1.5'}
        >
          <AlertTriangle size={15} /> Reports
        </button>
        <button
          onClick={() => { setActiveView('actions'); setPage(1) }}
          className={tabClass(activeView === 'actions') + ' flex items-center gap-1.5'}
        >
          <History size={15} /> Action Log
        </button>
      </div>

      {/* Report Filters */}
      {activeView === 'reports' && (
        <div className="flex flex-wrap gap-2">
          {[
            { value: 'pending', label: 'Pending' },
            { value: 'resolved', label: 'Resolved' },
            { value: 'dismissed', label: 'Dismissed' },
            { value: '', label: 'All' },
          ].map(f => (
            <button
              key={f.value}
              onClick={() => { setStatusFilter(f.value); setPage(1) }}
              className={`px-3 py-1 rounded-lg text-xs font-medium transition-colors ${
                statusFilter === f.value
                  ? 'bg-primary-500 text-dark-950'
                  : 'bg-dark-800/50 text-dark-400 hover:text-white border border-dark-700/50'
              }`}
            >
              {f.label}
            </button>
          ))}
          <div className="w-px bg-dark-700/50 mx-1" />
          {[
            { value: '', label: 'All Types' },
            { value: 'thread', label: 'Threads' },
            { value: 'post', label: 'Posts' },
            { value: 'user', label: 'Users' },
          ].map(f => (
            <button
              key={f.value}
              onClick={() => { setTypeFilter(f.value); setPage(1) }}
              className={`px-3 py-1 rounded-lg text-xs font-medium transition-colors ${
                typeFilter === f.value
                  ? 'bg-blue-500/80 text-white'
                  : 'bg-dark-800/50 text-dark-400 hover:text-white border border-dark-700/50'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
      )}

      {/* Content */}
      {loading ? (
        <LoadingState label="loading reports" />
      ) : activeView === 'reports' ? (
        /* Report List */
        reports.length === 0 ? (
          <EmptyState icon={CheckCircle}>
            {statusFilter === 'pending' ? 'no pending reports' : 'no reports found'}
          </EmptyState>
        ) : (
          <div className="space-y-2">
            {reports.map((r) => {
              const Icon = TYPE_ICON[r.report_type] || AlertTriangle
              return (
                <Card
                  key={r.id}
                  as={motion.div}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="space-y-2"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-start gap-3 min-w-0">
                      <div className="w-9 h-9 rounded-lg bg-red-500/10 flex items-center justify-center flex-shrink-0">
                        <Icon size={16} className="text-red-400" />
                      </div>
                      <div className="min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-sm font-medium">{r.reason}</span>
                          <StatusBadge status={r.status} />
                          <Tag>{r.report_type}</Tag>
                        </div>
                        {r.description && (
                          <p className="text-xs text-dark-400 mt-1 line-clamp-2">{r.description}</p>
                        )}
                        <div className="flex items-center gap-3 mt-1.5 text-[10px] text-dark-500 flex-wrap">
                          <span>Reported by: <span className="text-dark-300">{r.reporter?.username || r.reporter?.first_name || `#${r.reporter_id}`}</span></span>
                          {r.reported_user && (
                            <span>Against: <Link to={`/profile/${r.reported_user_id}`} className="text-primary-400 hover:underline">@{r.reported_user.username || r.reported_user.first_name}</Link></span>
                          )}
                          {r.thread_id && (
                            <Link to={`/thread/${r.thread_slug}`} className="text-primary-400 hover:underline">View thread</Link>
                          )}
                          <span className="flex items-center gap-1"><Clock size={10} />{timeAgo(r.created_at)}</span>
                        </div>
                        {r.mod_notes && (
                          <p className="text-xs text-blue-400/80 mt-1.5 bg-blue-500/5 px-2 py-1 rounded">Mod: {r.mod_notes}</p>
                        )}
                      </div>
                    </div>
                    {r.status === 'pending' && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => { setResolveTarget(r); setResolveAction('dismissed'); setModNotes('') }}
                        className="!text-primary-400 hover:!text-primary-300 whitespace-nowrap"
                      >
                        Resolve
                      </Button>
                    )}
                  </div>
                </Card>
              )
            })}

            {/* Pagination */}
            {total > 20 && (
              <div className="flex justify-center items-center gap-2 pt-2">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setPage(p => Math.max(1, p - 1))}
                  disabled={page === 1}
                >
                  Previous
                </Button>
                <span className="px-3 py-1.5 text-xs text-dark-400">
                  Page {page} of {Math.ceil(total / 20)}
                </span>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setPage(p => p + 1)}
                  disabled={page >= Math.ceil(total / 20)}
                >
                  Next
                </Button>
              </div>
            )}
          </div>
        )
      ) : (
        /* Action Log */
        actions.length === 0 ? (
          <EmptyState icon={History}>no moderation actions yet</EmptyState>
        ) : (
          <div className="space-y-2">
            {actions.map((a) => (
              <Card
                key={a.id}
                as={motion.div}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                className="!p-3 flex items-start gap-3"
              >
                <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${
                  a.action_type === 'ban' ? 'bg-red-500/10' :
                  a.action_type === 'warning' ? 'bg-amber-500/10' :
                  a.action_type === 'unban' ? 'bg-green-500/10' :
                  'bg-dark-700'
                }`}>
                  <Shield size={14} className={
                    a.action_type === 'ban' ? 'text-red-400' :
                    a.action_type === 'warning' ? 'text-amber-400' :
                    a.action_type === 'unban' ? 'text-green-400' :
                    'text-dark-400'
                  } />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-xs font-semibold capitalize">{a.action_type.replace('_', ' ')}</span>
                    <span className="text-[10px] text-dark-500">by @{a.moderator?.username || 'mod'}</span>
                  </div>
                  {a.target_user && (
                    <p className="text-xs text-dark-400 mt-0.5">
                      Target: <Link to={`/profile/${a.target_user_id}`} className="text-primary-400 hover:underline">@{a.target_user.username || a.target_user.first_name}</Link>
                    </p>
                  )}
                  {a.reason && <p className="text-xs text-dark-400 mt-0.5 line-clamp-1">{a.reason}</p>}
                  <span className="text-[10px] text-dark-500">{timeAgo(a.created_at)}</span>
                </div>
              </Card>
            ))}
          </div>
        )
      )}

      {/* Resolve Modal */}
      <AnimatePresence>
        {resolveTarget && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/60 z-50 flex items-end sm:items-center justify-center p-4"
            onClick={(e) => { if (e.target === e.currentTarget) setResolveTarget(null) }}
          >
            <Card
              as={motion.div}
              initial={{ y: 40, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              exit={{ y: 40, opacity: 0 }}
              className="w-full max-w-md !p-5 space-y-4"
            >
              <h3 className="font-display font-bold text-lg">Resolve Report #{resolveTarget.id}</h3>
              <p className="text-sm text-dark-400">{resolveTarget.reason}: {resolveTarget.description || 'No description'}</p>

              <div>
                <label className="text-xs font-medium text-dark-400 mb-2 block">Action</label>
                <div className="grid grid-cols-2 gap-2">
                  {ACTIONS.map(a => (
                    <Button
                      key={a.value}
                      type="button"
                      variant={a.variant}
                      size="sm"
                      onClick={() => setResolveAction(a.value)}
                      className={resolveAction === a.value ? 'ring-2 ring-primary-400/50' : 'opacity-70'}
                    >
                      {a.label}
                    </Button>
                  ))}
                </div>
              </div>

              <FormTextarea
                label="Mod Notes (optional)"
                value={modNotes}
                onChange={e => setModNotes(e.target.value)}
                placeholder="Internal notes..."
                rows={3}
              />

              <div className="flex justify-end gap-2 pt-2">
                <Button variant="ghost" onClick={() => setResolveTarget(null)}>
                  Cancel
                </Button>
                <Button variant="primary" onClick={handleResolve} disabled={resolving}>
                  {resolving ? 'Resolving...' : 'Confirm'}
                </Button>
              </div>
            </Card>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
