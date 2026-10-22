import { useT } from '../../lib/i18n'

export default function Pagination({ page, totalPages, onPageChange }) {
  const t = useT()
  if (totalPages <= 1) return null

  const getPageNumbers = () => {
    const pages = []
    const delta = 2
    const left = Math.max(2, page - delta)
    const right = Math.min(totalPages - 1, page + delta)

    pages.push(1)
    if (left > 2) pages.push('...')
    for (let i = left; i <= right; i++) pages.push(i)
    if (right < totalPages - 1) pages.push('...')
    if (totalPages > 1) pages.push(totalPages)

    return pages
  }

  return (
    <div className="flex items-center justify-center gap-1.5">
      <button
        onClick={() => onPageChange(page - 1)}
        disabled={page <= 1}
        className="px-2.5 py-1.5 text-xs rounded-lg border border-dark-700/50 disabled:opacity-30 text-dark-400 hover:text-white hover:bg-dark-700/50 transition-all"
      >
        {t('forum.prev')}
      </button>
      {getPageNumbers().map((p, i) => (
        p === '...' ? (
          <span key={`dots-${i}`} className="px-1 text-dark-500 text-xs">...</span>
        ) : (
          <button
            key={p}
            onClick={() => onPageChange(p)}
            className={`w-8 h-8 text-xs rounded-lg transition-all ${
              p === page
                ? 'bg-primary-500 text-dark-950 font-semibold'
                : 'border border-dark-700/50 text-dark-400 hover:text-white hover:bg-dark-700/50'
            }`}
          >
            {p}
          </button>
        )
      ))}
      <button
        onClick={() => onPageChange(page + 1)}
        disabled={page >= totalPages}
        className="px-2.5 py-1.5 text-xs rounded-lg border border-dark-700/50 disabled:opacity-30 text-dark-400 hover:text-white hover:bg-dark-700/50 transition-all"
      >
        {t('forum.next')}
      </button>
    </div>
  )
}
