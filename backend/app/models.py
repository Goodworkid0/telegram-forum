"""Database Models for Forum Platform"""
from sqlalchemy import Column, Integer, BigInteger, String, Float, Numeric, Boolean, Date, DateTime, ForeignKey, Text, Enum as SQLEnum, Index, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.database import Base

# USD money: exact 2-decimal fixed point (SQLAlchemy returns Python Decimal).
# Crypto pay/payout amounts and percentage config stay Float (different precision).
MONEY = Numeric(14, 2)


# ============================================================================
# ENUMS
# ============================================================================

class UserRole(str, enum.Enum):
    """User roles with increasing permissions"""
    TRIAL = "TRIAL"          # New users — limited access until premium purchase or admin upgrade (no time limit)
    USER = "USER"            # Verified users
    MODERATOR = "MODERATOR"  # Forum moderators
    ADMIN = "ADMIN"          # Full access


class ThreadStatus(str, enum.Enum):
    """Thread states"""
    OPEN = "open"
    LOCKED = "locked"
    ARCHIVED = "archived"
    DELETED = "deleted"


class ReportStatus(str, enum.Enum):
    """Report states"""
    PENDING = "pending"
    REVIEWED = "reviewed"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class ReportType(str, enum.Enum):
    """Reportable content types"""
    POST = "post"
    THREAD = "thread"
    USER = "user"
    MESSAGE = "message"


class WithdrawalStatus(str, enum.Enum):
    """Withdrawal request states"""
    PENDING = "pending"
    PROCESSING = "processing"
    APPROVED = "approved"
    REJECTED = "rejected"
    FAILED = "failed"


class EscrowStatus(str, enum.Enum):
    """Escrow deal states"""
    PENDING = "pending"          # Created, waiting for counterparty
    ACCEPTED = "accepted"        # Both parties agreed
    FUNDED = "funded"            # Buyer deposited funds
    DELIVERED = "delivered"      # Seller marked as delivered
    COMPLETED = "completed"      # Buyer confirmed, funds released
    DISPUTED = "disputed"        # One party opened dispute
    CANCELLED = "cancelled"      # Deal cancelled
    REFUNDED = "refunded"        # Funds returned to buyer


# ============================================================================
# USER SYSTEM
# ============================================================================

