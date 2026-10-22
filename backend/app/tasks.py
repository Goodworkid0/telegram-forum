"""Background tasks - auto-finish giveaways, auto-release escrow, achievement checks"""
import asyncio
import json
import logging
import random
from datetime import datetime, timedelta
from sqlalchemy import select, func, or_, and_
from sqlalchemy.orm import selectinload
from app.database import async_session
from app.ledger import record_balance_change, commit_and_broadcast, ACCOUNT_PENDING
from app.models import (
    User, Notification, UserRole,
    Giveaway, GiveawayEntry, CryptoDeposit,
    Badge, UserBadge,
    EscrowDeal, EscrowStatus, EscrowMessage,
    LeaderboardPeriod, LeaderboardScore,
    AppSettings,
    Thread, ThreadStatus,
    Broadcast, BroadcastStatus,
)
from app.telegram import create_notification
from app.routers.forum_helpers import bump_level

logger = logging.getLogger(__name__)

GIVEAWAY_CHECK_INTERVAL = 60
BROADCAST_CHECK_INTERVAL = 15     # how often the worker polls for a queued broadcast
BROADCAST_SEND_SLEEP = 0.05      # ~20 Telegram DMs/sec — stays under the ~30/s flood limit
BROADCAST_BATCH = 200            # users fetched per DB page while delivering
BROADCAST_STALE_MINUTES = 5      # a SENDING broadcast older than this is resumed (worker crash)
ACHIEVEMENT_CHECK_INTERVAL = 300
ESCROW_CHECK_INTERVAL = 60
LEADERBOARD_CHECK_INTERVAL = 120


async def auto_finish_giveaways():
    """Check for ended giveaways with auto_pick_winner=True and pick a random winner"""
    audit_logger = logging.getLogger("audit")
    while True:
        try:
            async with async_session() as db:
                now = datetime.utcnow()
                result = await db.execute(
                    select(Giveaway).where(
                        Giveaway.enabled == True,
                        Giveaway.auto_pick_winner == True,
                        Giveaway.ends_at != None,
                        Giveaway.ends_at <= now,
                        Giveaway.winner_user_id == None
                    ).with_for_update()
                )
                giveaways = result.scalars().all()
                
                for g in giveaways:
                    try:
                        entries_res = await db.execute(
                            select(GiveawayEntry)
                            .where(GiveawayEntry.giveaway_id == g.id)
                            .options(selectinload(GiveawayEntry.user))
                        )
                        entries = [e for e in entries_res.scalars().all() if e.user is not None]
                        
                        if not entries:
                            logger.info(f"Giveaway #{g.id} '{g.title}' ended with no entries, skipping auto-pick")
                            continue
                        
                        if g.deposit_required:
                            eligible = []
                            for e in entries:
                                has_deposit = await db.scalar(
                                    select(func.count(CryptoDeposit.id)).where(
                                        CryptoDeposit.user_id == e.user_id,
                                        CryptoDeposit.is_credited == True,
                                    )
                                )
                                if (has_deposit or 0) > 0:
                                    eligible.append(e)
                            entries = eligible
                            
                            if not entries:
                                logger.info(f"Giveaway #{g.id} '{g.title}' has no eligible entries (deposit required), skipping")
                                continue
                        
                        winner_entry = random.choice(entries)
                        g.winner_user_id = winner_entry.user_id
                        g.winner_picked_at = datetime.utcnow()
                        
                        await create_notification(
                            db, user_id=winner_entry.user_id, type="giveaway_won",
                            title=f"You won: {g.title}!",
                            body=f"Congratulations! You won the giveaway prize: {g.prize or 'Prize'}",
                            link="/giveaways",
                            telegram_id=winner_entry.user.telegram_id if winner_entry.user else None,
                        )
                        
                        await db.commit()
                        logger.info(f"Auto-picked winner for giveaway #{g.id} '{g.title}': user #{winner_entry.user_id}")
                        audit_logger.info(
                            f"GIVEAWAY_AUTO_PICK: Giveaway #{g.id} '{g.title}' - "
                            f"Winner: @{winner_entry.user.username} (ID:{winner_entry.user_id}), "
                            f"Prize: {g.prize}, Entries: {len(entries)}"
                        )
                        
                    except Exception as e:
                        logger.error(f"Failed to auto-pick winner for giveaway #{g.id}: {e}")
                        await db.rollback()
        
        except Exception as e:
            logger.error(f"Auto-finish giveaways task error: {e}")
        
        await asyncio.sleep(GIVEAWAY_CHECK_INTERVAL)


