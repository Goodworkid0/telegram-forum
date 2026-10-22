import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkBreaks from 'remark-breaks'
import { Link } from 'react-router-dom'
import { ExternalLink } from 'lucide-react'
import { normalizeLinkHref } from '../../lib/utils'

// Renders a markdown link safely: scheme-less URLs are forced external (so they
// don't route back into our SPA), internal paths use the client router, and
// external links open in a new tab with an indicator icon.
function MarkdownLink({ node, href, children, ...props }) {
  const { href: safeHref, isExternal } = normalizeLinkHref(href)

  if (!safeHref) {
    // Blocked/empty href (e.g. javascript:) — render as plain text.
    return <span {...props}>{children}</span>
  }

  if (!isExternal) {
    // In-app navigation (anchors stay as anchors; paths use the router).
    if (safeHref.startsWith('#') || safeHref.startsWith('mailto:') || safeHref.startsWith('tel:')) {
      return <a href={safeHref} {...props}>{children}</a>
    }
    return <Link to={safeHref} {...props}>{children}</Link>
  }

  return (
    <a href={safeHref} target="_blank" rel="noopener noreferrer nofollow" {...props}>
      {children}
      <ExternalLink size={12} className="inline-block ml-0.5 -mt-0.5 opacity-60" aria-hidden="true" />
    </a>
  )
}

export default function MarkdownContent({ content }) {
  if (!content) return null
  return (
    <div className="prose prose-invert prose-sm sm:prose-base max-w-none
      break-words [overflow-wrap:anywhere]
      prose-p:my-1.5 prose-p:leading-relaxed
      prose-headings:text-white prose-headings:font-semibold
      prose-a:text-primary-400 prose-a:no-underline hover:prose-a:underline
      prose-code:bg-dark-700 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:text-xs prose-code:font-mono prose-code:text-primary-300
      prose-pre:bg-dark-900 prose-pre:border prose-pre:border-dark-700 prose-pre:rounded-lg prose-pre:overflow-x-auto prose-pre:max-w-full prose-pre:whitespace-pre
      prose-blockquote:border-l-primary-500/50 prose-blockquote:bg-dark-750/30 prose-blockquote:rounded-r-lg prose-blockquote:py-0.5 prose-blockquote:px-3 prose-blockquote:not-italic prose-blockquote:text-dark-300
      prose-strong:text-white
      prose-ul:my-1 prose-ol:my-1 prose-li:my-0.5
      prose-img:rounded-lg prose-img:max-h-96">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkBreaks]}
        components={{
          a: MarkdownLink,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}
