"""Pydantic Schemas for Forum Platform"""
from __future__ import annotations
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from typing import Optional, List, Any, TYPE_CHECKING
from datetime import datetime, date
from app.models import UserRole, ThreadStatus, ReportStatus, ReportType


# Staff (moderators/admins) always get premium perks without owning the Premium
# badge. Applied at the serialization boundary so it covers every endpoint —
# both the ones that build a response manually and the ones that serialize the
# ORM model via from_attributes. The stored is_premium column is untouched.
_STAFF_ROLES = (UserRole.MODERATOR, UserRole.ADMIN)


def _apply_staff_premium(model):
    if not model.is_premium and model.role in _STAFF_ROLES:
        model.is_premium = True
    return model


# ============================================================================
# AUTH SCHEMAS
# ============================================================================

class Token(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"


# ============================================================================
# USER SCHEMAS
# ============================================================================

class UserContactUpdate(BaseModel):
    """Update profile info. Display name (first_name) is NOT here — it's set free
    at onboarding and changed only via the paid POST /users/me/display-name ($20)."""
    profile_bio: Optional[str] = Field(None, max_length=2000)
    signature: Optional[str] = Field(None, max_length=500)
    custom_title: Optional[str] = Field(None, max_length=50)
    profile_theme: Optional[str] = None  # JSON: {avatar_border, name_color, avatar_glow}
    notification_preferences: Optional[dict] = None
    show_telegram: Optional[bool] = None


class UserResponse(BaseModel):
    id: int
    telegram_id: str
    username: Optional[str] = None
    first_name: Optional[str] = None
    avatar_url: Optional[str] = None
    role: UserRole
    is_active: bool = True
    is_banned: bool = False
    ban_reason: Optional[str] = None
    is_muted: bool = False
    mute_reason: Optional[str] = None
    mute_expires_at: Optional[datetime] = None

    # Balance
    balance: float = 0.0
    pending_balance: float = 0.0
    referral_earnings: float = 0.0
    
    # Stats
    post_count: int = 0
    thread_count: int = 0
    like_count: int = 0
    rep_positive: int = 0
    rep_negative: int = 0
    
    # Profile
    signature: Optional[str] = None
    custom_title: Optional[str] = None
    profile_banner_url: Optional[str] = None
    profile_bio: Optional[str] = None
    profile_theme: Optional[str] = None
    notification_preferences: Optional[dict] = None
    show_telegram: bool = True
    
    # Timestamps
    created_at: datetime
    last_seen_at: Optional[datetime] = None
    
    # XP & Leveling
    xp: int = 0
    level: int = 1
    login_streak: int = 0
    
    # Badges (populated separately)
    primary_badge: Optional["BadgeResponse"] = None
    
    # Premium
    is_premium: bool = False
    premium_until: Optional[datetime] = None

    # Account setup
    is_setup_complete: bool = False
    
    @field_validator('is_banned', mode='before')
    @classmethod
    def default_is_banned(cls, v):
        return v if v is not None else False
    
    @field_validator('notification_preferences', mode='before')
    @classmethod
    def parse_notification_preferences(cls, v):
        if isinstance(v, str):
            import json
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return None
        return v

    @field_validator('post_count', 'thread_count', 'like_count', 'rep_positive', 'rep_negative', mode='before')
    @classmethod
    def default_int(cls, v):
        return v if v is not None else 0

    @model_validator(mode='after')
    def _staff_premium(self):
        return _apply_staff_premium(self)

    model_config = ConfigDict(from_attributes=True)


class UserPublicProfile(BaseModel):
    """Public profile view (for other users viewing)"""
    id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    avatar_url: Optional[str] = None
    role: UserRole
    
    # Stats
    post_count: int = 0
    thread_count: int = 0
    like_count: int = 0
    rep_positive: int = 0
    rep_negative: int = 0
    referral_earnings: float = 0.0
    
    # Profile
    signature: Optional[str] = None
    custom_title: Optional[str] = None
    profile_banner_url: Optional[str] = None
    profile_bio: Optional[str] = None
    profile_theme: Optional[str] = None  # premium name color / avatar border (JSON)
    show_telegram: bool = True

    # Recent activity
    last_seen_at: Optional[datetime] = None
    created_at: datetime
    
    # Badges
    badges: List["UserBadgeResponse"] = []
    
    # XP & Leveling
    xp: int = 0
    level: int = 1
    login_streak: int = 0
    
    # Premium
    is_premium: bool = False
    
    # Follow status (for current user)
    is_following: bool = False
    follower_count: int = 0
    following_count: int = 0

    # Moderation state (for staff viewing the profile)
    is_banned: bool = False
    is_muted: bool = False

    @model_validator(mode='after')
    def _staff_premium(self):
        return _apply_staff_premium(self)

    model_config = ConfigDict(from_attributes=True)


class UserMinimal(BaseModel):
    """Minimal user info for embeds"""
    id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    avatar_url: Optional[str] = None
    role: UserRole
    custom_title: Optional[str] = None
    rep_positive: int = 0
    rep_negative: int = 0
    post_count: int = 0
    thread_count: int = 0
    like_count: int = 0
    referral_earnings: float = 0.0
    created_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
    signature: Optional[str] = None
    primary_badge: Optional["BadgeResponse"] = None
    profile_theme: Optional[str] = None
    show_telegram: bool = True
    xp: int = 0
    level: int = 1
    is_premium: bool = False
    premium_until: Optional[datetime] = None
    is_banned: bool = False
    is_muted: bool = False

    @model_validator(mode='after')
    def _staff_premium(self):
        return _apply_staff_premium(self)

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# FORUM TAB SCHEMAS
# ============================================================================


class ForumTabCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    slug: str = Field(..., min_length=1, max_length=50)
    icon: Optional[str] = None
    sort_order: int = 0
    is_visible: bool = True
    min_role: UserRole = UserRole.TRIAL
    required_badge_id: Optional[int] = None
    is_default: bool = False


class ForumTabUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=50)
    slug: Optional[str] = Field(None, min_length=1, max_length=50)
    icon: Optional[str] = None
    sort_order: Optional[int] = None
    is_visible: Optional[bool] = None
    min_role: Optional[UserRole] = None
    required_badge_id: Optional[int] = None
    is_default: Optional[bool] = None