async def run_achievement_award_pass(db) -> int:
    """Run a single pass of auto-award badge checks. Returns count of awards made.

    Shared by the background loop and the admin "trigger" endpoint so both run
    identical logic. Ownership is pre-loaded in one query (no per-user N+1) and
    all awards are committed in a single transaction per pass.
    """
    result = await db.execute(
        select(Badge).where(
            Badge.is_active == True,
            Badge.auto_award_criteria != None,
            Badge.auto_award_criteria != "",
        )
    )
    badges = result.scalars().all()

    # Parse criteria once, skipping invalid/empty.
    parsed_badges = []
    for badge in badges:
        try:
            criteria = json.loads(badge.auto_award_criteria)
        except (json.JSONDecodeError, TypeError):
            continue
        if criteria:
            parsed_badges.append((badge, criteria))
    if not parsed_badges:
        return 0

    # Load active users once (the candidate set is identical for every badge).
    users = (await db.execute(select(User).where(User.is_active == True))).scalars().all()

    # Pre-load existing ownership for all candidate badges in a single query to
    # avoid an O(users) count query per user.
    badge_ids = [b.id for b, _ in parsed_badges]
    owned_rows = await db.execute(
        select(UserBadge.user_id, UserBadge.badge_id).where(UserBadge.badge_id.in_(badge_ids))
    )
    owned = {(uid, bid) for uid, bid in owned_rows.all()}

    awarded = 0
    pending_notifications = []
    for badge, criteria in parsed_badges:
        for user in users:
            if (user.id, badge.id) in owned:
                continue

            meets = True
            for field, threshold in criteria.items():
                current_val = getattr(user, field, 0) or 0
                if current_val < threshold:
                    meets = False
                    break
            if not meets:
                continue

            db.add(UserBadge(user_id=user.id, badge_id=badge.id, acquired_type="achievement"))
            owned.add((user.id, badge.id))

            if badge.is_limited:
                badge.current_supply = (badge.current_supply or 0) + 1

            reward_desc_parts = []
            if badge.reward_xp and badge.reward_xp > 0:
                user.xp = (user.xp or 0) + badge.reward_xp
                reward_desc_parts.append(f"+{badge.reward_xp} XP")
                bump_level(user)
            if badge.reward_balance and badge.reward_balance > 0:
                record_balance_change(
                    db, user, delta=badge.reward_balance, entry_type="badge_reward",
                    ref_type="badge", ref_id=badge.id,
                    description=f"Achievement reward: {badge.name}",
                )
                reward_desc_parts.append(f"+${badge.reward_balance:.2f}")

            reward_text = " | ".join(reward_desc_parts)
            pending_notifications.append((
                user.id,
                f"Badge earned: {badge.name}!",
                (badge.description or f"You earned the '{badge.name}' badge!") + (f"\n{reward_text}" if reward_text else ""),
                f"/profile/{user.id}",
            ))
            awarded += 1
            logger.info(f"Awarded badge '{badge.name}' to user #{user.id}")

    if awarded:
        # Commit all awards atomically, then emit notifications (which add their
        # own rows) and commit those.
        await commit_and_broadcast(db)
        for user_id, title, body, link in pending_notifications:
            await create_notification(db, user_id=user_id, type="badge", title=title, body=body, link=link)
        await db.commit()
    return awarded


async def auto_award_achievements():
    """Check badges with auto_award_criteria and award them to qualifying users"""
    while True:
        try:
            async with async_session() as db:
                await run_achievement_award_pass(db)
        except Exception as e:
            logger.error(f"Auto-award achievements task error: {e}")

        await asyncio.sleep(ACHIEVEMENT_CHECK_INTERVAL)