class User(Base):
    """Forum user model"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(String, unique=True, index=True)
    # Always mirrors the user's Telegram @handle (synced on every login). Unique
    # so a handle can't be squatted via a concurrent login race; NULLs permitted
    # and distinct (users may have no handle). Users can only show/hide it —
    # visibility is chosen at setup and later changeable by premium users only.
    username = Column(String, nullable=True, unique=True, index=True)
    first_name = Column(String, nullable=True)
    avatar_url = Column(String, nullable=True)
    
    # Role & Status
    role = Column(SQLEnum(UserRole), default=UserRole.TRIAL)
    is_active = Column(Boolean, default=True)
    is_banned = Column(Boolean, default=False)
    ban_reason = Column(String, nullable=True)
    banned_at = Column(DateTime, nullable=True)
    ban_expires_at = Column(DateTime, nullable=True)
    banned_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    is_muted = Column(Boolean, default=False)
    mute_reason = Column(String, nullable=True)
    muted_at = Column(DateTime, nullable=True)
    mute_expires_at = Column(DateTime, nullable=True)  # None = permanent
    muted_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Auth
    token_version = Column(Integer, default=0)
    refresh_token_family = Column(String, nullable=True)  # UUID for rotation tracking
    refresh_token_version = Column(Integer, default=0)    # Increments per rotation; -1 = family invalidated
    
    # Balance (for premium, badges)
    balance = Column(MONEY, default=0.0)
    pending_balance = Column(MONEY, default=0.0)
    total_escrow_fees = Column(MONEY, default=0.0)  # Cumulative platform escrow fees this user has paid
    
    # Forum statistics
    post_count = Column(Integer, default=0)
    thread_count = Column(Integer, default=0)
    like_count = Column(Integer, default=0)       # Total likes received
    like_given_count = Column(Integer, default=0) # Total likes given
    
    # Reputation
    rep_positive = Column(Integer, default=0)
    rep_negative = Column(Integer, default=0)
    
    # Profile customization
    signature = Column(Text, nullable=True)           # Forum signature
    custom_title = Column(String, nullable=True)      # Purchasable custom title
    profile_banner_url = Column(String, nullable=True)
    profile_theme = Column(Text, nullable=True)       # JSON: custom colors
    profile_bio = Column(Text, nullable=True)         # About me
    notification_preferences = Column(Text, nullable=True)  # JSON notification prefs
    show_telegram = Column(Boolean, default=True)         # Whether to show @username publicly
    auto_response = Column(Text, nullable=True)          # Auto-reply message for DMs
    
    # Premium
    is_premium = Column(Boolean, default=False)
    premium_until = Column(DateTime, nullable=True)
    
    # XP & Leveling
    xp = Column(Integer, default=0)
    level = Column(Integer, default=1)
    
    # Daily streak
    login_streak = Column(Integer, default=0)
    last_login_date = Column(DateTime, nullable=True)
    streak_bonus_claimed = Column(Boolean, default=False)
    last_daily_claim_date = Column(Date, nullable=True)
    
    # Referral
    referral_code = Column(String, unique=True, nullable=True)
    referred_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    referral_earnings = Column(MONEY, default=0.0)  # Total earned from referral commissions

    # Account setup
    is_setup_complete = Column(Boolean, default=False)  # User completed onboarding
    pin_hash = Column(String, nullable=True)  # bcrypt hash of access PIN
    
    # Activity tracking
    last_seen_at = Column(DateTime, nullable=True)
    last_post_at = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    threads = relationship("Thread", back_populates="author", foreign_keys="Thread.author_id")
    posts = relationship("Post", back_populates="author", foreign_keys="Post.author_id")
    badges = relationship("UserBadge", back_populates="user")
    notifications = relationship("Notification", back_populates="user", foreign_keys="Notification.user_id")

    # Computed properties usable as badge auto_award_criteria fields. The
    # achievement pass (tasks.py:run_achievement_award_pass) compares
    # getattr(user, field, 0) in Python, so these need no DB column — they read
    # already-loaded columns and do not trigger any IO.
    @property
    def account_age_days(self) -> int:
        """Whole days since registration (total membership, not login streak)."""
        if not self.created_at:
            return 0
        return (datetime.utcnow() - self.created_at).days

    @property
    def net_reputation(self) -> int:
        """Positive reputation minus negative reputation."""
        return (self.rep_positive or 0) - (self.rep_negative or 0)


class UserFollow(Base):
    """User following system"""
    __tablename__ = "user_follows"
    __table_args__ = (
        UniqueConstraint('follower_id', 'following_id', name='uq_user_follow'),
    )

    id = Column(Integer, primary_key=True, index=True)
    follower_id = Column(Integer, ForeignKey("users.id"), index=True)
    following_id = Column(Integer, ForeignKey("users.id"), index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    follower = relationship("User", foreign_keys=[follower_id], backref="following")
    following = relationship("User", foreign_keys=[following_id], backref="followers")


# ============================================================================
# FORUM STRUCTURE
# ============================================================================

class ForumTab(Base):
    """Tabs for grouping sections on forum home"""
    __tablename__ = "forum_tabs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    slug = Column(String, unique=True, nullable=False, index=True)
    icon = Column(String, nullable=True)
    sort_order = Column(Integer, default=0)
    is_visible = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)  # Default tab for trial users
    min_role = Column(SQLEnum(UserRole), default=UserRole.TRIAL)  # Minimum role to view (ADMIN = admin-only)
    # If set, only users who hold this badge (or admins) can see/access the tab.
    required_badge_id = Column(Integer, ForeignKey("badges.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    sections = relationship("ForumSection", back_populates="tab", order_by="ForumSection.sort_order")


class ForumSection(Base):
    """Main forum sections (e.g., Gaming, Off-Topic, Services)"""
    __tablename__ = "forum_sections"

    id = Column(Integer, primary_key=True, index=True)
    tab_id = Column(Integer, ForeignKey("forum_tabs.id"), nullable=True, index=True)
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    icon = Column(String, nullable=True)  # Emoji or icon URL
    
    sort_order = Column(Integer, default=0)
    is_visible = Column(Boolean, default=True)
    can_trial_view = Column(Boolean, default=True)  # Deprecated - use min_role instead
    min_role = Column(SQLEnum(UserRole), default=UserRole.TRIAL)  # Minimum role to view section
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    tab = relationship("ForumTab", back_populates="sections")
    boards = relationship("ForumBoard", back_populates="section", order_by="ForumBoard.sort_order")


class ForumBoard(Base):
    """Sub-forums within sections — supports nesting via parent_id"""
    __tablename__ = "forum_boards"

    id = Column(Integer, primary_key=True, index=True)
    section_id = Column(Integer, ForeignKey("forum_sections.id"), index=True)
    parent_id = Column(Integer, ForeignKey("forum_boards.id"), nullable=True, index=True)
    
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    icon = Column(String, nullable=True)

    # 'forum' = normal board holding threads; 'link' = a shortcut row that points
    # at another page (e.g. /leaderboard, /giveaways, or an external URL) instead
    # of containing threads. link_target holds the destination for link boards.
    board_type = Column(String, nullable=False, default="forum")
    link_target = Column(String, nullable=True)

    sort_order = Column(Integer, default=0)
    is_visible = Column(Boolean, default=True)
    is_locked = Column(Boolean, default=False)  # Only admins can post
    
    # Permissions
    min_role = Column(SQLEnum(UserRole), default=UserRole.TRIAL)  # Minimum role to view board
    can_trial_view = Column(Boolean, default=True)  # Deprecated - use min_role
    can_trial_post = Column(Boolean, default=False)
    min_role_to_post = Column(SQLEnum(UserRole), default=UserRole.USER)
    min_role_to_create_thread = Column(SQLEnum(UserRole), default=UserRole.USER)
    
    # Statistics (denormalized for performance)
    thread_count = Column(Integer, default=0)
    post_count = Column(Integer, default=0)
    
    # Last activity tracking
    last_thread_id = Column(Integer, ForeignKey("threads.id", use_alter=True), nullable=True)
    last_post_id = Column(Integer, ForeignKey("posts.id", use_alter=True), nullable=True)
    last_post_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    section = relationship("ForumSection", back_populates="boards")
    last_thread = relationship("Thread", foreign_keys=[last_thread_id])
    threads = relationship("Thread", back_populates="board", foreign_keys="Thread.board_id")
    parent = relationship("ForumBoard", remote_side=[id], back_populates="children")
    children = relationship("ForumBoard", back_populates="parent", order_by="ForumBoard.sort_order")


class Thread(Base):
    """Forum threads/topics"""
    __tablename__ = "threads"

    id = Column(Integer, primary_key=True, index=True)
    board_id = Column(Integer, ForeignKey("forum_boards.id"), index=True)
    author_id = Column(Integer, ForeignKey("users.id"), index=True)
    
    title = Column(String(300), nullable=False)
    slug = Column(String(350), nullable=True, index=True)
    content = Column(Text, nullable=False)  # Thread body (first post)
    
    status = Column(SQLEnum(ThreadStatus), default=ThreadStatus.OPEN, index=True)
    
    # Thread flags
    is_pinned = Column(Boolean, default=False, index=True)
    is_announcement = Column(Boolean, default=False)  # Shows in all boards
    is_featured = Column(Boolean, default=False)      # Featured on home
    
    # Tags (comma-separated)
    tags = Column(Text, nullable=True)
    
    # Statistics
    view_count = Column(Integer, default=0)
    reply_count = Column(Integer, default=0)
    like_count = Column(Integer, default=0)
    
    # Last activity (for sorting/display)
    last_post_id = Column(Integer, ForeignKey("posts.id", use_alter=True), nullable=True)
    last_post_at = Column(DateTime, nullable=True)
    last_post_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Edit tracking
    is_edited = Column(Boolean, default=False)
    edited_at = Column(DateTime, nullable=True)
    edit_count = Column(Integer, default=0)

    # Paid/cosmetic upgrades
    title_color = Column(String, nullable=True)        # hex color for a stand-out title
    title_glow = Column(Boolean, default=False)        # glow effect on the title
    last_manual_bump_at = Column(DateTime, nullable=True)  # free manual bump cooldown (48h)
    auto_bump_until = Column(DateTime, nullable=True)   # paid auto-bump active until (None = off)
    last_auto_bump_at = Column(DateTime, nullable=True) # scheduler: last auto-bump time

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    bumped_at = Column(DateTime, default=datetime.utcnow, index=True)  # For bump logic
    
    # Relationships
    board = relationship("ForumBoard", back_populates="threads", foreign_keys=[board_id])
    author = relationship("User", back_populates="threads", foreign_keys=[author_id])
    last_post_by = relationship("User", foreign_keys=[last_post_by_id])
    posts = relationship("Post", back_populates="thread", foreign_keys="Post.thread_id")
    poll = relationship("Poll", back_populates="thread", uselist=False, foreign_keys="Poll.thread_id")


class Post(Base):
    """Thread replies"""
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)
    thread_id = Column(Integer, ForeignKey("threads.id"), index=True)
    author_id = Column(Integer, ForeignKey("users.id"), index=True)
    parent_id = Column(Integer, ForeignKey("posts.id"), nullable=True, index=True)  # Reply to specific post
    
    content = Column(Text, nullable=False)
    
    # Edit tracking
    is_edited = Column(Boolean, default=False)
    edited_at = Column(DateTime, nullable=True)
    edit_count = Column(Integer, default=0)
    
    # Statistics
    like_count = Column(Integer, default=0)
    
    # Special flags
    is_best_answer = Column(Boolean, default=False)  # Thread author can mark
    
    # Soft delete
    is_deleted = Column(Boolean, default=False)
    deleted_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    deleted_at = Column(DateTime, nullable=True)
    delete_reason = Column(String, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    thread = relationship("Thread", back_populates="posts", foreign_keys=[thread_id])
    author = relationship("User", back_populates="posts", foreign_keys=[author_id])
    parent = relationship("Post", remote_side=[id], backref="replies")
    likes = relationship("PostLike", back_populates="post")


class PostLike(Base):
    """Post likes/reactions"""
    __tablename__ = "post_likes"
    __table_args__ = (
        UniqueConstraint('post_id', 'user_id', name='uq_post_like'),
    )

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id"), index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    post = relationship("Post", back_populates="likes")
    user = relationship("User")


class ThreadLike(Base):
    """Thread likes (for the OP)"""
    __tablename__ = "thread_likes"
    __table_args__ = (
        UniqueConstraint('thread_id', 'user_id', name='uq_thread_like'),
    )

    id = Column(Integer, primary_key=True, index=True)
    thread_id = Column(Integer, ForeignKey("threads.id"), index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    thread = relationship("Thread")
    user = relationship("User")


class ThreadView(Base):
    """Track user read state for threads"""
    __tablename__ = "thread_views"
    __table_args__ = (
        UniqueConstraint('thread_id', 'user_id', name='uq_thread_view'),
    )

    id = Column(Integer, primary_key=True, index=True)
    thread_id = Column(Integer, ForeignKey("threads.id"), index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    last_read_post_id = Column(Integer, ForeignKey("posts.id"), nullable=True)
    last_viewed_at = Column(DateTime, default=datetime.utcnow)
    
    thread = relationship("Thread")
    user = relationship("User")


class ThreadWatch(Base):
    """Users watching a thread for notifications"""
    __tablename__ = "thread_watches"
    __table_args__ = (
        UniqueConstraint('thread_id', 'user_id', name='uq_thread_watch'),
    )

    id = Column(Integer, primary_key=True, index=True)
    thread_id = Column(Integer, ForeignKey("threads.id"), index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    thread = relationship("Thread")
    user = relationship("User")


# ============================================================================
# REPUTATION SYSTEM
# ============================================================================

class ReputationEntry(Base):
    """Reputation history (+rep / -rep)"""
    __tablename__ = "reputation_entries"

    id = Column(Integer, primary_key=True, index=True)
    from_user_id = Column(Integer, ForeignKey("users.id"), index=True)
    to_user_id = Column(Integer, ForeignKey("users.id"), index=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=True)
    thread_id = Column(Integer, ForeignKey("threads.id"), nullable=True)
    
    is_positive = Column(Boolean, nullable=False)  # True = +rep, False = -rep
    comment = Column(String(200), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    from_user = relationship("User", foreign_keys=[from_user_id])
    to_user = relationship("User", foreign_keys=[to_user_id])
    post = relationship("Post")
    thread = relationship("Thread")


# ============================================================================
# BADGE SYSTEM
# ============================================================================

class Badge(Base):
    """Available badges"""
    __tablename__ = "badges"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    description = Column(Text, nullable=True)
    icon_url = Column(String, nullable=True)
    icon = Column(String, nullable=True)     # Lucide icon name (e.g., "flame", "star")
    icon_style = Column(String, default="default")  # Visual style: default, ring, glow, pulse, sparkle
    color = Column(String, default="#6366f1")  # Hex color
    
    # Purchase settings
    is_purchasable = Column(Boolean, default=False)
    price = Column(MONEY, default=0.0)
    multi_purchase = Column(Boolean, default=False)  # Can be purchased multiple times
    
    # Limited edition
    is_limited = Column(Boolean, default=False)
    max_supply = Column(Integer, nullable=True)
    current_supply = Column(Integer, default=0)
    
    # Auto-award criteria (JSON for flexible rules)
    auto_award_criteria = Column(Text, nullable=True)  # e.g., {"post_count": 100}
    
    # Rewards granted when badge is earned via achievement or purchase
    reward_xp = Column(Integer, default=0)
    reward_balance = Column(MONEY, default=0.0)
    reward_role = Column(String, nullable=True)  # e.g., 'USER' — upgrades user role on purchase
    
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class UserBadge(Base):
    """User's acquired badges"""
    __tablename__ = "user_badges"
    __table_args__ = (
        UniqueConstraint('user_id', 'badge_id', name='uq_user_badge'),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    badge_id = Column(Integer, ForeignKey("badges.id"), index=True)
    
    is_primary = Column(Boolean, default=False)  # Shows next to username
    is_hidden = Column(Boolean, default=False)   # User can hide badges
    
    acquired_at = Column(DateTime, default=datetime.utcnow)
    acquired_type = Column(String, default="purchase")  # purchase, achievement, gift, admin
    quantity = Column(Integer, default=1)  # For multi-purchase badges
    
    user = relationship("User", back_populates="badges")
    badge = relationship("Badge")


# ============================================================================
# POLL SYSTEM
# ============================================================================

class Poll(Base):
    """Thread polls"""
    __tablename__ = "polls"

    id = Column(Integer, primary_key=True, index=True)
    thread_id = Column(Integer, ForeignKey("threads.id", use_alter=True), nullable=True, index=True)
    author_id = Column(Integer, ForeignKey("users.id"), index=True)
    
    question = Column(String(500), nullable=False)
    
    is_multiple_choice = Column(Boolean, default=False)
    max_choices = Column(Integer, default=1)
    
    # Settings
    is_anonymous = Column(Boolean, default=False)  # Hide who voted for what
    show_results_before_vote = Column(Boolean, default=False)
    allow_vote_change = Column(Boolean, default=True)
    
    ends_at = Column(DateTime, nullable=True)
    is_closed = Column(Boolean, default=False)
    
    total_votes = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    thread = relationship("Thread", back_populates="poll", foreign_keys=[thread_id])
    author = relationship("User")
    options = relationship("PollOption", back_populates="poll", order_by="PollOption.sort_order")


class PollOption(Base):
    """Poll options"""
    __tablename__ = "poll_options"

    id = Column(Integer, primary_key=True, index=True)
    poll_id = Column(Integer, ForeignKey("polls.id"), index=True)
    
    text = Column(String(200), nullable=False)
    vote_count = Column(Integer, default=0)
    sort_order = Column(Integer, default=0)
    
    poll = relationship("Poll", back_populates="options")
    votes = relationship("PollVote", back_populates="option")


class PollVote(Base):
    """User poll votes"""
    __tablename__ = "poll_votes"
    __table_args__ = (
        UniqueConstraint('poll_id', 'option_id', 'user_id', name='uq_poll_vote'),
    )

    id = Column(Integer, primary_key=True, index=True)
    poll_id = Column(Integer, ForeignKey("polls.id"), index=True)
    option_id = Column(Integer, ForeignKey("poll_options.id"), index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    poll = relationship("Poll")
    option = relationship("PollOption", back_populates="votes")
    user = relationship("User")


# ============================================================================
# REPORTS & MODERATION
# ============================================================================

class Report(Base):
    """Content reports"""
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    reporter_id = Column(Integer, ForeignKey("users.id"), index=True)
    
    report_type = Column(SQLEnum(ReportType), nullable=False)
    thread_id = Column(Integer, ForeignKey("threads.id"), nullable=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=True)
    reported_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    reason = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    
    status = Column(SQLEnum(ReportStatus), default=ReportStatus.PENDING, index=True)
    
    resolved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    mod_notes = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    reporter = relationship("User", foreign_keys=[reporter_id])
    reported_user = relationship("User", foreign_keys=[reported_user_id])
    resolved_by_user = relationship("User", foreign_keys=[resolved_by])
    thread = relationship("Thread", foreign_keys=[thread_id])
    post = relationship("Post", foreign_keys=[post_id])


class ModAction(Base):
    """Moderator action log"""
    __tablename__ = "mod_actions"

    id = Column(Integer, primary_key=True, index=True)
    moderator_id = Column(Integer, ForeignKey("users.id"), index=True)
    target_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    
    action_type = Column(String, nullable=False)  # ban, warn, delete_post, lock_thread, etc.
    
    
    reason = Column(Text, nullable=True)
    details = Column(Text, nullable=True)  # JSON for additional details
    notes = Column(Text, nullable=True)
    thread_id = Column(Integer, ForeignKey("threads.id"), nullable=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=True)
    expires_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    moderator = relationship("User", foreign_keys=[moderator_id])
    target_user = relationship("User", foreign_keys=[target_user_id])


# ============================================================================
# NOTIFICATIONS
# ============================================================================

class Notification(Base):
    """User notifications"""
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    
    type = Column(String, nullable=False)  # reply, mention, like, rep, badge, etc.
    title = Column(String, nullable=False)
    body = Column(Text, nullable=True)
    link = Column(String, nullable=True)  # e.g., /t/123
    
    # Related entities (optional, for grouping/dedup)
    related_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    related_thread_id = Column(Integer, ForeignKey("threads.id"), nullable=True)
    related_post_id = Column(Integer, ForeignKey("posts.id"), nullable=True)
    
    is_read = Column(Boolean, default=False, index=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="notifications", foreign_keys=[user_id])
    related_user = relationship("User", foreign_keys=[related_user_id])


# ============================================================================
# DIRECT MESSAGES (kept from original)
# ============================================================================

class DirectConversation(Base):
    """Direct message conversation between two users"""
    __tablename__ = "direct_conversations"
    __table_args__ = (
        UniqueConstraint('user1_id', 'user2_id', name='uq_direct_conversation'),
    )

    id = Column(Integer, primary_key=True, index=True)
    user1_id = Column(Integer, ForeignKey("users.id"), index=True)  # Lower ID
    user2_id = Column(Integer, ForeignKey("users.id"), index=True)  # Higher ID

    # Optional context for how the conversation started
    context_type = Column(String(50), nullable=True)
    context_id = Column(Integer, nullable=True)
    context_label = Column(String(200), nullable=True)

    is_active = Column(Boolean, default=True)
    last_message_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    user1 = relationship("User", foreign_keys=[user1_id])
    user2 = relationship("User", foreign_keys=[user2_id])
    messages = relationship("DirectMessage", back_populates="conversation", order_by="DirectMessage.created_at")


class DirectMessage(Base):
    """Message in a direct conversation"""
    __tablename__ = "direct_messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("direct_conversations.id"), index=True)
    sender_id = Column(Integer, ForeignKey("users.id"), index=True)

    content = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)
    is_edited = Column(Boolean, default=False)
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    conversation = relationship("DirectConversation", back_populates="messages")
    sender = relationship("User", foreign_keys=[sender_id])


# ============================================================================
# WALLET & PAYMENTS (kept from original)
# ============================================================================

class CryptoDeposit(Base):
    """Crypto deposit records"""
    __tablename__ = "crypto_deposits"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)

    order_id = Column(String, unique=True, index=True)
    payment_id = Column(String, unique=True, index=True, nullable=True)

    price_amount = Column(MONEY)
    price_currency = Column(String)
    price_amount_usd = Column(MONEY, default=0.0)

    pay_amount = Column(Float, nullable=True)
    pay_currency = Column(String, nullable=True)
    pay_address = Column(String, nullable=True)
    payment_status = Column(String, default="created")
    tx_hash = Column(String, nullable=True)
    confirmations = Column(Integer, default=0)
    is_credited = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    user = relationship("User", foreign_keys=[user_id])


