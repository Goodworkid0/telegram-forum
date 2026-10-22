import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../../lib/api'
import { Card, SectionHeader, StatusBadge, StatTile, EmptyState, LoadingState } from '../../components/admin/ui'

const cx = (...p) => p.filter(Boolean).join(' ')

const STATUS_FILTERS = [
  { value: '', label: 'All' },
  { value: 'pending', label: 'Pending' },
  { value: 'accepted', label: 'Accepted' },
  { value: 'funded', label: 'Funded' },
  { value: 'delivered', label: 'Delivered' },
  { value: 'disputed', label: 'Disputed' },
  { value: 'completed', label: 'Completed' },
  { value: 'refunded', label: 'Refunded' },
  { value: 'cancelled', label: 'Cancelled' },
]

const EMPTY_STATS = {
  total_deals: 0, active_deals: 0, disputed_deals: 0, completed_deals: 0,
  total_volume: 0, completed_volume: 0, fees_earned: 0, fees_pending: 0,
}

export default function AdminEscrow() {
  const navigate = useNavigate()
  const [data, setData] = useState({ items: [], total: 0, page: 1, per_page: 20, pages: 1, stats: EMPTY_STATS })
  const [status, setStatus] = useState('')
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)

  const load = async () => {
    setLoading(true)
    try {
      const res = await api.get('/api/admin/escrow/deals', { params: { status: status || undefined, page, per_page: 20 } })
      setData(res.data)
    } catch (err) { import.meta.env.DEV && console.error(err) }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [status, page])

  const stats = data.stats || EMPTY_STATS
  const money = (n) => `$${(Number(n) || 0).toFixed(2)}`

  return (
    <div className="space-y-4">
      <SectionHeader
        right={stats.disputed_deals > 0 && (
          <span className="bg-red-500/15 text-red-300 border border-red-500/30 text-xs font-mono font-semibold px-2 py-0.5 rounded">{stats.disputed_deals} disputed</span>
        )}
      >
        ESCROW_OVERVIEW
      </SectionHeader>

      {/* Earnings / volume stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatTile label="Fees Earned" value={money(stats.fees_earned)} accent="emerald" />
        <StatTile label="Fees In Hold" value={money(stats.fees_pending)} accent="amber" />
        <StatTile label="Total Volume" value={money(stats.total_volume)} accent="cyan" />
        <StatTile label="Completed Vol." value={money(stats.completed_volume)} accent="green" />
        <StatTile label="Total Deals" value={stats.total_deals} accent="default" />
        <StatTile label="Active" value={stats.active_deals} accent="cyan" />
        <StatTile label="Completed" value={stats.completed_deals} accent="green" />
        <StatTile label="Disputed" value={stats.disputed_deals} accent="red" />
      </div>

      {/* Status filter */}
      <div className="flex flex-wrap gap-1.5">
        {STATUS_FILTERS.map(f => (
          <button
            key={f.value}
            onClick={() => { setStatus(f.value); setPage(1) }}
            className={cx(
              'px-2.5 py-1 rounded text-xs font-mono border transition-colors',
              status === f.value
                ? 'bg-primary-500/15 text-primary-300 border-primary-500/40'
                : 'bg-dark-800/40 text-dark-400 border-transparent hover:text-dark-200'
            )}
          >
            {f.label}
          </button>
        ))}
      </div>

      {loading ? (
        <LoadingState label="loading escrow deals" />
      ) : data.items?.length === 0 ? (
        <EmptyState>no_escrow_deals</EmptyState>
      ) : (
        <Card className="!p-0 overflow-x-auto">
          <table className="w-full">
            <thead className="bg-dark-800/60 font-mono text-[10px] uppercase tracking-wider text-primary-400/70">
              <tr>
                <th className="px-4 py-3 text-left">#</th>
                <th className="px-4 py-3 text-left">Deal</th>
                <th className="px-4 py-3 text-left">Buyer → Seller</th>
                <th className="px-4 py-3 text-right">Amount</th>
                <th className="px-4 py-3 text-right">Fee</th>
                <th className="px-4 py-3 text-left">Status</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map(d => (
                <tr
                  key={d.id}
                  onClick={() => navigate(`/escrow/${d.id}`)}
                  className="border-t border-primary-500/10 cursor-pointer hover:bg-dark-800/40 transition-colors"
                >
                  <td className="px-4 py-3 text-xs font-mono text-dark-500">{d.id}</td>
                  <td className="px-4 py-3 text-sm max-w-[220px] truncate">{d.title}</td>
                  <td className="px-4 py-3 text-xs text-dark-400 font-mono">
                    @{d.buyer_username || d.buyer_id} → @{d.seller_username || d.seller_id}
                  </td>
                  <td className="px-4 py-3 text-sm font-mono font-medium text-right">${(d.amount || 0).toFixed(2)}</td>
                  <td className="px-4 py-3 text-xs font-mono text-right text-neon-400">${(d.fee_amount || 0).toFixed(2)}</td>
                  <td className="px-4 py-3"><StatusBadge status={d.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      {/* Pagination */}
      {data.pages > 1 && (
        <div className="flex items-center justify-center gap-3 text-xs font-mono text-dark-400">
          <button disabled={page <= 1} onClick={() => setPage(p => Math.max(1, p - 1))}
            className="px-3 py-1 rounded border border-primary-500/20 disabled:opacity-40 hover:text-primary-300">prev</button>
          <span>{data.page} / {data.pages}</span>
          <button disabled={page >= data.pages} onClick={() => setPage(p => p + 1)}
            className="px-3 py-1 rounded border border-primary-500/20 disabled:opacity-40 hover:text-primary-300">next</button>
        </div>
      )}
    </div>
  )
}
