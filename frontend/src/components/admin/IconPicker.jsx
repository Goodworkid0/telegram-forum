import { useState } from 'react'
import { Search, X } from 'lucide-react'
import BadgeIcon, { ICON_NAMES } from '../BadgeIcon'

// Visual grid picker for badge/achievement icons. Renders every icon from
// BadgeIcon's ICON_MAP so what you pick is exactly what gets shown on the badge.
export default function IconPicker({ value, onChange, color = '#6366f1', iconStyle = 'default' }) {
  const [query, setQuery] = useState('')
  const q = query.trim().toLowerCase()
  const names = q ? ICON_NAMES.filter(n => n.includes(q)) : ICON_NAMES

  return (
    <div>
      <label className="mb-1 block font-mono text-[10px] uppercase tracking-widest text-primary-400/70">
        Icon{value ? ` · ${value}` : ''}
      </label>

      <div className="relative mb-2">
        <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-dark-500" />
        <input
          type="text"
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder="Search icons…"
          className="w-full bg-dark-950/60 border border-primary-500/15 rounded-lg pl-8 pr-8 py-2 text-sm text-white font-mono placeholder:text-dark-500 focus:border-primary-500/50 focus:outline-none transition-all"
        />
        {value && (
          <button
            type="button"
            onClick={() => onChange('')}
            title="Clear icon"
            className="absolute right-2 top-1/2 -translate-y-1/2 text-dark-500 hover:text-red-400 transition-colors"
          >
            <X size={14} />
          </button>
        )}
      </div>

      <div className="grid grid-cols-8 gap-1.5 max-h-44 overflow-y-auto rounded-lg border border-primary-500/15 bg-dark-950/40 p-2">
        {names.map(name => {
          const selected = name === value
          return (
            <button
              key={name}
              type="button"
              title={name}
              onClick={() => onChange(name)}
              className={
                'flex aspect-square items-center justify-center rounded-md border transition-all ' +
                (selected
                  ? 'border-primary-500/70 bg-primary-500/10 shadow-[0_0_0_1px_rgba(0,200,230,0.4)]'
                  : 'border-transparent hover:border-primary-500/30 hover:bg-dark-800/60')
              }
            >
              <BadgeIcon icon={name} iconStyle={selected ? iconStyle : 'default'} color={color} size={18} />
            </button>
          )
        })}
        {names.length === 0 && (
          <p className="col-span-8 py-3 text-center text-xs text-dark-500 font-mono">no icons match “{query}”</p>
        )}
      </div>
    </div>
  )
}