class WithdrawalRequest(Base):
    """Withdrawal requests"""
    __tablename__ = "withdrawal_requests"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    # Client-supplied key to make withdrawal submission idempotent (a retried
    # request with the same key returns the original withdrawal instead of
    # creating a second payout).
    idempotency_key = Column(String, nullable=True, unique=True, index=True)

    amount = Column(MONEY, nullable=False)
    destination = Column(String, nullable=True)
    status = Column(SQLEnum(WithdrawalStatus), default=WithdrawalStatus.PENDING)
    admin_note = Column(Text, nullable=True)
    processed_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)

    # Payout tracking
    payout_hash = Column(String, nullable=True)
    payout_currency = Column(String, default="usdterc20")
    fee_amount = Column(MONEY, default=0.0)
    net_amount = Column(MONEY, nullable=True)

    user = relationship("User", foreign_keys=[user_id])


class LedgerEntry(Base):
    """Append-only ledger of every balance change.

    One immutable row per movement of a user's spendable `balance` or escrow
    `pending` balance. `amount` is the signed effective delta and `balance_after`
    is the account value right after applying it, so the running sum of `amount`
    for a (user, account) must always equal the user's current balance —
    enabling audit and reconciliation. Never UPDATE or DELETE these rows.
    """
    __tablename__ = "ledger_entries"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    # Which account moved: 'balance' (spendable) or 'pending' (escrow hold).
    account = Column(String, default="balance", nullable=False, index=True)
    amount = Column(MONEY, nullable=False)         # signed effective delta
    balance_after = Column(MONEY, nullable=False)  # account value after applying
    entry_type = Column(String, nullable=False, index=True)  # deposit/withdrawal/escrow_*/donation/...
    ref_type = Column(String, nullable=True)       # e.g. crypto_deposit / withdrawal_request / escrow_deal
    ref_id = Column(Integer, nullable=True)
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    user = relationship("User", foreign_keys=[user_id])

    __table_args__ = (
        Index("ix_ledger_user_account", "user_id", "account"),
        Index("ix_ledger_ref", "ref_type", "ref_id"),
    )




