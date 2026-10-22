// Achievement / badge templates and criteria fields.
//
// The backend auto-award pass (backend/app/tasks.py:run_achievement_award_pass)
// awards a badge once `getattr(user, field, 0) >= threshold` holds for EVERY
// key in the badge's `auto_award_criteria` JSON. So every `field` below MUST be
// a real numeric column on the User model (backend/app/models.py:User).

// Criteria fields the admin can pick from in the structured builder.
// `value` is the exact User column name written into auto_award_criteria.
export const CRITERIA_FIELDS = [
  { value: 'post_count', label: 'Posts written', unit: 'posts' },
  { value: 'thread_count', label: 'Threads created', unit: 'threads' },
  { value: 'like_count', label: 'Likes received', unit: 'likes' },
  { value: 'like_given_count', label: 'Likes given', unit: 'likes' },
  { value: 'rep_positive', label: 'Positive reputation', unit: 'rep' },
  { value: 'net_reputation', label: 'Net reputation (pos − neg)', unit: 'rep' },
  { value: 'level', label: 'Level reached', unit: 'level' },
  { value: 'xp', label: 'Total XP', unit: 'XP' },
  { value: 'account_age_days', label: 'Days as a member (since signup)', unit: 'days' },
  { value: 'login_streak', label: 'Login streak (consecutive days)', unit: 'days' },
  { value: 'balance', label: 'Current balance ($)', unit: '$' },
  { value: 'total_escrow_fees', label: 'Escrow fees paid ($)', unit: '$' },
  { value: 'referral_earnings', label: 'Referral earnings ($)', unit: '$' },
]

// Quick map for label/unit lookups by field name.
export const CRITERIA_FIELD_MAP = Object.fromEntries(
  CRITERIA_FIELDS.map(f => [f.value, f])
)