class _NullTolerantModel(BaseModel):
    """Base for forum-structure responses read from legacy rows.

    Columns added to these tables over time are frequently NULL in older rows
    (min_role, is_locked, can_trial_post, thread_count, ...). Pydantic does NOT
    apply a field default to an *explicit* None, so serializing such a row raises
    ResponseValidationError -> HTTP 500. This coerces any None on a field that
    HAS a default back to that default. Required fields and genuinely-Optional
    fields (default None) are left untouched.
    """
    @field_validator("*", mode="before")
    @classmethod
    def _null_to_default(cls, v, info):
        if v is None:
            f = cls.model_fields.get(info.field_name)
            if f is not None and not f.is_required():
                return f.default_factory() if f.default_factory is not None else f.default
        return v


class ForumTabResponse(_NullTolerantModel):
    id: int
    name: str
    slug: str
    icon: Optional[str] = None
    sort_order: int = 0
    is_visible: bool = True
    min_role: UserRole = UserRole.TRIAL
    required_badge_id: Optional[int] = None
    is_default: bool = False
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# FORUM SECTION SCHEMAS
# ============================================================================

class ForumSectionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    slug: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    icon: Optional[str] = None
    sort_order: int = 0
    is_visible: bool = True
    min_role: UserRole = UserRole.TRIAL
    tab_id: Optional[int] = None


class ForumSectionUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    slug: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    icon: Optional[str] = None
    sort_order: Optional[int] = None
    is_visible: Optional[bool] = None
    min_role: Optional[UserRole] = None
    tab_id: Optional[int] = None


class ForumSectionResponse(_NullTolerantModel):
    id: int
    tab_id: Optional[int] = None
    name: str
    slug: str
    description: Optional[str] = None
    icon: Optional[str] = None
    sort_order: int = 0
    is_visible: bool = True
    min_role: UserRole = UserRole.TRIAL
    created_at: Optional[datetime] = None

    boards: List["ForumBoardResponse"] = []

    model_config = ConfigDict(from_attributes=True)


class ForumTabWithSectionsResponse(ForumTabResponse):
    """Tab with nested sections"""
    sections: List[ForumSectionResponse] = []


# ============================================================================
# FORUM BOARD SCHEMAS
# ============================================================================

def _validate_link_target(board_type: Optional[str], link_target: Optional[str]) -> Optional[str]:
    """A 'link' board must point somewhere; the target is either an in-app path
    (starting with '/') or an absolute http(s) URL. Returns the cleaned target."""
    if board_type != "link":
        return link_target
    target = (link_target or "").strip()
    if not target:
        raise ValueError("A link board requires a link target")
    if not (target.startswith("/") or target.startswith("http://") or target.startswith("https://")):
        raise ValueError("Link target must be an in-app path (e.g. /leaderboard) or an http(s) URL")
    return target


class ForumBoardCreate(BaseModel):
    section_id: int
    parent_id: Optional[int] = None
    name: str = Field(..., min_length=1, max_length=100)
    slug: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    icon: Optional[str] = None
    board_type: str = "forum"
    link_target: Optional[str] = Field(None, max_length=500)
    sort_order: int = 0
    is_visible: bool = True
    is_locked: bool = False
    min_role: UserRole = UserRole.TRIAL
    min_role_to_post: UserRole = UserRole.USER
    min_role_to_create_thread: UserRole = UserRole.USER

    @model_validator(mode="after")
    def _check_link(self):
        self.link_target = _validate_link_target(self.board_type, self.link_target)
        return self


class ForumBoardUpdate(BaseModel):
    section_id: Optional[int] = None
    parent_id: Optional[int] = None
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    slug: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    icon: Optional[str] = None
    board_type: Optional[str] = None
    link_target: Optional[str] = Field(None, max_length=500)
    sort_order: Optional[int] = None
    is_visible: Optional[bool] = None
    is_locked: Optional[bool] = None
    min_role: Optional[UserRole] = None
    min_role_to_post: Optional[UserRole] = None
    min_role_to_create_thread: Optional[UserRole] = None

    @model_validator(mode="after")
    def _check_link(self):
        # Only validate when this update actually sets the board to a link type;
        # partial updates that don't touch board_type are left alone.
        if self.board_type == "link":
            self.link_target = _validate_link_target(self.board_type, self.link_target)
        return self


class ForumBoardResponse(_NullTolerantModel):
    id: int
    section_id: int
    parent_id: Optional[int] = None
    name: str
    slug: str
    description: Optional[str] = None
    icon: Optional[str] = None
    board_type: str = "forum"
    link_target: Optional[str] = None
    sort_order: int = 0
    is_visible: bool = True
    is_locked: bool = False
    min_role: UserRole = UserRole.TRIAL
    can_trial_post: bool = False
    min_role_to_post: UserRole = UserRole.USER
    min_role_to_create_thread: UserRole = UserRole.USER

    # Statistics
    thread_count: int = 0
    post_count: int = 0
    last_post_at: Optional[datetime] = None

    # Last thread info (populated separately)
    last_thread: Optional["ThreadMinimal"] = None

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# THREAD SCHEMAS
# ============================================================================

class ThreadCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    content: str = Field(..., min_length=1, max_length=50000)
    tags: Optional[List[str]] = None
    poll: Optional["PollCreate"] = None


class ThreadUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=300)
    content: Optional[str] = Field(None, min_length=1, max_length=50000)


class ThreadModUpdate(BaseModel):
    """Moderator-only updates"""
    status: Optional[ThreadStatus] = None
    is_pinned: Optional[bool] = None
    is_announcement: Optional[bool] = None
    is_featured: Optional[bool] = None


class ThreadMinimal(BaseModel):
    """Minimal thread info for lists"""
    id: int
    title: str
    slug: Optional[str] = None
    status: ThreadStatus = ThreadStatus.OPEN
    is_pinned: bool = False
    is_announcement: bool = False
    tags: Optional[List[str]] = None
    title_color: Optional[str] = None
    title_glow: bool = False

    reply_count: int = 0
    view_count: int = 0
    like_count: int = 0
    
    created_at: datetime
    last_post_at: Optional[datetime] = None
    
    author: UserMinimal
    last_post_by: Optional[UserMinimal] = None
    
    # For current user
    has_unread: bool = False

    @field_validator('tags', mode='before')
    @classmethod
    def parse_tags(cls, v):
        if isinstance(v, str):
            return [t.strip() for t in v.split(',') if t.strip()]
        return v
    
    model_config = ConfigDict(from_attributes=True)


class ThreadResponse(BaseModel):
    id: int
    board_id: int
    title: str
    slug: Optional[str] = None
    content: str
    status: ThreadStatus = ThreadStatus.OPEN
    
    is_pinned: bool = False
    is_announcement: bool = False
    is_featured: bool = False
    tags: Optional[List[str]] = None
    title_color: Optional[str] = None
    title_glow: bool = False

    # Statistics
    view_count: int = 0
    reply_count: int = 0
    like_count: int = 0

    # Edit info
    is_edited: bool = False
    edited_at: Optional[datetime] = None
    edit_count: int = 0

    # Timestamps
    created_at: datetime
    updated_at: datetime
    last_post_at: Optional[datetime] = None
    # Bump state
    last_manual_bump_at: Optional[datetime] = None
    auto_bump_until: Optional[datetime] = None
    bump_available_at: Optional[datetime] = None  # when the CURRENT user may next bump (None = now)
    
    # Relations
    author: UserMinimal
    author_badges: List[dict] = []  # [{badge_id, badge_name, badge_color, badge_icon, badge_icon_style, is_primary}]
    board: "ForumBoardResponse"
    poll: Optional["PollResponse"] = None
    
    # Section breadcrumb info (populated from board.section)
    section_name: Optional[str] = None
    section_slug: Optional[str] = None
    
    # For current user
    is_liked: bool = False
    is_watched: bool = False

    @field_validator('tags', mode='before')
    @classmethod
    def parse_tags(cls, v):
        if isinstance(v, str):
            return [t.strip() for t in v.split(',') if t.strip()]
        return v
    
    model_config = ConfigDict(from_attributes=True)


class ThreadListResponse(BaseModel):
    threads: List[ThreadMinimal]
    total: int
    page: int
    per_page: int
    total_pages: int


# ============================================================================
# POST SCHEMAS
# ============================================================================

class PostCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=50000)
    parent_id: Optional[int] = None  # For replying to specific post


class PostUpdate(BaseModel):
    content: str = Field(..., min_length=1, max_length=50000)


class PostResponse(BaseModel):
    id: int
    thread_id: int
    thread_slug: Optional[str] = None
    content: str
    parent_id: Optional[int] = None
    
    # Edit info
    is_edited: bool = False
    edited_at: Optional[datetime] = None
    edit_count: int = 0
    
    # Statistics
    like_count: int = 0
    
    # Flags
    is_best_answer: bool = False
    is_deleted: bool = False
    delete_reason: Optional[str] = None
    
    # Timestamps
    created_at: datetime
    
    # Relations
    author: UserMinimal
    author_badges: List[dict] = []
    parent_author: Optional[UserMinimal] = None
    parent_preview: Optional[str] = None
    
    # For current user
    is_liked: bool = False
    
    model_config = ConfigDict(from_attributes=True)