async def auto_release_escrow():
    """Auto-release escrow deals where hold period has expired"""
    while True:
        try:
            async with async_session() as db:
                now = datetime.utcnow()
                result = await db.execute(
                    select(EscrowDeal).where(
                        EscrowDeal.status == EscrowStatus.FUNDED,
                        EscrowDeal.hold_ends_at != None,
                        EscrowDeal.hold_ends_at <= now,
                    )
                )
                deals = result.scalars().all()

                for deal in deals:
                    try:
                        # Re-load the deal under a row lock and re-assert it is
                        # still FUNDED. A concurrent complete_deal / resolve may
                        # have already released or refunded it; without this the
                        # funds could be released twice.
                        locked_result = await db.execute(
                            select(EscrowDeal)
                            .where(EscrowDeal.id == deal.id)
                            .with_for_update()
                        )
                        locked_deal = locked_result.scalar_one_or_none()
                        if not locked_deal or locked_deal.status != EscrowStatus.FUNDED:
                            await db.rollback()
                            continue

                        net = locked_deal.amount - (locked_deal.fee_amount or 0)

                        buyer_res = await db.execute(
                            select(User).where(User.id == locked_deal.buyer_id).with_for_update()
                        )
                        buyer = buyer_res.scalar_one_or_none()
                        seller_res = await db.execute(
                            select(User).where(User.id == locked_deal.seller_id).with_for_update()
                        )
                        seller = seller_res.scalar_one_or_none()

                        if buyer:
                            record_balance_change(
                                db, buyer, delta=-net, account=ACCOUNT_PENDING, clamp_zero=True,
                                entry_type="escrow_release_hold", ref_type="escrow_deal",
                                ref_id=locked_deal.id, description="Escrow auto-released (hold expired)",
                            )
                        if seller:
                            record_balance_change(
                                db, seller, delta=net, entry_type="escrow_payout",
                                ref_type="escrow_deal", ref_id=locked_deal.id,
                                description="Escrow auto-payout (hold expired)",
                            )

                        locked_deal.status = EscrowStatus.COMPLETED
                        locked_deal.completed_at = now

                        msg = EscrowMessage(
                            deal_id=locked_deal.id,
                            sender_id=None,  # system message; no user 0 exists (FK to users.id)
                            content=f"Hold period expired. ${net:.2f} auto-released to seller.",
                            is_system=True,
                        )
                        db.add(msg)

                        await commit_and_broadcast(db)
                        logger.info(f"Auto-released escrow deal #{deal.id} after hold expiry")

                    except Exception as e:
                        logger.error(f"Failed to auto-release deal #{deal.id}: {e}")
                        await db.rollback()

        except Exception as e:
            logger.error(f"Auto-release escrow task error: {e}")

        await asyncio.sleep(ESCROW_CHECK_INTERVAL)


async def auto_rotate_leaderboard():
    """Create new 3-day periods and award XP to top 10 of previous period"""
    while True:
        try:
            async with async_session() as db:
                now = datetime.utcnow()

                # Find active period that has ended
                result = await db.execute(
                    select(LeaderboardPeriod).where(
                        LeaderboardPeriod.is_active == True,
                        LeaderboardPeriod.ends_at <= now,
                    )
                )
                ended_periods = result.scalars().all()

                for period in ended_periods:
                    if not period.rewards_distributed:
                        # Get top 10 scores
                        scores_result = await db.execute(
                            select(LeaderboardScore).where(
                                LeaderboardScore.period_id == period.id,
                            ).order_by(LeaderboardScore.score.desc()).limit(10)
                        )
                        top_scores = scores_result.scalars().all()

                        # XP rewards: configurable via AppSettings, fallback to default
                        xp_rewards = [1000, 750, 500, 400, 300, 250, 200, 150, 100, 50]
                        settings_res = await db.execute(select(AppSettings).limit(1))
                        settings = settings_res.scalar_one_or_none()
                        if settings and settings.leaderboard_rewards:
                            try:
                                parsed = json.loads(settings.leaderboard_rewards)
                                if isinstance(parsed, list) and all(isinstance(x, (int, float)) for x in parsed):
                                    xp_rewards = parsed
                            except (json.JSONDecodeError, TypeError):
                                pass
                        for i, entry in enumerate(top_scores):
                            if i < len(xp_rewards):
                                user = await db.get(User, entry.user_id)
                                if user:
                                    user.xp = (user.xp or 0) + xp_rewards[i]
                                    bump_level(user)
                                    await create_notification(
                                        db, user_id=user.id, type="leaderboard",
                                        title=f"Leaderboard #{i+1} place!",
                                        body=f"You ranked #{i+1} with {entry.score} points and earned +{xp_rewards[i]} XP!",
                                        link="/leaderboard",
                                    )

                        period.rewards_distributed = True
                        period.is_active = False
                        await db.commit()
                        logger.info(f"Leaderboard period #{period.id} ended, rewards distributed to top {len(top_scores)}")

                # Create next period if none active
                active_count = await db.scalar(
                    select(func.count()).select_from(LeaderboardPeriod).where(
                        LeaderboardPeriod.is_active == True,
                    )
                )
                if active_count == 0:
                    next_start = now
                    next_end = now + timedelta(days=3)
                    new_period = LeaderboardPeriod(starts_at=next_start, ends_at=next_end)
                    db.add(new_period)
                    await db.commit()
                    logger.info(f"New leaderboard period created: {next_start} to {next_end}")

        except Exception as e:
            logger.error(f"Leaderboard rotation task error: {e}")

        await asyncio.sleep(LEADERBOARD_CHECK_INTERVAL)

