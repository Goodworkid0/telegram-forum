"""Forum Poll CRUD, voting, results"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from datetime import datetime

from app.dependencies import limiter

from app.database import get_db
from app.auth import (
    get_current_user,
    get_current_verified_user,
)
from app.models import (
    User,
    Poll, PollOption, PollVote,
    Thread, ForumBoard, ThreadStatus,
)
from app.schemas import (
    PollResponse, PollVoteCreate,
)
from app.routers.forum_helpers import assert_board_readable

router = APIRouter(prefix="/api/forum", tags=["Forum"])


@router.post("/polls/{poll_id}/vote", response_model=PollResponse)
@limiter.limit("30/minute")
async def vote_poll(
    request: Request,
    poll_id: int,
    data: PollVoteCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_verified_user),
):
    """Vote on a poll"""
    # Lock the poll row so concurrent votes from the same user can't double-vote
    # and the denormalized vote counters can't be inflated by a lost update.
    result = await db.execute(
        select(Poll)
        .where(Poll.id == poll_id)
        .options(selectinload(Poll.options))
        .with_for_update()
    )
    poll = result.scalar_one_or_none()

    if not poll:
        raise HTTPException(status_code=404, detail="Poll not found")

    # Read-gate: a poll lives in a thread on a board — enforce the board's
    # access rules (and skip deleted threads) so a user excluded from a
    # restricted board can't vote in / read its polls by guessing poll_id.
    if poll.thread_id:
        thread = await db.scalar(
            select(Thread).where(Thread.id == poll.thread_id).options(selectinload(Thread.board))
        )
        if not thread or thread.status == ThreadStatus.DELETED:
            raise HTTPException(status_code=404, detail="Poll not found")
        await assert_board_readable(db, thread.board, current_user)

    if poll.is_closed:
        raise HTTPException(status_code=400, detail="Poll is closed")

    if poll.ends_at and poll.ends_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Poll has ended")

    # Check if user already voted
    existing_votes = await db.execute(
        select(PollVote).where(PollVote.poll_id == poll_id, PollVote.user_id == current_user.id)
    )
    existing = list(existing_votes.scalars())

    if existing and not poll.allow_vote_change:
        raise HTTPException(status_code=400, detail="Already voted and vote changes not allowed")

    # Dedupe option IDs up front: a repeated id (e.g. [5, 5]) must count as a
    # single vote, not let one user stack multiple votes on the same option
    # (and would otherwise trip the (poll,option,user) unique constraint -> 500).
    option_ids = list(dict.fromkeys(data.option_ids))

    # Validate option IDs
    valid_option_ids = {opt.id for opt in poll.options}
    for opt_id in option_ids:
        if opt_id not in valid_option_ids:
            raise HTTPException(status_code=400, detail=f"Invalid option ID: {opt_id}")

    # Check number of choices
    if not poll.is_multiple_choice and len(option_ids) > 1:
        raise HTTPException(status_code=400, detail="Only one choice allowed")

    if poll.is_multiple_choice and poll.max_choices and len(option_ids) > poll.max_choices:
        raise HTTPException(status_code=400, detail=f"Maximum {poll.max_choices} choices allowed")

    # Remove existing votes if changing
    options_map = {opt.id: opt for opt in poll.options}
    existing_count = len(existing)
    if existing:
        for vote in existing:
            opt = options_map.get(vote.option_id)
            if opt:
                opt.vote_count = max(0, (opt.vote_count or 0) - 1)
            await db.delete(vote)
        poll.total_votes = max(0, (poll.total_votes or 0) - existing_count)

    # Create new votes
    new_count = len(option_ids)
    for opt_id in option_ids:
        vote = PollVote(poll_id=poll_id, option_id=opt_id, user_id=current_user.id)
        db.add(vote)

        opt = options_map.get(opt_id)
        if opt:
            opt.vote_count = (opt.vote_count or 0) + 1

    poll.total_votes = (poll.total_votes or 0) + new_count

    await db.commit()
    await db.refresh(poll)

    # Build response
    total_votes = poll.total_votes or 0

    return PollResponse(
        id=poll.id,
        question=poll.question,
        is_multiple_choice=poll.is_multiple_choice,
        max_choices=poll.max_choices,
        is_anonymous=poll.is_anonymous,
        show_results_before_vote=poll.show_results_before_vote,
        allow_vote_change=poll.allow_vote_change,
        ends_at=poll.ends_at,
        is_closed=poll.is_closed,
        total_votes=total_votes,
        created_at=poll.created_at,
        options=[
            {
                "id": opt.id,
                "text": opt.text,
                "vote_count": opt.vote_count or 0,
                "percentage": (opt.vote_count or 0) / total_votes * 100 if total_votes > 0 else 0,
            }
            for opt in poll.options
        ],
        has_voted=True,
        voted_options=data.option_ids,
    )
