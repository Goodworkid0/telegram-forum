"""add board_type and link_target to forum_boards

Adds support for 'link' boards — rows that point at another page (e.g.
/leaderboard, /giveaways, or an external URL) instead of containing threads,
so navigation shortcuts can live inside the forum instead of the bottom nav.

On a create_all-built DB the columns already exist, so the ADD COLUMN guards
are no-ops there.

Revision ID: b2d4f6a8c0e2
Revises: a9f1e3c7b5d2
Create Date: 2026-06-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b2d4f6a8c0e2'
down_revision: Union[str, None] = 'a9f1e3c7b5d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return column in {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    if not _has_column("forum_boards", "board_type"):
        op.add_column(
            "forum_boards",
            sa.Column("board_type", sa.String(), nullable=False, server_default="forum"),
        )
    if not _has_column("forum_boards", "link_target"):
        op.add_column(
            "forum_boards",
            sa.Column("link_target", sa.String(), nullable=True),
        )


def downgrade() -> None:
    if _has_column("forum_boards", "link_target"):
        op.drop_column("forum_boards", "link_target")
    if _has_column("forum_boards", "board_type"):
        op.drop_column("forum_boards", "board_type")
