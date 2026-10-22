"""add_last_daily_claim_to_users

Revision ID: e071f8f03791
Revises: 46f6ece172e2
Create Date: 2026-06-16 19:07:57.172715

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e071f8f03791'
down_revision: Union[str, None] = '46f6ece172e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN last_daily_claim_date DATE")


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN last_daily_claim_date")