class PostListResponse(BaseModel):
    posts: List[PostResponse]
    total: int
    page: int
    per_page: int
    total_pages: int


# ============================================================================
# REPUTATION SCHEMAS
# ============================================================================

class ReputationCreate(BaseModel):
    is_positive: bool
    comment: Optional[str] = Field(None, max_length=200)
    post_id: Optional[int] = None
    thread_id: Optional[int] = None
    # Reference to a closed escrow deal between giver and target; exempts the
    # giver from the min-posts requirement (traders aren't necessarily posters).
    deal_id: Optional[int] = None


class ReputationResponse(BaseModel):
    id: int
    is_positive: bool
    comment: Optional[str] = None
    created_at: datetime
    
    from_user: UserMinimal
    
    model_config = ConfigDict(from_attributes=True)


class ReputationListResponse(BaseModel):
    entries: List[ReputationResponse]
    total_positive: int
    total_negative: int


# ============================================================================
# BADGE SCHEMAS
# ============================================================================

class BadgeCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    description: Optional[str] = Field(None, max_length=500)
    icon_url: Optional[str] = None
    icon: Optional[str] = None
    icon_style: str = "default"
    color: str = "#6366f1"
    is_purchasable: bool = False
    price: float = Field(0.0, ge=0)
    multi_purchase: bool = False
    is_limited: bool = False
    max_supply: Optional[int] = None
    sort_order: int = 0
    auto_award_criteria: Optional[str] = None
    reward_xp: int = Field(0, ge=0)
    reward_balance: float = Field(0.0, ge=0)
    reward_role: Optional[str] = None


class BadgeUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=50)
    description: Optional[str] = Field(None, max_length=500)
    icon_url: Optional[str] = None
    icon: Optional[str] = None
    icon_style: Optional[str] = None
    color: Optional[str] = None
    is_purchasable: Optional[bool] = None
    price: Optional[float] = Field(None, ge=0)
    multi_purchase: Optional[bool] = None
    is_limited: Optional[bool] = None
    max_supply: Optional[int] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None
    auto_award_criteria: Optional[str] = None
    reward_xp: Optional[int] = Field(None, ge=0)
    reward_balance: Optional[float] = Field(None, ge=0)
    reward_role: Optional[str] = None


class BadgeResponse(_NullTolerantModel):
    id: int
    name: str
    description: Optional[str] = None
    icon_url: Optional[str] = None
    icon: Optional[str] = None
    icon_style: str = "default"
    color: str = "#6366f1"
    is_purchasable: bool = False
    price: float = 0.0
    multi_purchase: bool = False
    is_limited: bool = False
    max_supply: Optional[int] = None
    current_supply: int = 0
    sort_order: int = 0
    is_active: bool = True
    auto_award_criteria: Optional[str] = None
    reward_xp: int = 0
    reward_balance: float = 0.0
    reward_role: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class UserBadgeResponse(BaseModel):
    id: int
    badge: BadgeResponse
    is_primary: bool = False
    acquired_at: datetime
    acquired_type: str = "purchase"
    quantity: int = 1
    
    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# POLL SCHEMAS
# ============================================================================

class PollOptionCreate(BaseModel):
    text: str = Field(..., min_length=1, max_length=200)


class PollCreate(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)
    options: List[PollOptionCreate] = Field(..., min_length=2, max_length=10)
    is_multiple_choice: bool = False
    max_choices: int = 1
    is_anonymous: bool = False
    show_results_before_vote: bool = False
    allow_vote_change: bool = True
    ends_at: Optional[datetime] = None


class PollOptionResponse(BaseModel):
    id: int
    text: str
    vote_count: int = 0
    percentage: float = 0.0  # Calculated field
    
    model_config = ConfigDict(from_attributes=True)