# ============================================================================
# GIVEAWAYS (kept from original)
# ============================================================================

class Giveaway(Base):
    """Giveaways"""
    __tablename__ = "giveaways"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    prize = Column(String(200), nullable=True)

    enabled = Column(Boolean, default=True)
    deposit_required = Column(Boolean, default=False)
    auto_pick_winner = Column(Boolean, default=False)

    starts_at = Column(DateTime, nullable=True)
    ends_at = Column(DateTime, nullable=True)

    winner_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    winner_picked_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    winner_user = relationship("User", foreign_keys=[winner_user_id])
    entries = relationship("GiveawayEntry", back_populates="giveaway")


class GiveawayEntry(Base):
    """Giveaway entries"""
    __tablename__ = "giveaway_entries"
    __table_args__ = (
        UniqueConstraint('giveaway_id', 'user_id', name='uq_giveaway_entry'),
    )

    id = Column(Integer, primary_key=True, index=True)
    giveaway_id = Column(Integer, ForeignKey("giveaways.id"), index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    giveaway = relationship("Giveaway", back_populates="entries")
    user = relationship("User")


# ============================================================================
# ESCROW SYSTEM
# ============================================================================

class EscrowDeal(Base):
    """Escrow deals between two users"""
    __tablename__ = "escrow_deals"

    id = Column(Integer, primary_key=True, index=True)
    buyer_id = Column(Integer, ForeignKey("users.id"), index=True)
    seller_id = Column(Integer, ForeignKey("users.id"), index=True)

    title = Column(String(300), nullable=False)
    description = Column(Text, nullable=True)
    amount = Column(MONEY, nullable=False)
    
    status = Column(SQLEnum(EscrowStatus), default=EscrowStatus.PENDING, index=True)
    
    # Hold period (buyer chooses at funding time)
    hold_days = Column(Integer, nullable=True)  # 1, 2, 7, 14, 30 — buyer's chosen hold period
    hold_ends_at = Column(DateTime, nullable=True)  # Timestamp when hold expires
    
    # Fee
    fee_amount = Column(MONEY, default=0.0)  # Platform fee deducted

    # Dispute handling
    dispute_reason = Column(Text, nullable=True)
    dispute_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    resolved_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    resolution_note = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    buyer = relationship("User", foreign_keys=[buyer_id])
    seller = relationship("User", foreign_keys=[seller_id])
    dispute_by = relationship("User", foreign_keys=[dispute_by_id])
    resolved_by = relationship("User", foreign_keys=[resolved_by_id])
    messages = relationship("EscrowMessage", back_populates="deal", order_by="EscrowMessage.created_at")


class EscrowMessage(Base):
    """Chat messages within an escrow deal"""
    __tablename__ = "escrow_messages"

    id = Column(Integer, primary_key=True, index=True)
    deal_id = Column(Integer, ForeignKey("escrow_deals.id"), index=True)
    sender_id = Column(Integer, ForeignKey("users.id"), index=True)
    
    content = Column(Text, nullable=False)
    is_system = Column(Boolean, default=False)  # System messages (status changes)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    deal = relationship("EscrowDeal", back_populates="messages")
    sender = relationship("User", foreign_keys=[sender_id])


class EscrowInvite(Base):
    """Shareable single-use code that invites a counterparty into a deal.

    The creator fixes the terms (their role, title, amount); the redeemer
    consents by accepting, which creates the deal directly in ACCEPTED state.
    Avoids addressing users by @handle (which may be hidden)."""
    __tablename__ = "escrow_invites"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(16), unique=True, index=True, nullable=False)
    creator_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    creator_role = Column(String(8), nullable=False)  # 'buyer' | 'seller'

    title = Column(String(300), nullable=False)
    description = Column(Text, nullable=True)
    amount = Column(MONEY, nullable=False)
    hold_days = Column(Integer, nullable=True)

    used_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    deal_id = Column(Integer, ForeignKey("escrow_deals.id"), nullable=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    creator = relationship("User", foreign_keys=[creator_id])


class SharedFileStatus(str, enum.Enum):
    """Moderation state of a user-dropped file on the public file board."""
    PENDING = "PENDING"    # dropped in the bot, awaiting ACP approval
    APPROVED = "APPROVED"  # visible on the board
    REJECTED = "REJECTED"  # hidden (kept in channels as archive)


class FileCategory(Base):
    """Admin-created category files are sorted into at approval time. Files with
    no category show as 'Uncategorized' on the board."""
    __tablename__ = "file_categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(80), unique=True, nullable=False)
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class SharedFile(Base):
    """A file a user dropped into the bot, mirrored to the retrieval + backup
    channels and (once approved) listed on the public file board.

    We never re-host bytes: delivery is the bot re-sending by `file_id`. The
    DURABLE anchor is (retrieval_chat_id, retrieval_message_id) — `file_id` is a
    per-bot cache that can be regenerated by forwarding the channel message if
    the bot token/identity ever changes. `file_unique_id` is the stable dedup
    key (also stable across bots, but not usable to send)."""
    __tablename__ = "shared_files"

    id = Column(Integer, primary_key=True, index=True)

    # Stable dedup key across bots (NOT sendable). Unique so the same file
    # dropped twice doesn't create two board entries.
    file_unique_id = Column(String(128), unique=True, index=True, nullable=False)
    # Current sendable handle for the retrieval bot — regenerable cache.
    file_id = Column(Text, nullable=False)

    kind = Column(String(16), nullable=False, default="document")  # document/photo/video/audio/voice
    category_id = Column(Integer, ForeignKey("file_categories.id"), nullable=True, index=True)  # admin's final assignment
    suggested_category_id = Column(Integer, ForeignKey("file_categories.id"), nullable=True)     # uploader's suggestion
    file_name = Column(String(300), nullable=True)
    mime_type = Column(String(128), nullable=True)
    file_size = Column(BigInteger, nullable=True)  # bytes; BigInteger — a 2GB+ file overflows int4
    caption = Column(Text, nullable=True)

    # Uploader: mapped User when registered, plus the raw tg id for attribution.
    uploader_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    uploader_tg_id = Column(String(32), nullable=True, index=True)

    # Durable anchors in the two channels (message ids never change).
    retrieval_chat_id = Column(String(32), nullable=True)
    retrieval_message_id = Column(Integer, nullable=True)
    backup_chat_id = Column(String(32), nullable=True)
    backup_message_id = Column(Integer, nullable=True)

    status = Column(SQLEnum(SharedFileStatus), default=SharedFileStatus.PENDING, nullable=False, index=True)
    reviewed_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    reject_reason = Column(String(300), nullable=True)

    download_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    uploader = relationship("User", foreign_keys=[uploader_id])
    category = relationship("FileCategory", foreign_keys=[category_id])
    suggested_category = relationship("FileCategory", foreign_keys=[suggested_category_id])


class BroadcastStatus(str, enum.Enum):
    PENDING = "PENDING"    # queued, waiting for the worker
    SENDING = "SENDING"    # worker is delivering
    DONE = "DONE"
    FAILED = "FAILED"


class Broadcast(Base):
    """An admin advertisement/announcement fanned out to users' in-app inbox
    and/or Telegram DM by the background worker (throttled to respect Telegram
    flood limits). Targets everyone or a single role."""
    __tablename__ = "broadcasts"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    body = Column(Text, nullable=True)
    link = Column(String(500), nullable=True)

    send_inbox = Column(Boolean, default=True)
    send_bot = Column(Boolean, default=False)
    target_role = Column(String(16), nullable=True)  # None = all users

    status = Column(SQLEnum(BroadcastStatus), default=BroadcastStatus.PENDING, nullable=False, index=True)
    total_recipients = Column(Integer, default=0)
    sent_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    # Resume cursor: highest user id already delivered to. Lets a broadcast that
    # was interrupted (worker restart / leadership flap) resume without
    # re-delivering to users it already reached.
    last_delivered_user_id = Column(Integer, default=0)

    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)


