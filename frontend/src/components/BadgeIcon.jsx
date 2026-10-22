import {
  Anchor,
  Atom,
  Award,
  BadgeCheck,
  Banknote,
  Bell,
  Bird,
  Bookmark,
  Bot,
  Brain,
  Bug,
  CalendarDays,
  CircleDollarSign,
  Clock,
  Code,
  Coins,
  Compass,
  Crown,
  Crosshair,
  Diamond,
  Eye,
  Feather,
  Flame,
  Gamepad2,
  Gem,
  Ghost,
  Gift,
  GitPullRequest,
  Heart,
  HeartHandshake,
  Hexagon,
  Key,
  LayoutList,
  Leaf,
  Lightbulb,
  Lock,
  Medal,
  Megaphone,
  MessageCircle,
  MessagesSquare,
  MessageSquareQuote,
  Moon,
  Mountain,
  PenSquare,
  PiggyBank,
  Rocket,
  Shield,
  ShieldCheck,
  Skull,
  Snowflake,
  Sparkles,
  Sprout,
  Star,
  Sun,
  Sword,
  Swords,
  Target,
  Terminal,
  ThumbsUp,
  TrendingUp,
  Trophy,
  UserPlus,
  Users,
  VenetianMask,
  Wallet,
  Waves,
  Zap,
} from 'lucide-react'

// Map of icon-name (string stored on the badge) -> Lucide component.
// Keep keys kebab-case so they match Lucide's canonical names.
const ICON_MAP = {
  'anchor': Anchor,
  'atom': Atom,
  'award': Award,
  'badge-check': BadgeCheck,
  'banknote': Banknote,
  'bell': Bell,
  'bird': Bird,
  'bookmark': Bookmark,
  'bot': Bot,
  'brain': Brain,
  'bug': Bug,
  'calendar-days': CalendarDays,
  'circle-dollar-sign': CircleDollarSign,
  'clock': Clock,
  'code': Code,
  'coins': Coins,
  'compass': Compass,
  'crown': Crown,
  'crosshair': Crosshair,
  'diamond': Diamond,
  'eye': Eye,
  'feather': Feather,
  'flame': Flame,
  'gamepad-2': Gamepad2,
  'gem': Gem,
  'ghost': Ghost,
  'gift': Gift,
  'git-pull-request': GitPullRequest,
  'heart': Heart,
  'heart-handshake': HeartHandshake,
  'hexagon': Hexagon,
  'key': Key,
  'layout-list': LayoutList,
  'leaf': Leaf,
  'lightbulb': Lightbulb,
  'lock': Lock,
  'medal': Medal,
  'megaphone': Megaphone,
  'message-circle': MessageCircle,
  'messages-square': MessagesSquare,
  'message-square-quote': MessageSquareQuote,
  'moon': Moon,
  'mountain': Mountain,
  'pen-square': PenSquare,
  'piggy-bank': PiggyBank,
  'rocket': Rocket,
  'shield': Shield,
  'shield-check': ShieldCheck,
  'skull': Skull,
  'snowflake': Snowflake,
  'sparkles': Sparkles,
  'sprout': Sprout,
  'star': Star,
  'sun': Sun,
  'sword': Sword,
  'swords': Swords,
  'target': Target,
  'terminal': Terminal,
  'thumbs-up': ThumbsUp,
  'trending-up': TrendingUp,
  'trophy': Trophy,
  'user-plus': UserPlus,
  'users': Users,
  'venetian-mask': VenetianMask,
  'wallet': Wallet,
  'waves': Waves,
  'zap': Zap,
}

// Sorted list of available icon names — used by the admin icon picker.
export const ICON_NAMES = Object.keys(ICON_MAP).sort()

const STYLE_CLASSES = {
  default: '',
  ring: 'ring-2 ring-offset-1 ring-offset-dark-800/50',
  glow: 'shadow-lg',
  pulse: 'animate-[pulse_2s_ease-in-out_infinite]',
  sparkle: 'animate-[pulse_1.5s_ease-in-out_infinite]',
}

export default function BadgeIcon({ icon, iconStyle = 'default', size = 16, color = '#6366f1', className = '' }) {
  if (!icon) {
    return (
      <span
        className={`inline-block rounded ${className}`}
        style={{ width: size, height: size, backgroundColor: color }}
      />
    )
  }

  const IconComponent = ICON_MAP[icon]
  const styleClass = STYLE_CLASSES[iconStyle] || ''

  if (!IconComponent) {
    return (
      <span className={`text-xs ${styleClass} ${className}`} style={{ color }}>
        {icon}
      </span>
    )
  }

  const glowShadow = iconStyle === 'glow' ? `0 0 8px ${color}66` : undefined
  const sparkleShadow = iconStyle === 'sparkle' ? `0 0 6px ${color}99, 0 0 12px ${color}44` : undefined

  return (
    <span
      className={`inline-flex items-center justify-center rounded-lg ${styleClass} ${className}`}
      style={{
        boxShadow: sparkleShadow || glowShadow || undefined,
      }}
    >
      <IconComponent
        size={size}
        style={{ color, filter: iconStyle === 'glow' ? `drop-shadow(0 0 4px ${color}66)` : iconStyle === 'sparkle' ? `drop-shadow(0 0 6px ${color}99)` : undefined }}
      />
      {iconStyle === 'ring' && (
        <span
          className="absolute inset-0 rounded-lg pointer-events-none"
          style={{ boxShadow: `inset 0 0 0 2px ${color}66` }}
        />
      )}
      {iconStyle === 'sparkle' && (
        <Sparkles size={size * 0.45} className="absolute -top-0.5 -right-0.5" style={{ color }} />
      )}
    </span>
  )
}
