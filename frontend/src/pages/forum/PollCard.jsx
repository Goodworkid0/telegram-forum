import { useState } from 'react'
import { motion } from 'framer-motion'
import api from '../../lib/api'
import { useAuthStore } from '../../store/authStore'
import { useToast } from '../../components/Toast'
import { useT } from '../../lib/i18n'
import { parseDate } from '../../lib/utils'

export default function PollCard({ poll, threadId, user, onUpdate }) {
  const t = useT()
  const { isVerified } = useAuthStore()
  const { showToast } = useToast()
  const [selectedOptions, setSelectedOptions] = useState(poll.voted_options || [])
  const [voting, setVoting] = useState(false)
  const hasVoted = poll.has_voted
  const isClosed = poll.is_closed || (poll.ends_at && parseDate(poll.ends_at) < new Date())
  const showResults = hasVoted || isClosed || poll.show_results_before_vote
  const totalVotes = poll.total_votes || 0

  const toggleOption = (optId) => {
    if (hasVoted && !poll.allow_vote_change) return
    if (poll.is_multiple_choice) {
      setSelectedOptions(prev => prev.includes(optId) ? prev.filter(id => id !== optId) : [...prev, optId])
    } else {
      setSelectedOptions([optId])
    }
  }

  const handleVote = async () => {
    if (!selectedOptions.length || voting) return
    if (!isVerified()) {
      showToast(t('forum.verify_to_vote_toast'), 'warning')
      return
    }
    try {
      setVoting(true)
      const res = await api.post(`/api/forum/polls/${poll.id}/vote`, { option_ids: selectedOptions })
      onUpdate(res.data)
    } catch (err) {
      if (import.meta.env.DEV) console.error('Vote failed:', err)
    } finally {
      setVoting(false)
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-dark-800/80 rounded-xl border border-dark-700/50 p-5"
    >
      <div className="flex items-center gap-2 mb-3">
        <svg className="w-5 h-5 text-primary-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
        </svg>
        <h3 className="font-semibold text-white">{poll.question}</h3>
        {isClosed && <span className="text-[10px] bg-red-500/20 text-red-400 px-2 py-0.5 rounded font-semibold uppercase">{t('forum.poll_closed')}</span>}
      </div>

      <div className="space-y-2">
        {poll.options?.map(opt => {
          const pct = totalVotes > 0 ? ((opt.vote_count / totalVotes) * 100) : 0
          const isSelected = selectedOptions.includes(opt.id)
          const isVoted = poll.voted_options?.includes(opt.id)

          return (
            <button
              key={opt.id}
              type="button"
              onClick={() => !isClosed && user && toggleOption(opt.id)}
              disabled={isClosed || !user || (hasVoted && !poll.allow_vote_change)}
              className={`w-full relative overflow-hidden rounded-lg border text-left px-4 py-2.5 transition-all ${
                isSelected || isVoted
                  ? 'border-primary-500/50 bg-primary-500/5'
                  : 'border-dark-700/50 hover:border-dark-600'
              } disabled:cursor-default`}
            >
              {showResults && (
                <div className="absolute inset-0 bg-primary-500/10 rounded-lg transition-all" style={{ width: `${pct}%` }} />
              )}
              <div className="relative flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  {!isClosed && user && (!hasVoted || poll.allow_vote_change) && (
                    <div className={`w-4 h-4 rounded-${poll.is_multiple_choice ? 'sm' : 'full'} border-2 flex items-center justify-center flex-shrink-0 ${
                      isSelected ? 'border-primary-400 bg-primary-500' : 'border-dark-500'
                    }`}>
                      {isSelected && <div className={`w-2 h-2 bg-white rounded-${poll.is_multiple_choice ? 'sm' : 'full'}`} />}
                    </div>
                  )}
                  <span className="text-sm">{opt.text}</span>
                  {isVoted && <span className="text-[10px] text-primary-400 font-medium">{t('forum.your_vote')}</span>}
                </div>
                {showResults && (
                  <span className="text-xs text-dark-400 font-medium flex-shrink-0">{opt.vote_count} ({pct.toFixed(0)}%)</span>
                )}
              </div>
            </button>
          )
        })}
      </div>

      <div className="flex items-center justify-between mt-3 pt-3 border-t border-dark-700/30">
        <span className="text-xs text-dark-500">
          {t(totalVotes === 1 ? 'forum.votes_count_one' : 'forum.votes_count_many', { n: totalVotes })}
          {poll.is_multiple_choice && ` · ${t('forum.poll_multiple')}`}
          {poll.is_anonymous && ` · ${t('forum.anonymous')}`}
        </span>
        {user && !isClosed && selectedOptions.length > 0 && (!hasVoted || poll.allow_vote_change) && (
          <button
            onClick={handleVote}
            disabled={voting}
            className="bg-primary-500 hover:bg-primary-600 disabled:opacity-50 text-dark-950 text-xs font-medium px-4 py-1.5 rounded-lg transition-colors"
          >
            {voting ? t('forum.voting') : hasVoted ? t('forum.change_vote') : t('forum.vote')}
          </button>
        )}
        {user && !isVerified() && !isClosed && !hasVoted && (
          <span className="text-xs text-dark-500">{t('forum.verify_to_vote')}</span>
        )}
      </div>
    </motion.div>
  )
}