BAN_CHECK_INTERVAL = 60


async def auto_unexpire_bans():
    """Check for expired temporary bans and unban users"""
    while True:
        try:
            async with async_session() as db:
                now = datetime.utcnow()
                result = await db.execute(
                    select(User).where(
                        User.is_banned == True,
                        User.ban_expires_at != None,
                        User.ban_expires_at <= now,
                    )
                )
                expired_bans = result.scalars().all()

                for user in expired_bans:
                    try:
                        user.is_banned = False
                        user.ban_reason = None
                        user.ban_expires_at = None
                        user.banned_at = None
                        await create_notification(
                            db,
                            user_id=user.id,
                            type="unbanned",
                            title="Your ban has expired",
                            body="Your temporary ban has expired. You now have full access again.",
                            link="/",
                            telegram_id=user.telegram_id,
                        )
                        await db.commit()
                        logger.info(f"Auto-unbanned user #{user.id} (@{user.username}) after ban expiry")
                    except Exception as e:
                        logger.error(f"Failed to unban user #{user.id}: {e}")
                        await db.rollback()
        except Exception as e:
            logger.error(f"Auto-unexpire bans task error: {e}")

        await asyncio.sleep(BAN_CHECK_INTERVAL)


async def auto_unexpire_mutes():
    """Check for expired temporary mutes and unmute users"""
    while True:
        try:
            async with async_session() as db:
                now = datetime.utcnow()
                result = await db.execute(
                    select(User).where(
                        User.is_muted == True,
                        User.mute_expires_at != None,
                        User.mute_expires_at <= now,
                    )
                )
                expired_mutes = result.scalars().all()

                for user in expired_mutes:
                    try:
                        user.is_muted = False
                        user.mute_reason = None
                        user.mute_expires_at = None
                        user.muted_at = None
                        user.muted_by_id = None
                        await create_notification(
                            db,
                            user_id=user.id,
                            type="unmuted",
                            title="Your mute has expired",
                            body="Your temporary mute has expired. You can post and chat again.",
                            link="/",
                            telegram_id=user.telegram_id,
                        )
                        await db.commit()
                        logger.info(f"Auto-unmuted user #{user.id} (@{user.username}) after mute expiry")
                    except Exception as e:
                        logger.error(f"Failed to unmute user #{user.id}: {e}")
                        await db.rollback()
        except Exception as e:
            logger.error(f"Auto-unexpire mutes task error: {e}")

        await asyncio.sleep(BAN_CHECK_INTERVAL)


AUTO_BUMP_CHECK_INTERVAL = 600  # check every 10 min; each thread is bumped every 48h
_AUTO_BUMP_INTERVAL = timedelta(hours=48)