class PollResponse(BaseModel):
    id: int
    question: str
    is_multiple_choice: bool = False
    max_choices: int = 1
    is_anonymous: bool = False
    show_results_before_vote: bool = False
    allow_vote_change: bool = True
    ends_at: Optional[datetime] = None
    is_closed: bool = False
    total_votes: int = 0
    created_at: datetime
    
    options: List[PollOptionResponse] = []
    
    # For current user
    has_voted: bool = False
    voted_options: List[int] = []  # Option IDs user voted for
    
    model_config = ConfigDict(from_attributes=True)


class PollVoteCreate(BaseModel):
    option_ids: List[int] = Field(..., min_length=1)


# ============================================================================
# REPORT SCHEMAS
# ============================================================================

class ReportCreate(BaseModel):
    report_type: ReportType
    thread_id: Optional[int] = None
    post_id: Optional[int] = None
    reported_user_id: Optional[int] = None
    reason: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=2000)


class ReportResponse(BaseModel):
    id: int
    reporter_id: int
    report_type: ReportType
    thread_id: Optional[int] = None
    post_id: Optional[int] = None
    reported_user_id: Optional[int] = None
    reason: str
    description: Optional[str] = None
    status: ReportStatus
    resolved_by: Optional[int] = None
    mod_notes: Optional[str] = None
    created_at: datetime
    resolved_at: Optional[datetime] = None
    
    reporter: Optional[UserMinimal] = None
    reported_user: Optional[UserMinimal] = None
    resolved_by_user: Optional[UserMinimal] = None
    thread: Optional[dict] = None
    post: Optional[dict] = None
    
    model_config = ConfigDict(from_attributes=True)


class ReportListResponse(BaseModel):
    items: List[ReportResponse]
    total: int
    page: int
    per_page: int
    pages: int



# ============================================================================
# NOTIFICATION SCHEMAS
# ============================================================================

class NotificationResponse(BaseModel):
    id: int
    type: str
    title: str
    body: Optional[str] = None
    link: Optional[str] = None
    is_read: bool = False
    created_at: datetime
    
    related_user: Optional[UserMinimal] = None
    
    model_config = ConfigDict(from_attributes=True)



class WithdrawalRequestResponse(BaseModel):
    """Admin withdrawal response with more details. Manually constructed — field names intentionally differ from model."""
    id: int
    user_id: int
    username: Optional[str] = None
    amount: float
    crypto_address: str
    crypto_network: Optional[str] = None
    status: str
    admin_notes: Optional[str] = None
    created_at: datetime
    processed_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=False)


# ============================================================================
# ADMIN SCHEMAS
# ============================================================================

class ModActionResponse(BaseModel):
    id: int
    action_type: str
    reason: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    expires_at: Optional[datetime] = None

    moderator_id: Optional[int] = None
    moderator: UserMinimal
    target_user_id: Optional[int] = None
    target_user: Optional[UserMinimal] = None
    thread_id: Optional[int] = None
    post_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# GENERIC SCHEMAS
# ============================================================================

class LikeResponse(BaseModel):
    liked: bool
    like_count: int


class SuccessResponse(BaseModel):
    success: bool = True
    message: Optional[str] = None


# ============================================================================
# CRYPTO DEPOSIT SCHEMAS
# ============================================================================

class CreateCryptoDeposit(BaseModel):
    # Bounded to a sane range. The lower bound also stops negative/zero amounts
    # from reaching the credit path; the upper bound keeps price_amount within the
    # Numeric(14,2) money column and avoids absurd invoices.
    amount: float = Field(gt=0, le=1_000_000)
    pay_currency: str


class CoinInfo(BaseModel):
    """A deposit coin offered to users (resolved from the admin-curated set)."""
    currency: str
    symbol: str
    name: str
    network: str
    min_usd: Optional[float] = None