// Pre-defined templates. Selecting one prefills the whole badge form.
// `field: null` means "no auto-award" — a manual / purchasable badge that an
// admin grants via the award endpoint.
//
// `description` may contain `{n}` which is replaced with the chosen threshold.
export const ACHIEVEMENT_TEMPLATES = [
  {
    id: 'first-steps',
    label: 'First Steps',
    category: 'Posting',
    name: 'First Steps',
    description: 'Wrote your first {n} posts.',
    field: 'post_count',
    threshold: 10,
    icon: 'pen-square',
    color: '#22d3ee',
    icon_style: 'default',
    reward_xp: 100,
  },
  {
    id: 'prolific-poster',
    label: 'Prolific Poster',
    category: 'Posting',
    name: 'Prolific Poster',
    description: 'Reached {n} posts. A true regular.',
    field: 'post_count',
    threshold: 500,
    icon: 'messages-square',
    color: '#818cf8',
    icon_style: 'ring',
    reward_xp: 1000,
  },
  {
    id: 'thread-starter',
    label: 'Thread Starter',
    category: 'Posting',
    name: 'Thread Starter',
    description: 'Started {n} discussion threads.',
    field: 'thread_count',
    threshold: 25,
    icon: 'layout-list',
    color: '#34d399',
    icon_style: 'default',
    reward_xp: 500,
  },
  {
    id: 'well-liked',
    label: 'Well Liked',
    category: 'Engagement',
    name: 'Well Liked',
    description: 'Received {n} likes from the community.',
    field: 'like_count',
    threshold: 100,
    icon: 'thumbs-up',
    color: '#f472b6',
    icon_style: 'glow',
    reward_xp: 500,
  },
  {
    id: 'generous-soul',
    label: 'Generous Soul',
    category: 'Engagement',
    name: 'Generous Soul',
    description: 'Gave out {n} likes. Spreading the love.',
    field: 'like_given_count',
    threshold: 100,
    icon: 'heart-handshake',
    color: '#fb7185',
    icon_style: 'default',
    reward_xp: 300,
  },
  {
    id: 'trusted-member',
    label: 'Trusted Member',
    category: 'Reputation',
    name: 'Trusted Member',
    description: 'Earned {n} positive reputation.',
    field: 'rep_positive',
    threshold: 50,
    icon: 'shield-check',
    color: '#38bdf8',
    icon_style: 'ring',
    reward_xp: 750,
  },
  {
    id: 'level-milestone',
    label: 'Level Milestone',
    category: 'Progression',
    name: 'Level {n}',
    description: 'Reached level {n}.',
    field: 'level',
    threshold: 10,
    icon: 'star',
    color: '#facc15',
    icon_style: 'sparkle',
    reward_xp: 0,
  },
  {
    id: 'xp-grinder',
    label: 'XP Grinder',
    category: 'Progression',
    name: 'XP Grinder',
    description: 'Accumulated {n} total XP.',
    field: 'xp',
    threshold: 10000,
    icon: 'zap',
    color: '#a78bfa',
    icon_style: 'glow',
    reward_xp: 0,
  },
  {
    id: 'veteran',
    label: 'Veteran',
    category: 'Loyalty',
    name: 'Veteran',
    description: 'A member for {n} days.',
    field: 'account_age_days',
    threshold: 30,
    icon: 'calendar-days',
    color: '#60a5fa',
    icon_style: 'ring',
    reward_xp: 500,
    // Total membership time since signup — unlike login_streak this never resets.
    note: 'Counts total days since signup (never resets), unlike the login streak.',
  },
  {
    id: 'old-guard',
    label: 'Old Guard',
    category: 'Loyalty',
    name: 'Old Guard',
    description: 'A member for a full year ({n} days).',
    field: 'account_age_days',
    threshold: 365,
    icon: 'mountain',
    color: '#94a3b8',
    icon_style: 'glow',
    reward_xp: 2000,
  },
  {
    id: 'respected',
    label: 'Respected',
    category: 'Reputation',
    name: 'Respected',
    description: 'Reached {n} net reputation.',
    field: 'net_reputation',
    threshold: 100,
    icon: 'badge-check',
    color: '#4ade80',
    icon_style: 'ring',
    reward_xp: 1000,
  },
  {
    id: 'login-streak',
    label: 'Login Streak',
    category: 'Loyalty',
    name: '{n}-Day Streak',
    description: 'Logged in {n} days in a row.',
    field: 'login_streak',
    threshold: 30,
    icon: 'flame',
    color: '#f97316',
    icon_style: 'glow',
    reward_xp: 500,
    // login_streak RESETS to 1 the moment a day is missed (backend/app/routers/auth.py),
    // so this rewards *consecutive* days, not total membership days.
    note: 'Streak resets if the user misses a day — this is "30 days in a row", not "30 days as a member".',
  },
  {
    id: 'marketplace-vip',
    label: 'Marketplace VIP',
    category: 'Economy',
    name: 'Marketplace VIP',
    description: 'Paid ${n} in escrow fees across deals.',
    field: 'total_escrow_fees',
    threshold: 25,
    icon: 'gem',
    color: '#e879f9',
    icon_style: 'sparkle',
    reward_xp: 0,
    // total_escrow_fees accumulates the platform fee charged when a buyer funds
    // an escrow deal (backend/app/routers/escrow.py fund_deal).
    note: 'Tracks escrow fees paid across deals, not deposits.',
  },
  {
    id: 'referrer',
    label: 'Recruiter',
    category: 'Economy',
    name: 'Recruiter',
    description: 'Earned ${n} from referrals.',
    field: 'referral_earnings',
    threshold: 25,
    icon: 'user-plus',
    color: '#2dd4bf',
    icon_style: 'default',
    reward_xp: 0,
  },
  {
    id: 'manual-award',
    label: 'Manual / Custom',
    category: 'Manual',
    name: '',
    description: '',
    field: null,
    threshold: 0,
    icon: 'crown',
    color: '#fbbf24',
    icon_style: 'glow',
    reward_xp: 0,
    // No criteria — admin grants this by hand via the award endpoint.
    note: 'No auto-award rule. Grant this badge manually to specific users.',
  },
]

// Replace the {n} placeholder in a template description with the threshold.
export function fillTemplateText(text, threshold) {
  return (text || '').replace(/\{n\}/g, threshold)
}