async def auto_bump_threads():
    """Auto-bump paid threads to the top of their board every 48h while active."""
    while True:
        try:
            async with async_session() as db:
                now = datetime.utcnow()
                due_before = now - _AUTO_BUMP_INTERVAL
                result = await db.execute(
                    select(Thread).where(
                        Thread.auto_bump_until != None,
                        Thread.auto_bump_until > now,
                        Thread.status != ThreadStatus.DELETED,
                        (Thread.last_auto_bump_at == None) | (Thread.last_auto_bump_at <= due_before),
                    )
                )
                threads = result.scalars().all()
                for thread in threads:
                    try:
                        thread.bumped_at = now
                        thread.last_post_at = now
                        if not thread.last_post_by_id:
                            thread.last_post_by_id = thread.author_id
                        thread.last_auto_bump_at = now
                        await db.commit()
                        logger.info(f"Auto-bumped thread #{thread.id} (active until {thread.auto_bump_until})")
                    except Exception as e:
                        logger.error(f"Failed to auto-bump thread #{thread.id}: {e}")
                        await db.rollback()
        except Exception as e:
            logger.error(f"Auto-bump threads task error: {e}")

        await asyncio.sleep(AUTO_BUMP_CHECK_INTERVAL)


async def _deliver_broadcast(db, b: Broadcast) -> None:
    """Deliver one broadcast to its audience, paginating by user id and pacing
    Telegram DMs so the bot stays within flood limits. No opt-out — every
    targeted (active, non-banned) user receives it."""
    from app.telegram import send_telegram, _format_tg

    conds = [User.is_active == True, User.is_banned == False]
    if b.target_role:
        try:
            conds.append(User.role == UserRole[b.target_role])
        except KeyError:
            pass  # unknown role -> treat as "all"

    msg = _format_tg("announcement", b.title, b.body) if b.send_bot else None
    last_id = b.last_delivered_user_id or 0   # resume from where a prior run left off
    sent = b.sent_count or 0
    failed = b.failed_count or 0
    while True:
        rows = (await db.execute(
            select(User).where(*conds, User.id > last_id).order_by(User.id).limit(BROADCAST_BATCH)
        )).scalars().all()
        if not rows:
            break
        for u in rows:
            last_id = u.id
            try:
                if b.send_inbox:
                    db.add(Notification(
                        user_id=u.id, type="announcement",
                        title=b.title, body=b.body, link=b.link,
                        created_at=datetime.utcnow(),
                    ))
                if b.send_bot and u.telegram_id:
                    ok = await send_telegram(u.telegram_id, msg)
                    if not ok:
                        failed += 1
                    await asyncio.sleep(BROADCAST_SEND_SLEEP)
                sent += 1
            except Exception as e:
                failed += 1
                logger.warning("Broadcast #%s delivery to user %s failed: %s", b.id, u.id, e)
        b.sent_count = sent
        b.failed_count = failed
        b.last_delivered_user_id = last_id  # advance the resume cursor with this batch
        await db.commit()  # persist inbox rows + progress + cursor per batch

    b.status = BroadcastStatus.DONE
    b.finished_at = datetime.utcnow()
    await db.commit()
    logger.info("Broadcast #%s done: %s sent, %s failed", b.id, sent, failed)


async def process_broadcasts():
    """Pick up queued admin broadcasts and deliver them one at a time."""
    while True:
        try:
            async with async_session() as db:
                # Pick a queued broadcast, OR resume one stuck in SENDING (worker
                # died / leadership flapped mid-delivery). The resume cursor
                # (last_delivered_user_id) prevents re-delivering to reached users.
                stale_before = datetime.utcnow() - timedelta(minutes=BROADCAST_STALE_MINUTES)
                b = await db.scalar(
                    select(Broadcast).where(
                        or_(
                            Broadcast.status == BroadcastStatus.PENDING,
                            and_(
                                Broadcast.status == BroadcastStatus.SENDING,
                                Broadcast.started_at < stale_before,
                            ),
                        )
                    ).order_by(Broadcast.created_at).limit(1)
                )
                if b:
                    b.status = BroadcastStatus.SENDING
                    b.started_at = datetime.utcnow()
                    await db.commit()
                    try:
                        await _deliver_broadcast(db, b)
                    except Exception as e:
                        logger.error("Broadcast #%s failed: %s", b.id, e)
                        await db.rollback()
                        b.status = BroadcastStatus.FAILED
                        b.finished_at = datetime.utcnow()
                        await db.commit()
        except Exception as e:
            logger.error("process_broadcasts task error: %s", e)
        await asyncio.sleep(BROADCAST_CHECK_INTERVAL)
