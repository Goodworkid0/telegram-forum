import { useState, useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import api from '../lib/api'
import { ChevronRight, ExternalLink } from 'lucide-react'
import { useT } from '../lib/i18n'

const ROW_POSITIONS = ['home_row_1', 'home_row_2', 'home_row_3', 'home_row_4']
const MAX_PER_SPOT = 1
const ROTATE_INTERVAL = 8000

function BannerCard({ banner }) {
  const t = useT()
  const isInternal = banner.link && banner.link.startsWith('/')
  const LinkTag = isInternal ? Link : 'a'
  const linkProps = isInternal
    ? { to: banner.link }
    : { href: banner.link, target: '_blank', rel: 'noopener noreferrer' }

  const hasText = banner.title || banner.subtitle || banner.link
  const cardContent = (
    <div
      className="relative overflow-hidden rounded-xl border border-dark-700/50 h-20 sm:h-28 transition-all duration-200 hover:border-dark-600 hover:shadow-lg group"
      style={{
        background: banner.image_url
          ? `url(${banner.image_url}) center/cover no-repeat`
          : `linear-gradient(135deg, ${banner.gradient_from || '#6366f1'}, ${banner.gradient_to || '#8b5cf6'})`
      }}
    >
      {banner.image_url && hasText && (
        <div className="absolute inset-0 bg-black/30" />
      )}
      {hasText && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: 0.1 }}
          className="relative z-10 h-full flex flex-col justify-between p-3 sm:p-4"
        >
          <div>
            {banner.title && (
              <motion.h3
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3, delay: 0.15 }}
                className="font-semibold text-white text-xs sm:text-sm leading-tight line-clamp-1"
              >
                {banner.title}
              </motion.h3>
            )}
            {banner.subtitle && (
              <motion.p
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3, delay: 0.2 }}
                className="text-white/70 text-[10px] sm:text-xs mt-0.5 sm:mt-1 line-clamp-1"
              >
                {banner.subtitle}
              </motion.p>
            )}
          </div>
          {banner.link && (
            <motion.span
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3, delay: 0.25 }}
              className="flex items-center gap-1 text-white/80 text-[10px] sm:text-xs font-medium group-hover:text-white transition-colors"
            >
              {banner.link_text || t('modals.banner.learn_more')}
              {!isInternal && <ExternalLink size={10} />}
              {isInternal && <ChevronRight size={10} />}
            </motion.span>
          )}
        </motion.div>
      )}
    </div>
  )

  if (!banner.link) return cardContent
  return <LinkTag {...linkProps} className="block">{cardContent}</LinkTag>
}

function BannerSpot({ banners }) {
  const [page, setPage] = useState(0)
  const intervalRef = useRef(null)

  const pages = []
  for (let i = 0; i < banners.length; i += MAX_PER_SPOT) {
    pages.push(banners.slice(i, i + MAX_PER_SPOT))
  }
  const totalPages = pages.length

  useEffect(() => {
    if (totalPages <= 1) return
    intervalRef.current = setInterval(() => {
      setPage(p => (p + 1) % totalPages)
    }, ROTATE_INTERVAL)
    return () => clearInterval(intervalRef.current)
  }, [totalPages, banners])

  const visibleBanners = pages[page] || []

  return (
    <div className="space-y-2 sm:space-y-3">
      <AnimatePresence mode="wait">
        <motion.div
          key={page}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -6 }}
          transition={{ duration: 0.3 }}
          className="space-y-3"
        >
          {visibleBanners.map(banner => (
            <BannerCard key={banner.id} banner={banner} />
          ))}
        </motion.div>
      </AnimatePresence>
    </div>
  )
}

export default function BannerRows() {
  const [bannerRows, setBannerRows] = useState([])

  useEffect(() => {
    let cancelled = false
    api.get('/api/banners').then(res => {
      if (cancelled) return
      const banners = res.data || []
      const rows = ROW_POSITIONS
        .map(pos => ({
          position: pos,
          banners: banners
            .filter(b => b.position === pos)
            .sort((a, b) => a.sort_order - b.sort_order)
        }))
        .filter(row => row.banners.length > 0)
      setBannerRows(rows)
    }).catch(() => {})
    return () => { cancelled = true }
  }, [])

  if (bannerRows.length === 0) return null

  // Limit to 4 rows, 1 per row on mobile, 2 columns on desktop
  const displayRows = bannerRows.slice(0, 4)

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 sm:gap-3">
      {displayRows.map(row => (
        <div key={row.position}>
          <BannerSpot banners={row.banners} />
        </div>
      ))}
    </div>
  )
}
