import { Link } from 'react-router-dom'
import { ChevronRight, Home } from 'lucide-react'
import { useT } from '../lib/i18n'

export default function ForumBreadcrumb({ items = [] }) {
  const t = useT()
  if (!items.length) return null

  return (
    <nav className="flex items-center gap-1.5 text-sm text-dark-400 overflow-x-auto pb-1 scrollbar-hide">
      <Link
        to="/"
        className="flex items-center gap-1 hover:text-white transition-colors flex-shrink-0"
        title={t('forum.forum_home')}
      >
        <Home size={14} />
      </Link>

      {items.map((item, i) => {
        const isLast = i === items.length - 1
        return (
          <div key={i} className="flex items-center gap-1.5 min-w-0">
            <ChevronRight size={12} className="text-dark-600 flex-shrink-0" />
            {item.to && !isLast ? (
              <Link
                to={item.to}
                className="hover:text-white transition-colors truncate flex-shrink-0 max-w-[160px]"
              >
                {item.label}
              </Link>
            ) : (
              <span className={`truncate max-w-[200px] ${isLast ? 'text-dark-200 font-medium' : ''}`}>
                {item.label}
              </span>
            )}
          </div>
        )
      })}
    </nav>
  )
}
