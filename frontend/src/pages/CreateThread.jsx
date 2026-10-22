import { useState, useEffect, useRef } from 'react'
import { Link, useParams, useNavigate } from 'react-router-dom'
import { BarChart3, X, FilePlus2 } from 'lucide-react'
import api from '../lib/api'
import { useAuthStore } from '../store/authStore'
import { useToast } from '../components/Toast'
import MarkdownToolbar from '../components/MarkdownToolbar'
import MarkdownContent from './forum/MarkdownContent'
import { Card, PageHeading, Button, FormInput, Toggle, LoadingState } from '../components/ui'
import { useT } from '../lib/i18n'

export default function CreateThread() {
  const t = useT()
  const { boardId: boardSlug } = useParams()
  const navigate = useNavigate()
  const { user, canCreateThread } = useAuthStore()
  const userRole = user?.role?.toUpperCase()
  const { showToast } = useToast()
  
  const [board, setBoard] = useState(null)
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [tags, setTags] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [loading, setLoading] = useState(true)
  const [preview, setPreview] = useState(false)
  const [showPoll, setShowPoll] = useState(false)
  const [pollQuestion, setPollQuestion] = useState('')
  const [pollOptions, setPollOptions] = useState(['', ''])
  const [pollMultiple, setPollMultiple] = useState(false)
  const [pollAnonymous, setPollAnonymous] = useState(false)
  const [pollAllowChange, setPollAllowChange] = useState(true)
  const [previewContent, setPreviewContent] = useState('')
  const previewTimerRef = useRef(null)
  const contentRef = useRef(null)
  const mountedRef = useRef(true)

  useEffect(() => {
    mountedRef.current = true
    return () => { mountedRef.current = false }
  }, [])

  const minRole = board?.min_role_to_create_thread?.toUpperCase()

  useEffect(() => {
    loadBoard()
  }, [boardSlug])

  // Debounce preview updates to avoid re-rendering ReactMarkdown on every keystroke
  useEffect(() => {
    clearTimeout(previewTimerRef.current)
    previewTimerRef.current = setTimeout(() => {
      if (mountedRef.current) setPreviewContent(content)
    }, 300)
    return () => clearTimeout(previewTimerRef.current)
  }, [content])

  const loadBoard = async () => {
    try {
      const res = await api.get(`/api/forum/boards/${boardSlug}`)
      setBoard(res.data)
    } catch (err) {
      console.error('Failed to load board:', err)
      navigate('/')
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!title.trim() || !content.trim() || submitting) return

    try {
      setSubmitting(true)
      const payload = {
        title: title.trim(),
        content: content.trim()
      }
      if (tags.trim()) {
        payload.tags = tags.split(',').map(t => t.trim()).filter(Boolean)
      }
      if (showPoll && pollQuestion.trim() && pollOptions.filter(o => o.trim()).length >= 2) {
        payload.poll = {
          question: pollQuestion.trim(),
          options: pollOptions.filter(o => o.trim()).map(o => ({ text: o.trim() })),
          is_multiple_choice: pollMultiple,
          is_anonymous: pollAnonymous,
          allow_vote_change: pollAllowChange
        }
      }
      const res = await api.post(`/api/forum/boards/${boardSlug}/threads`, payload)
      showToast(t('forum.thread_created'), 'success')
      navigate(`/thread/${res.data.slug}`)
    } catch (err) {
      showToast(err.response?.data?.detail || t('forum.create_thread_failed'), 'error')
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) {
    return <LoadingState label={t('forum.loading_board')} className="min-h-[60vh] flex flex-col items-center justify-center" />
  }

  if (!canCreateThread(board)) {
    return (
      <Card className="p-8 text-center">
        <h2 className="font-semibold text-lg mb-2">{t('forum.insufficient_permissions')}</h2>
        {userRole === 'TRIAL' ? (
          <p className="text-dark-400 mb-4">
            {t('forum.trial_cant_create')}{' '}
            {t('forum.board_requires_level', { role: minRole || 'USER' })}{' '}
            <Link to="/shop" className="text-primary-400 hover:underline">{t('forum.upgrade_account')}</Link> {t('forum.to_participate')}
          </p>
        ) : (
          <p className="text-dark-400 mb-4">
            {t('forum.level_cant_create')}{' '}
            {t('forum.board_requires_level', { role: minRole || t('forum.role_higher') })}
          </p>
        )}
        <Link to="/" className="text-primary-400 hover:underline">{t('forum.go_back_forum')}</Link>
      </Card>
    )
  }

  return (
    <div className="space-y-4">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-dark-400">
        <Link to="/" className="hover:text-white">{t('nav.forum')}</Link>
        <span>/</span>
        <Link to={`/board/${boardSlug}`} className="hover:text-white">{board?.name}</Link>
        <span>/</span>
        <span className="text-white">{t('forum.new_thread')}</span>
      </div>

      {/* Form */}
      <form onSubmit={handleSubmit}>
        <Card className="space-y-4">
        <PageHeading icon={FilePlus2} title={t('forum.create_new_thread')} />

        <FormInput
          label={t('forum.title_label')}
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder={t('forum.title_placeholder')}
          maxLength={200}
        />
        <div className="text-xs text-dark-400 -mt-2">{title.length}/200</div>

        <div>
          <div className="flex items-center justify-between mb-2">
            <label className="block font-mono text-[10px] uppercase tracking-widest text-primary-400/70">{t('forum.content_label')}</label>
            <div className="flex rounded-lg border border-primary-500/15 overflow-hidden text-[10px]">
              <button type="button" onClick={() => setPreview(false)}
                className={`px-2.5 py-1 transition-colors ${!preview ? 'bg-primary-500 text-dark-950' : 'text-dark-400 hover:text-white'}`}>
                {t('forum.write')}
              </button>
              <button type="button" onClick={() => setPreview(true)}
                className={`px-2.5 py-1 transition-colors ${preview ? 'bg-primary-500 text-dark-950' : 'text-dark-400 hover:text-white'}`}>
                {t('forum.preview')}
              </button>
            </div>
          </div>
          <div className="rounded-xl border border-primary-500/15 overflow-hidden bg-dark-950/60">
            {!preview && <MarkdownToolbar textareaRef={contentRef} />}
            {preview ? (
              <div className="p-4 min-h-[200px]">
                {previewContent.trim() ? (
                  <MarkdownContent content={previewContent} />
                ) : (
                  <p className="text-dark-500 italic">{t('forum.nothing_to_preview')}</p>
                )}
              </div>
            ) : (
              <textarea
                ref={contentRef}
                value={content}
                onChange={(e) => setContent(e.target.value)}
                placeholder={t('forum.post_placeholder')}
                rows={10}
                className="w-full bg-transparent p-4 resize-none focus:outline-none text-sm leading-relaxed"
              />
            )}
          </div>
          <div className="text-xs text-dark-400 mt-1">{content.length > 0 ? t('forum.chars', { n: content.length.toLocaleString() }) : t('forum.markdown_supported')}</div>
        </div>

        <div>
          <FormInput
            label={t('forum.tags_label')}
            type="text"
            value={tags}
            onChange={(e) => setTags(e.target.value)}
            placeholder={t('forum.tags_placeholder')}
          />
          <div className="text-xs text-dark-400 mt-1">{t('forum.comma_separated')}</div>
        </div>

        {/* Poll Section */}
        <div>
          <Button
            type="button"
            variant={showPoll ? 'secondary' : 'ghost'}
            icon={BarChart3}
            onClick={() => setShowPoll(!showPoll)}
            className={showPoll ? '!border-primary-500/30 !text-primary-400' : '!border-dark-700 border'}
          >
            {showPoll ? t('forum.remove_poll') : t('forum.add_poll')}
          </Button>

          {showPoll && (
            <Card className="mt-3 !bg-dark-950/60 space-y-3">
              <FormInput
                type="text"
                value={pollQuestion}
                onChange={e => setPollQuestion(e.target.value)}
                placeholder={t('forum.poll_question_placeholder')}
                maxLength={500}
              />
              <div className="space-y-2">
                <label className="text-xs text-dark-400 font-medium">{t('forum.poll_options_label')}</label>
                {pollOptions.map((opt, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <FormInput
                      className="flex-1"
                      type="text"
                      value={opt}
                      onChange={e => {
                        const next = [...pollOptions]
                        next[i] = e.target.value
                        setPollOptions(next)
                      }}
                      placeholder={t('forum.poll_option_n', { n: i + 1 })}
                      maxLength={200}
                    />
                    {pollOptions.length > 2 && (
                      <button type="button" onClick={() => setPollOptions(pollOptions.filter((_, j) => j !== i))}
                        className="text-dark-500 hover:text-red-400 transition-colors p-1">
                        <X size={16} />
                      </button>
                    )}
                  </div>
                ))}
                {pollOptions.length < 10 && (
                  <button type="button" onClick={() => setPollOptions([...pollOptions, ''])}
                    className="text-xs text-primary-400 hover:text-primary-300 transition-colors">
                    {t('forum.poll_add_option')}
                  </button>
                )}
              </div>
              <div className="flex flex-wrap gap-4 pt-3 border-t border-primary-500/15">
                <Toggle checked={pollMultiple} onChange={e => setPollMultiple(e.target.checked)} label={t('forum.poll_multiple')} />
                <Toggle checked={pollAnonymous} onChange={e => setPollAnonymous(e.target.checked)} label={t('forum.poll_anonymous')} />
                <Toggle checked={pollAllowChange} onChange={e => setPollAllowChange(e.target.checked)} label={t('forum.poll_allow_change')} />
              </div>
            </Card>
          )}
        </div>

        <div className="flex items-center gap-3 pt-4 border-t border-primary-500/15">
          <Button
            type="button"
            variant="ghost"
            onClick={() => navigate(`/board/${boardSlug}`)}
          >
            {t('common.cancel')}
          </Button>
          <Button
            type="submit"
            variant="primary"
            disabled={!title.trim() || !content.trim() || submitting}
          >
            {submitting ? t('forum.creating') : t('forum.create_thread')}
          </Button>
        </div>
        </Card>
      </form>
    </div>
  )
}