class CryptoDepositResponse(BaseModel):
    deposit_id: int
    payment_id: Optional[str] = None
    pay_address: Optional[str] = None
    pay_amount: Optional[float] = None
    pay_currency: Optional[str] = None
    payment_status: str
    price_amount_usd: float


class CryptoDepositStatus(BaseModel):
    deposit_id: int
    payment_status: str
    confirmations: int = 0
    pay_address: Optional[str] = None
    pay_amount: Optional[float] = None
    pay_currency: Optional[str] = None
    price_amount_usd: float = 0.0
    is_credited: bool = False
    tx_hash: Optional[str] = None


class CryptoDepositItem(BaseModel):
    deposit_id: int
    payment_status: str
    confirmations: int = 0
    pay_amount: Optional[float] = None
    pay_currency: Optional[str] = None
    price_amount_usd: float = 0.0
    is_credited: bool = False
    tx_hash: Optional[str] = None
    created_at: datetime


# ============================================================================
# BANNER SCHEMAS
# ============================================================================

class BannerResponse(BaseModel):
    id: int
    title: str
    subtitle: Optional[str] = None
    image_url: Optional[str] = None
    link: Optional[str] = None
    link_text: str
    gradient_from: str
    gradient_to: str
    position: str
    is_active: bool
    sort_order: int
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class BannerBase(BaseModel):
    title: str
    subtitle: Optional[str] = None
    image_url: Optional[str] = None
    link: Optional[str] = None
    link_text: str = "Learn More"
    gradient_from: str = "primary-500"
    gradient_to: str = "accent-purple"
    position: str = "home_row_1"
    is_active: bool = True
    sort_order: int = 0


class BannerCreate(BannerBase):
    pass


class BannerUpdate(BaseModel):
    title: Optional[str] = None
    subtitle: Optional[str] = None
    image_url: Optional[str] = None
    link: Optional[str] = None
    link_text: Optional[str] = None
    gradient_from: Optional[str] = None
    gradient_to: Optional[str] = None
    position: Optional[str] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None



# ============================================================================
# ESCROW SCHEMAS
# ============================================================================

class EscrowMessageCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)

class EscrowMessageResponse(BaseModel):
    id: int
    deal_id: int
    # None for system messages (they have no sender; the FK forbids a fake user 0).
    sender_id: Optional[int] = None
    sender_username: Optional[str] = None
    content: str
    is_system: bool = False
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class EscrowDealResponse(BaseModel):
    id: int
    buyer_id: int
    seller_id: int
    buyer_username: Optional[str] = None
    seller_username: Optional[str] = None
    title: str
    description: Optional[str] = None
    amount: float
    status: str
    dispute_reason: Optional[str] = None
    dispute_by_id: Optional[int] = None
    dispute_by_username: Optional[str] = None
    resolution_note: Optional[str] = None
    resolved_by_id: Optional[int] = None
    resolved_by_username: Optional[str] = None
    hold_days: Optional[int] = None
    hold_ends_at: Optional[datetime] = None
    fee_amount: float = 0.0
    created_at: datetime
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    messages: Optional[List[EscrowMessageResponse]] = None

    model_config = ConfigDict(from_attributes=True)


class EscrowResolveRequest(BaseModel):
    release_to: str = Field(..., pattern="^(seller|buyer)$")
    note: Optional[str] = Field(None, max_length=2000)


# ============================================================================
# XP / LEVELING / LEADERBOARD SCHEMAS
# ============================================================================

class XPResponse(BaseModel):
    xp: int = 0
    level: int = 1
    xp_to_next_level: int = 0
    xp_for_current_level: int = 0
    login_streak: int = 0
    streak_bonus_claimed: bool = False
    last_daily_claim_date: Optional[date] = None
    daily_xp_preview: int = 0
    daily_balance_preview: float = 0.0
    daily_badge_preview: Optional[int] = None
    daily_badge_name_preview: Optional[str] = None
    daily_can_claim: bool = False

