import { useRef, useState } from 'react'
import { Bold, Italic, Strikethrough, Code, Link2, Quote, List, Heading1, Heading2, ImagePlus, FileCode2, X } from 'lucide-react'
import api from '../lib/api'
import { useToast } from './Toast'
import { normalizeLinkHref } from '../lib/utils'
import { useT } from '../lib/i18n'

export default function MarkdownToolbar({ textareaRef, onInsert }) {
  const t = useT()
  const fileRef = useRef(null)
  const { showToast } = useToast()
  // Link popover: null when closed, else the captured selection { start, end, text }.
  const [linkSel, setLinkSel] = useState(null)
  const [linkUrl, setLinkUrl] = useState('')
  const [linkText, setLinkText] = useState('')

  const getEl = () => textareaRef?.current

  const dispatchChange = (el, newValue) => {
    const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set
    setter.call(el, newValue)
    el.dispatchEvent(new Event('input', { bubbles: true }))
  }

  const wrap = (prefix, suffix = prefix) => {
    const el = getEl()
    if (!el) return
    const { selectionStart: start, selectionEnd: end, value } = el
    const selected = value.substring(start, end)
    const replacement = `${prefix}${selected || 'text'}${suffix}`
    dispatchChange(el, value.substring(0, start) + replacement + value.substring(end))
    el.focus()
    el.setSelectionRange(start + prefix.length, start + prefix.length + (selected.length || 4))
  }

  const insertLine = (prefix) => {
    const el = getEl()
    if (!el) return
    const { selectionStart: start, value } = el
    const before = value.substring(0, start)
    const lineStart = before.lastIndexOf('\n') + 1
    const insertion = before.length === lineStart ? `${prefix} ` : `\n${prefix} `
    dispatchChange(el, value.substring(0, start) + insertion + value.substring(start))
    el.focus()
    el.setSelectionRange(start + insertion.length, start + insertion.length)
  }

  // Open the link popover, capturing the current selection so we can replace it
  // even after focus moves to the popover input.
  const openLink = () => {
    const el = getEl()
    if (!el) return
    const { selectionStart: start, selectionEnd: end, value } = el
    const selected = value.substring(start, end)
    setLinkSel({ start, end })
    setLinkText(selected)
    setLinkUrl('')
  }

  const closeLink = () => { setLinkSel(null); setLinkUrl(''); setLinkText('') }

  const submitLink = (e) => {
    e?.preventDefault()
    const el = getEl()
    if (!el || !linkSel) return
    const { href } = normalizeLinkHref(linkUrl)
    if (!href) { showToast(t('modals.md.invalid_url'), 'error'); return }
    const text = linkText.trim() || href
    const { start, end } = linkSel
    const value = el.value
    const replacement = `[${text}](${href})`
    dispatchChange(el, value.substring(0, start) + replacement + value.substring(end))
    closeLink()
    el.focus()
    const caret = start + replacement.length
    el.setSelectionRange(caret, caret)
  }

  const handleImage = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    e.target.value = ''

    const el = getEl()
    if (!el) return

    const formData = new FormData()
    formData.append('file', file)

    try {
      const { data } = await api.post('/api/forum/upload-image', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
      const md = `![${file.name}](${data.url})`
      const { selectionStart: start, value } = el
      const prefix = start > 0 && value[start - 1] !== '\n' ? '\n' : ''
      dispatchChange(el, value.substring(0, start) + prefix + md + '\n' + value.substring(start))
      el.focus()
    } catch (err) {
      showToast(err.response?.data?.detail || t('modals.md.upload_failed'), 'error')
    }
  }

  const btn = "p-1.5 rounded hover:bg-dark-600/50 text-dark-400 hover:text-white transition-colors"
  const sep = <div className="w-px h-4 bg-dark-700/50 mx-0.5" />

  return (
    <div className="relative flex items-center gap-0.5 px-3 py-1.5 border-b border-dark-700/30 bg-dark-800/30 flex-wrap">
      <button type="button" onClick={() => wrap('**')} className={btn} title={t('modals.md.bold')}><Bold size={15} /></button>
      <button type="button" onClick={() => wrap('*')} className={btn} title={t('modals.md.italic')}><Italic size={15} /></button>
      <button type="button" onClick={() => wrap('~~')} className={btn} title={t('modals.md.strikethrough')}><Strikethrough size={15} /></button>
      {sep}
      <button type="button" onClick={() => insertLine('#')} className={btn} title={t('modals.md.h1')}><Heading1 size={15} /></button>
      <button type="button" onClick={() => insertLine('##')} className={btn} title={t('modals.md.h2')}><Heading2 size={15} /></button>
      {sep}
      <button type="button" onClick={() => wrap('`')} className={btn} title={t('modals.md.inline_code')}><Code size={15} /></button>
      <button type="button" onClick={() => wrap('```\n', '\n```')} className={btn} title={t('modals.md.code_block')}><FileCode2 size={15} /></button>
      <button type="button" onClick={openLink} className={`${btn} ${linkSel ? 'bg-dark-600/50 text-white' : ''}`} title={t('modals.md.insert_link')}><Link2 size={15} /></button>
      {sep}
      <button type="button" onClick={() => insertLine('>')} className={btn} title={t('modals.md.quote')}><Quote size={15} /></button>
      <button type="button" onClick={() => insertLine('-')} className={btn} title={t('modals.md.list')}><List size={15} /></button>
      {sep}
      <button type="button" onClick={() => fileRef.current?.click()} className={btn} title={t('modals.md.upload_image')}><ImagePlus size={15} /></button>
      <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={handleImage} />

      {/* Link popover */}
      {linkSel && (
        <form
          onSubmit={submitLink}
          className="absolute z-30 top-full left-2 mt-1 w-72 max-w-[calc(100%-1rem)] rounded-lg border border-primary-500/25 bg-dark-900 shadow-xl p-2.5 space-y-2"
        >
          <div className="flex items-center justify-between">
            <span className="text-[10px] uppercase tracking-widest text-dark-500 font-mono">{t('modals.md.insert_link')}</span>
            <button type="button" onClick={closeLink} className="text-dark-500 hover:text-white"><X size={14} /></button>
          </div>
          <input
            autoFocus
            type="text"
            value={linkUrl}
            onChange={e => setLinkUrl(e.target.value)}
            placeholder="https://example.com"
            className="w-full bg-dark-950/60 border border-primary-500/15 rounded px-2.5 py-1.5 text-sm focus:outline-none focus:border-primary-500/50 placeholder-dark-500"
          />
          <input
            type="text"
            value={linkText}
            onChange={e => setLinkText(e.target.value)}
            placeholder={t('modals.md.link_text_ph')}
            className="w-full bg-dark-950/60 border border-primary-500/15 rounded px-2.5 py-1.5 text-sm focus:outline-none focus:border-primary-500/50 placeholder-dark-500"
          />
          <button
            type="submit"
            disabled={!linkUrl.trim()}
            className="w-full bg-primary-500 hover:bg-primary-400 disabled:opacity-40 text-dark-950 font-semibold text-sm rounded px-3 py-1.5 transition-colors"
          >
            {t('modals.md.insert')}
          </button>
        </form>
      )}
    </div>
  )
}
