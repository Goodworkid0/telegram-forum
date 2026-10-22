"""add_referral_commission_fields

Revision ID: f3562f2f4fe6
Revises: 5cf8d042a5b8
Create Date: 2026-06-17 12:49:05.453261

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3562f2f4fe6'
down_revision: Union[str, None] = '5cf8d042a5b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN referral_earnings FLOAT DEFAULT 0.0")
    op.execute("ALTER TABLE app_settings ADD COLUMN referral_level1_percent FLOAT DEFAULT 3.0")
    op.execute("ALTER TABLE app_settings ADD COLUMN referral_level2_percent FLOAT DEFAULT 5.0")


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN referral_earnings")
    op.execute("ALTER TABLE app_settings DROP COLUMN referral_level1_percent")
    op.execute("ALTER TABLE app_settings DROP COLUMN referral_level2_percent")