# ============================================================================
# BANNERS & SETTINGS
# ============================================================================

class Banner(Base):
    """Promotional banners"""
    __tablename__ = "banners"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    subtitle = Column(String, nullable=True)
    image_url = Column(String, nullable=True)
    link = Column(String, nullable=True)
    link_text = Column(String, default="Learn More")
    gradient_from = Column(String, default="primary-500")
    gradient_to = Column(String, default="accent-purple")
    position = Column(String, default="home_row_1")  # home_row_1, home_row_2, home_row_3, home_row_4
    is_active = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class AppSettings(Base):
    """Singleton settings table — always ID=1"""
    __tablename__ = "app_settings"

    id = Column(Integer, primary_key=True, default=1)
    app_name = Column(String, default="Forum")
    logo_url = Column(String, nullable=True)
    show_logo = Column(Boolean, default=True)
    bot_username = Column(String, default="ForumBot")
    maintenance_mode = Column(Boolean, default=False)
    
    # Links
    announcements_url = Column(String, nullable=True)
    official_group_url = Column(String, nullable=True)
    
    # Fee settings
    withdrawal_fee_percent = Column(Float, default=0.0)
    escrow_fee_percent = Column(Float, default=0.0)  # Platform fee on escrow deals
    min_deposit_amount = Column(MONEY, default=10.0)
    min_withdrawal_amount = Column(MONEY, default=10.0)
    # Admin-curated deposit coins (comma-separated NOWPayments tickers, e.g.
    # "btc,ltc,eth,xmr,usdttrc20"). NULL/empty => legacy default set.
    enabled_deposit_coins = Column(String, nullable=True)

    # Escrow settings
    max_active_escrow_deals = Column(Integer, default=3)  # Max concurrent deals per user
    
    # Referral settings
    referral_enabled = Column(Boolean, default=False)
    referral_level1_percent = Column(Float, default=3.0)   # Commission on direct referrals' deposits
    referral_level2_percent = Column(Float, default=5.0)   # Commission on indirect referrals' deposits
    
    # Forum settings
    trial_mode_enabled = Column(Boolean, default=True)  # False => new users get USER role directly
    min_posts_for_dm = Column(Integer, default=5)      # Min posts before DM allowed
    min_posts_for_rep = Column(Integer, default=10)    # Min posts before giving rep
    
    # Rate limits
    max_posts_per_hour = Column(Integer, default=30)
    max_threads_per_day = Column(Integer, default=10)
    max_pm_per_minute = Column(Integer, default=1)
    
    # Support
    support_username = Column(String, nullable=True)
    support_display_name = Column(String, nullable=True)
    
    # Leaderboard
    leaderboard_rewards = Column(String, nullable=True)  # JSON array: [1000, 750, 500, ...]

    # Shop prices (admin-configurable)
    premium_price = Column(MONEY, default=80.0)
    name_change_price = Column(MONEY, default=20.0)
    thread_title_price = Column(MONEY, default=20.0)
    thread_autobump_price = Column(MONEY, default=60.0)

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DailyRewardConfig(Base):
    __tablename__ = "daily_reward_config"

    id = Column(Integer, primary_key=True, index=True)
    day = Column(Integer, nullable=False, unique=True)
    xp_amount = Column(Integer, default=10)
    balance_amount = Column(MONEY, default=0.10)
    badge_id = Column(Integer, ForeignKey("badges.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    badge = relationship("Badge", foreign_keys=[badge_id])


# ============================================================================
# LIVE CHAT (SHOUTBOX)
# ============================================================================

class ChatMessage(Base):
    """Live chat / shoutbox messages"""
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    content = Column(Text, nullable=False)
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    user = relationship("User")


# ============================================================================
# LEADERBOARD SCORING
# ============================================================================

class LeaderboardPeriod(Base):
    """3-day leaderboard period"""
    __tablename__ = "leaderboard_periods"

    id = Column(Integer, primary_key=True, index=True)
    starts_at = Column(DateTime, default=datetime.utcnow)
    ends_at = Column(DateTime, nullable=False)
    is_active = Column(Boolean, default=True, index=True)
    rewards_distributed = Column(Boolean, default=False)


class LeaderboardScore(Base):
    """Per-user score within a leaderboard period"""
    __tablename__ = "leaderboard_scores"
    __table_args__ = (
        UniqueConstraint('user_id', 'period_id', name='uq_user_period_score'),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    period_id = Column(Integer, ForeignKey("leaderboard_periods.id"), index=True)
    score = Column(Integer, default=0)
    post_count = Column(Integer, default=0)
    thread_count = Column(Integer, default=0)
    likes_received = Column(Integer, default=0)
    likes_given = Column(Integer, default=0)
    rep_received = Column(Integer, default=0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User")