class DailyRewardResponse(BaseModel):
    claimed: bool
    streak: int = 0
    xp_awarded: int = 0
    balance_awarded: float = 0.0
    badge_id: Optional[int] = None
    badge_name: Optional[str] = None

class DailyRewardConfigResponse(BaseModel):
    id: int
    day: int
    xp_amount: int
    balance_amount: float
    badge_id: Optional[int] = None
    badge_name: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class DailyRewardConfigCreate(BaseModel):
    day: int = Field(..., gt=0)
    xp_amount: int = Field(10, ge=0)
    balance_amount: float = Field(0.10, ge=0.0)
    badge_id: Optional[int] = None
    is_active: bool = True

class DailyRewardConfigUpdate(BaseModel):
    xp_amount: Optional[int] = Field(None, ge=0)
    balance_amount: Optional[float] = Field(None, ge=0.0)
    badge_id: Optional[int] = None
    is_active: Optional[bool] = None

class LeaderboardEntry(BaseModel):
    rank: int
    user_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    avatar_url: Optional[str] = None
    show_telegram: bool = True
    role: Optional[UserRole] = None
    profile_theme: Optional[str] = None  # premium name color / avatar border (JSON)
    value: int = 0
    post_count: int = 0
    thread_count: int = 0
    likes_received: int = 0
    likes_given: int = 0
    rep_received: int = 0

class LeaderboardResponse(BaseModel):
    entries: List[LeaderboardEntry]
    current_user_rank: Optional[int] = None
    current_user_value: Optional[int] = None
    period_ends_at: Optional[datetime] = None
    period_starts_at: Optional[datetime] = None


# ============================================================================
# LIVE CHAT SCHEMAS
# ============================================================================

class ChatMessageCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=1000)

class ChatMessageResponse(BaseModel):
    id: int
    user_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    avatar_url: Optional[str] = None
    role: Optional[str] = None
    show_telegram: bool = True
    profile_theme: Optional[str] = None  # premium name color / avatar border (JSON)
    content: str
    is_deleted: bool = False
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ChatMessageListResponse(BaseModel):
    messages: List[ChatMessageResponse]
    has_more: bool = False


# Update forward references - must be called at module level after all classes are defined
ThreadCreate.model_rebuild()
# ============================================================================
# SHARED FILES (bot file board)
# ============================================================================

class SharedFileResponse(BaseModel):
    id: int
    kind: str
    file_name: Optional[str] = None
    mime_type: Optional[str] = None
    file_size: Optional[int] = None
    caption: Optional[str] = None
    uploader: Optional[UserMinimal] = None
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    suggested_category_id: Optional[int] = None
    suggested_category_name: Optional[str] = None
    download_count: int = 0
    created_at: Optional[datetime] = None
    # Admin-only fields (populated only on the ACP queue endpoints).
    status: Optional[str] = None
    reject_reason: Optional[str] = None


class SharedFileRejectRequest(BaseModel):
    reason: Optional[str] = Field(None, max_length=300)


class SharedFileApproveRequest(BaseModel):
    category_id: Optional[int] = None


class SharedFileCategoryRequest(BaseModel):
    category_id: Optional[int] = None


class FileCategoryResponse(BaseModel):
    id: int
    name: str
    sort_order: int = 0
    is_active: bool = True
    file_count: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class FileCategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    sort_order: int = 0


class FileCategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=80)
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


UserResponse.model_rebuild()
UserPublicProfile.model_rebuild()
UserMinimal.model_rebuild()
SharedFileResponse.model_rebuild()
ForumSectionResponse.model_rebuild()
ForumBoardResponse.model_rebuild()
ThreadMinimal.model_rebuild()
ThreadResponse.model_rebuild()
PostResponse.model_rebuild()
PollResponse.model_rebuild()
EscrowDealResponse.model_rebuild()
EscrowMessageResponse.model_rebuild()
