"""Direct Messages Router - User-to-user messaging"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_, func, desc
from sqlalchemy.orm import selectinload
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime, timedelta

from app.database import get_db
from app.models import DirectConversation, DirectMessage, User, UserRole, AppSettings
from app.auth import get_current_active_user
from app.sanitize import sanitize_content
from app.routers.forum_helpers import public_name

from app.dependencies import limiter

router = APIRouter(prefix="/api/dm", tags=["Direct Messages"])


class SendMessage(BaseModel):
    content: str = Field(min_length=1, max_length=2000)


class EditMessage(BaseModel):
    content: str = Field(min_length=1, max_length=2000)


# Allowed conversation-context kinds. context_type is attacker-controlled display
# metadata, so it must be constrained to known values rather than stored verbatim.
ALLOWED_CONTEXT_TYPES = {"seller_profile", "wtb_post"}


class StartConversation(BaseModel):
    user_id: int
    message: str = Field(min_length=1, max_length=2000)
    context_type: Optional[str] = None   # 'seller_profile', 'wtb_post'
    context_id: Optional[int] = None
    context_label: Optional[str] = None

    @field_validator("context_type")
    @classmethod
    def _validate_context_type(cls, v):
        if v is None:
            return v
        if v not in ALLOWED_CONTEXT_TYPES:
            raise ValueError(f"invalid context_type: {v}")
        return v


def _normalize_pair(a: int, b: int):
    """user1_id is always the smaller id"""
    return (min(a, b), max(a, b))


def _serialize_conversation(conv: DirectConversation, current_user_id: int) -> dict:
    other = conv.user2 if conv.user1_id == current_user_id else conv.user1
    msgs = conv.messages or []
    unread = sum(1 for m in msgs if not m.is_read and m.sender_id != current_user_id)
    last_msg = msgs[-1] if msgs else None

    is_online = False
    if other and other.last_seen_at:
        is_online = (datetime.utcnow() - other.last_seen_at).total_seconds() < 300

    return {
        "id": conv.id,
        "other_user": {
            "id": other.id,
            "username": other.username,
            "first_name": other.first_name,
            "show_telegram": other.show_telegram if other.show_telegram is not None else True,
            "avatar_url": other.avatar_url,
            "role": other.role.value if other.role else "buyer",
            "profile_theme": other.profile_theme,
            "seller_rank": getattr(other, "seller_rank", 0) or 0,
            "is_online": is_online,
        } if other else None,
        "context_type": conv.context_type,
        "context_id": conv.context_id,
        "context_label": conv.context_label,
        "last_message": last_msg.content[:80] if last_msg else None,
        "last_message_at": conv.last_message_at.isoformat() if conv.last_message_at else None,
        "unread_count": unread,
        "created_at": conv.created_at.isoformat() if conv.created_at else None,
    }


def _serialize_message(msg: DirectMessage) -> dict:
    return {
        "id": msg.id,
        "sender_id": msg.sender_id,
        "sender_username": public_name(msg.sender) if msg.sender else None,
        "sender_avatar": msg.sender.avatar_url if msg.sender else None,
        "content": msg.content,
        "is_read": msg.is_read,
        "is_edited": getattr(msg, "is_edited", False) or False,
        "is_deleted": getattr(msg, "is_deleted", False) or False,
        "created_at": msg.created_at.isoformat() if msg.created_at else None,
    }


# ── List conversations ─────────────────────────────────────────────────────

@router.get("")
async def list_conversations(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DirectConversation)
        .where(
            or_(
                DirectConversation.user1_id == current_user.id,
                DirectConversation.user2_id == current_user.id,
            )
        )
        .options(
            selectinload(DirectConversation.user1),
            selectinload(DirectConversation.user2),
            selectinload(DirectConversation.messages).selectinload(DirectMessage.sender),
        )
        .order_by(desc(DirectConversation.last_message_at))
    )
    convos = result.scalars().all()
    return [_serialize_conversation(c, current_user.id) for c in convos]


# ── Unread count ────────────────────────────────────────────────────────────

@router.get("/unread-count")
async def unread_count(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    # Count all unread DMs where current user is NOT the sender
    count = await db.scalar(
        select(func.count()).select_from(DirectMessage).join(
            DirectConversation, DirectMessage.conversation_id == DirectConversation.id
        ).where(
            or_(
                DirectConversation.user1_id == current_user.id,
                DirectConversation.user2_id == current_user.id,
            ),
            DirectMessage.sender_id != current_user.id,
            DirectMessage.is_read == False,
        )
    ) or 0
    return {"count": count}


# ── Start or get conversation ───────────────────────────────────────────────

@router.post("/start")
@limiter.limit("30/hour")
async def start_conversation(
    request: Request,
    payload: StartConversation,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Start a new DM conversation (or return existing) and send first message"""
    if payload.user_id == current_user.id:
        raise HTTPException(400, "Cannot message yourself.")

    settings_result = await db.execute(select(AppSettings).where(AppSettings.id == 1))
    settings = settings_result.scalar_one_or_none()
    min_posts = settings.min_posts_for_dm if settings else 5
    if (current_user.post_count or 0) < min_posts:
        raise HTTPException(
            403,
            f"You need at least {min_posts} posts to send direct messages. "
            f"You currently have {current_user.post_count or 0}."
        )

    if current_user.is_banned:
        raise HTTPException(403, "Your account is restricted.")

    # Check target user exists
    target = await db.get(User, payload.user_id)
    if not target:
        raise HTTPException(404, "User not found.")
    if target.is_banned:
        raise HTTPException(400, "Cannot message this user.")

    u1, u2 = _normalize_pair(current_user.id, payload.user_id)

    # Find existing conversation (any context)
    result = await db.execute(
        select(DirectConversation).where(
            DirectConversation.user1_id == u1,
            DirectConversation.user2_id == u2,
        ).order_by(desc(DirectConversation.last_message_at)).limit(1)
    )
    conv = result.scalar_one_or_none()

    if not conv:
        conv = DirectConversation(
            user1_id=u1,
            user2_id=u2,
            context_type=payload.context_type,
            context_id=payload.context_id,
            context_label=(payload.context_label or "")[:200] or None,
        )
        db.add(conv)
        await db.flush()

    # Add first message
    msg = DirectMessage(
        conversation_id=conv.id,
        sender_id=current_user.id,
        content=sanitize_content(payload.message.strip()),
    )
    db.add(msg)
    conv.last_message_at = datetime.utcnow()

    # Auto-response: if target has auto_response configured, send it. Sanitize on
    # delivery too (defense in depth) — every other DM write goes through
    # sanitize_content, and this content is injected into every conversation the
    # target receives, so it must not be the one unsanitized path.
    if target.auto_response and target.auto_response.strip():
        auto_msg = DirectMessage(
            conversation_id=conv.id,
            sender_id=target.id,
            content=sanitize_content(target.auto_response.strip()),
        )
        db.add(auto_msg)
        conv.last_message_at = datetime.utcnow()

    # Notify the recipient about the new conversation (one notification per
    # conversation start, not per message — unread counts cover the rest).
    # Type dm_message respects the "DM messages" notification preference.
    from app.telegram import create_notification
    await create_notification(
        db, user_id=target.id, type="dm_message",
        title="New message",
        body=f"{public_name(current_user)} sent you a message",
        link=f"/messages/{conv.id}",
        telegram_id=target.telegram_id,
        related_user_id=current_user.id,
    )

    await db.commit()

    return {"conversation_id": conv.id}


