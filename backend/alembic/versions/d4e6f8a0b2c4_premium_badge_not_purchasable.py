"""premium_badge_not_purchasable

Premium is now sold only via the $80 Shop > Account purchase, never as a grid
badge. Make the 'Premium' badge non-purchasable so it drops out of /badges/shop
and the direct badge-purchase endpoint rejects it. The $80 purchase still grants
the badge directly (it doesn't go through the badge-purchase flow).

Revision ID: d4e6f8a0b2c4
Revises: c3d5e7f9a1b3
Create Date: 2026-06-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'd4e6f8a0b2c4'
down_revision: Union[str, None] = 'c3d5e7f9a1b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE badges SET is_purchasable = FALSE WHERE name = 'Premium'")


def downgrade() -> None:
    op.execute("UPDATE badges SET is_purchasable = TRUE WHERE name = 'Premium'")
