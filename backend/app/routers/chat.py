"""Live Chat (Shoutbox) API Router"""
import re
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload
from typing import List
from datetime import datetime

from app.database import get_db
from app.dependencies import limiter
from app.auth import get_current_active_user, get_current_unmuted_user
from app.models import User, ChatMessage, UserRole, ModAction
from app.sanitize import sanitize_content
from app.routers.forum_helpers import public_name
from app.telegram import create_notification
from app.schemas import ChatMessageCreate, ChatMessageResponse, ChatMessageListResponse, SuccessResponse

router = APIRouter(prefix="/api/chat", tags=["Chat"])

MAX_MESSAGE_LENGTH = 1000
MESSAGE_HISTORY_LIMIT = 50
RATE_LIMIT_SECONDS = 2  # Anti-spam: min seconds between messages


def message_to_response(msg: ChatMessage) -> ChatMessageResponse:
    return ChatMessageResponse(
        id=msg.id,
        user_id=msg.user_id,
        username=msg.user.username if msg.user else None,
        first_name=msg.user.first_name if msg.user else None,
        avatar_url=msg.user.avatar_url if msg.user else None,
        role=msg.user.role.value if msg.user and msg.user.role else None,
        show_telegram=msg.user.show_telegram if msg.user and msg.user.show_telegram is not None else True,
        profile_theme=msg.user.profile_theme if msg.user else None,
        content=msg.content if not msg.is_deleted else "[deleted]",
        is_deleted=msg.is_deleted,
        created_at=msg.created_at,
    )


@router.get("/messages", response_model=ChatMessageListResponse)
async def get_messages(
    before_id: int = Query(None, description="Cursor: get messages before this ID"),
    limit: int = Query(MESSAGE_HISTORY_LIMIT, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    query = (
        select(ChatMessage)
        .options(selectinload(ChatMessage.user))
        .order_by(desc(ChatMessage.id))
        .limit(limit + 1)
    )
    if before_id:
        query = query.where(ChatMessage.id < before_id)

    result = await db.execute(query)
    messages = result.scalars().all()

    has_more = len(messages) > limit
    messages = messages[:limit]

    # Reverse to chronological order
    messages.reverse()

    return ChatMessageListResponse(
        messages=[message_to_response(m) for m in messages],
        has_more=has_more,
    )


@router.post("/messages", response_model=ChatMessageResponse)
@limiter.limit("20/minute")
async def send_message(
    request: Request,
    data: ChatMessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_unmuted_user),
):
    content = sanitize_content(data.content.strip())
    if not content:
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    if len(content) > MAX_MESSAGE_LENGTH:
        raise HTTPException(status_code=400, detail=f"Message too long (max {MAX_MESSAGE_LENGTH} chars)")

    # Anti-spam: check last message time
    last_msg = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.user_id == current_user.id)
        .order_by(desc(ChatMessage.id))
        .limit(1)
    )
    last = last_msg.scalar_one_or_none()
    if last and (datetime.utcnow() - last.created_at).total_seconds() < RATE_LIMIT_SECONDS:
        raise HTTPException(status_code=429, detail="Slow down! Wait a moment between messages.")

    msg = ChatMessage(user_id=current_user.id, content=content)
    db.add(msg)
    await db.flush()  # assign msg.id without ending the transaction

    # Parse @mentions and notify mentioned users (excluding the sender).
    # Users who hide their Telegram handle are tagged by display name (the
    # autocomplete inserts @DisplayName for them), so match both fields.
    mentioned_usernames = {u for u in re.findall(r'@(\w+)', content) if u}
    if mentioned_usernames:
        mention_result = await db.execute(
            select(User).where(
                (User.username.in_(mentioned_usernames))
                | (User.first_name.in_(mentioned_usernames)),
                User.is_active == True,
                User.id != current_user.id,
            )
        )
        sender_name = public_name(current_user)
        for mentioned_user in mention_result.scalars().all():
            await create_notification(
                db,
                user_id=mentioned_user.id,
                type="mention",
                title="You were mentioned",
                body=f"{sender_name} mentioned you in live chat",
                link="/chat",
                related_user_id=current_user.id,
            )

    await db.commit()
    await db.refresh(msg)

    # Reload with user
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.id == msg.id)
        .options(selectinload(ChatMessage.user))
    )
    msg = result.scalar_one()

    return message_to_response(msg)


@router.delete("/messages/{message_id}", response_model=SuccessResponse)
async def delete_message(
    message_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(
        select(ChatMessage).where(ChatMessage.id == message_id)
    )
    msg = result.scalar_one_or_none()

    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")

    is_owner = msg.user_id == current_user.id
    is_mod = current_user.role in (UserRole.MODERATOR, UserRole.ADMIN)

    if not is_owner and not is_mod:
        raise HTTPException(status_code=403, detail="Not allowed")

    msg.is_deleted = True

    # Log staff deletions of other users' messages for the mod audit trail.
    if is_mod and not is_owner:
        db.add(ModAction(
            moderator_id=current_user.id,
            target_user_id=msg.user_id,
            action_type="delete_chat_message",
            reason=f"Deleted chat message #{msg.id}",
        ))

    await db.commit()

    return SuccessResponse(message="Message deleted")


@router.get("/unread-count")
async def get_unread_count(
    since_id: int = Query(0, description="Last seen message ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    count = await db.scalar(
        select(func.count(ChatMessage.id)).where(
            ChatMessage.id > since_id,
            ChatMessage.is_deleted == False,
            ChatMessage.user_id != current_user.id,
        )
    )
    latest_id = await db.scalar(select(func.max(ChatMessage.id)))
    return {"count": count or 0, "latest_id": latest_id or 0}