# ── Get conversation messages ───────────────────────────────────────────────

@router.get("/{conversation_id}")
async def get_conversation(
    conversation_id: int,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DirectConversation)
        .where(DirectConversation.id == conversation_id)
        .options(
            selectinload(DirectConversation.user1),
            selectinload(DirectConversation.user2),
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(404, "Conversation not found.")
    if current_user.id not in (conv.user1_id, conv.user2_id):
        raise HTTPException(403, "Not your conversation.")

    # Count total messages
    total = await db.scalar(
        select(func.count()).select_from(DirectMessage)
        .where(DirectMessage.conversation_id == conversation_id)
    ) or 0
    total_pages = max(1, -(-total // per_page))  # ceil division

    # For chat: page 1 = latest messages. Offset from end.
    if total == 0 or page > total_pages:
        # Out-of-range page -> empty window (previously this wrongly returned page 1).
        offset = 0
        limit = 0
    else:
        offset = max(0, total - page * per_page)
        limit = per_page if page < total_pages else total - (total_pages - 1) * per_page

    msgs_result = await db.execute(
        select(DirectMessage)
        .where(DirectMessage.conversation_id == conversation_id)
        .options(selectinload(DirectMessage.sender))
        .order_by(DirectMessage.created_at)
        .offset(offset)
        .limit(limit)
    )
    messages = msgs_result.scalars().all()

    # Mark unread as read
    for m in messages:
        if m.sender_id != current_user.id and not m.is_read:
            m.is_read = True
    await db.commit()

    other = conv.user2 if conv.user1_id == current_user.id else conv.user1
    is_online = False
    if other and other.last_seen_at:
        is_online = (datetime.utcnow() - other.last_seen_at).total_seconds() < 300

    return {
        "id": conv.id,
        "other_user": {
            "id": other.id,
            "username": other.username,
            "first_name": other.first_name,
            "show_telegram": other.show_telegram if other.show_telegram is not None else True,
            "avatar_url": other.avatar_url,
            "role": other.role.value if other.role else "buyer",
            "profile_theme": other.profile_theme,
            "seller_rank": getattr(other, "seller_rank", 0) or 0,
            "is_online": is_online,
        } if other else None,
        "context_type": conv.context_type,
        "context_id": conv.context_id,
        "context_label": conv.context_label,
        "messages": [_serialize_message(m) for m in messages],
        "total_messages": total,
        "page": page,
        "total_pages": total_pages,
    }


# ── Send message ────────────────────────────────────────────────────────────

@router.post("/{conversation_id}/messages")
@limiter.limit("60/minute")
async def send_message(
    request: Request,
    conversation_id: int,
    payload: SendMessage,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    conv = await db.get(DirectConversation, conversation_id)
    if not conv:
        raise HTTPException(404, "Conversation not found.")
    if current_user.id not in (conv.user1_id, conv.user2_id):
        raise HTTPException(403, "Not your conversation.")

    # PM rate limit
    recent = await db.execute(
        select(DirectMessage).where(
            DirectMessage.sender_id == current_user.id,
            DirectMessage.created_at > datetime.utcnow() - timedelta(seconds=60),
        ).limit(1)
    )
    if recent.scalar_one_or_none():
        from app.models import AppSettings
        settings = await db.execute(select(AppSettings).where(AppSettings.id == 1))
        s = settings.scalar_one_or_none()
        max_pm = (s.max_pm_per_minute if s and s.max_pm_per_minute else 1)
        recent_count = await db.scalar(
            select(func.count()).select_from(DirectMessage).where(
                DirectMessage.sender_id == current_user.id,
                DirectMessage.created_at > datetime.utcnow() - timedelta(seconds=60),
            )
        )
        if (recent_count or 0) >= max_pm:
            raise HTTPException(429, f"Rate limited. Max {max_pm} PM per minute.")

    msg = DirectMessage(
        conversation_id=conv.id,
        sender_id=current_user.id,
        content=sanitize_content(payload.content.strip()),
    )
    db.add(msg)
    conv.last_message_at = datetime.utcnow()
    await db.commit()
    await db.refresh(msg, ["sender"])

    return _serialize_message(msg)


# ── Edit message ────────────────────────────────────────────────────────────

@router.put("/messages/{message_id}")
async def edit_message(
    message_id: int,
    payload: EditMessage,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    msg = await db.get(DirectMessage, message_id)
    if not msg:
        raise HTTPException(404, "Message not found.")
    if msg.sender_id != current_user.id:
        raise HTTPException(403, "Can only edit your own messages.")
    if getattr(msg, "is_deleted", False):
        raise HTTPException(400, "Cannot edit deleted message.")
    # 15 min edit window
    if (datetime.utcnow() - msg.created_at).total_seconds() > 900:
        raise HTTPException(400, "Edit window expired (15 minutes).")

    msg.content = sanitize_content(payload.content.strip())
    msg.is_edited = True
    await db.commit()
    await db.refresh(msg, ["sender"])
    return _serialize_message(msg)


# ── Delete message ──────────────────────────────────────────────────────────

@router.delete("/messages/{message_id}")
async def delete_message(
    message_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    msg = await db.get(DirectMessage, message_id)
    if not msg:
        raise HTTPException(404, "Message not found.")
    if msg.sender_id != current_user.id:
        raise HTTPException(403, "Can only delete your own messages.")

    msg.content = ""
    msg.is_deleted = True
    await db.commit()
    return {"success": True}


# ── Search conversations ───────────────────────────────────────────────────

@router.get("/search/messages")
async def search_conversations(
    q: str = Query(..., min_length=2, max_length=100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Search messages in user's conversations"""
    search_term = f"%{q}%"
    result = await db.execute(
        select(DirectMessage)
        .join(DirectConversation, DirectMessage.conversation_id == DirectConversation.id)
        .where(
            or_(
                DirectConversation.user1_id == current_user.id,
                DirectConversation.user2_id == current_user.id,
            ),
            DirectMessage.content.ilike(search_term),
            DirectMessage.is_deleted == False,
        )
        .options(selectinload(DirectMessage.sender))
        .order_by(desc(DirectMessage.created_at))
        .limit(20)
    )
    messages = result.scalars().all()
    return [
        {
            **_serialize_message(m),
            "conversation_id": m.conversation_id,
        }
        for m in messages
    ]
