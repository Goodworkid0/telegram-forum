"""add_missing_uniques_and_indexes

Backfills the dedup unique constraints that were only ever declared in the ORM
models (never in a migration), plus hot-path indexes. On a DB built fresh by
create_all the unique constraints already exist as backing indexes, so every
statement is guarded with IF NOT EXISTS and is a no-op there. On a DB that was
alembic-stamped before these constraints were added to the model, they are
absent — the app-level check-then-insert guards are then TOCTOU-racy
(double-like / double-vote / duplicate badge award / duplicate giveaway entry).
This migration makes the database the source of truth again.

Each unique index is preceded by a dedup that keeps the lowest id per key, so
the CREATE UNIQUE INDEX can't fail on a DB that already accumulated duplicates.

Revision ID: c3d5e7f9a1b3
Revises: b2c4d6e8f0a1
Create Date: 2026-06-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'c3d5e7f9a1b3'
down_revision: Union[str, None] = 'b2c4d6e8f0a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (index name, table, columns) — name matches the ORM UniqueConstraint so that
# IF NOT EXISTS detects the constraint's backing index on create_all-built DBs.
_UNIQUES = [
    ("uq_user_follow", "user_follows", ["follower_id", "following_id"]),
    ("uq_post_like", "post_likes", ["post_id", "user_id"]),
    ("uq_thread_like", "thread_likes", ["thread_id", "user_id"]),
    ("uq_thread_view", "thread_views", ["thread_id", "user_id"]),
    ("uq_thread_watch", "thread_watches", ["thread_id", "user_id"]),
    ("uq_user_badge", "user_badges", ["user_id", "badge_id"]),
    ("uq_vouch", "vouches", ["voucher_id", "vouchee_id"]),
    ("uq_poll_vote", "poll_votes", ["poll_id", "option_id", "user_id"]),
    ("uq_direct_conversation", "direct_conversations", ["user1_id", "user2_id"]),
    ("uq_giveaway_entry", "giveaway_entries", ["giveaway_id", "user_id"]),
    ("uq_user_period_score", "leaderboard_scores", ["user_id", "period_id"]),
]

# (index name, table, columns)
_INDEXES = [
    ("ix_posts_is_deleted", "posts", ["is_deleted"]),
    ("ix_direct_messages_conversation_is_read", "direct_messages", ["conversation_id", "is_read"]),
    ("ix_withdrawal_requests_status", "withdrawal_requests", ["status"]),
    ("ix_crypto_deposits_is_credited", "crypto_deposits", ["is_credited"]),
    ("ix_escrow_deals_hold_ends_at", "escrow_deals", ["hold_ends_at"]),
]


def upgrade() -> None:
    for name, table, cols in _UNIQUES:
        cols_sql = ", ".join(cols)
        group_by = ", ".join(cols)
        # Drop duplicate rows (keep the lowest id per key) so the unique index
        # can be created on a DB that predates the constraint.
        op.execute(
            f"DELETE FROM {table} WHERE id NOT IN "
            f"(SELECT min_id FROM (SELECT MIN(id) AS min_id FROM {table} GROUP BY {group_by}) t)"
        )
        op.execute(f"CREATE UNIQUE INDEX IF NOT EXISTS {name} ON {table} ({cols_sql})")

    for name, table, cols in _INDEXES:
        cols_sql = ", ".join(cols)
        op.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({cols_sql})")


def downgrade() -> None:
    for name, _table, _cols in _INDEXES:
        op.execute(f"DROP INDEX IF EXISTS {name}")
    # Leave the unique indexes in place on downgrade: dropping them would
    # re-open the data-integrity races, and on create_all-built DBs the name
    # belongs to a model constraint we must not remove.
