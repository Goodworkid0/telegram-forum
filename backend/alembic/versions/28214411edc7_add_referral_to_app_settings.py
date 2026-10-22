"""add_referral_to_app_settings

Revision ID: 28214411edc7
Revises: 06326b775ebb
Create Date: 2026-06-16 19:07:51.212999

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '28214411edc7'
down_revision: Union[str, None] = '06326b775ebb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE app_settings ADD COLUMN referral_enabled BOOLEAN DEFAULT 0")
    op.execute("ALTER TABLE app_settings ADD COLUMN referral_percent FLOAT DEFAULT 5.0")
    op.execute("ALTER TABLE app_settings ADD COLUMN referral_first_deposit_bonus_percent FLOAT DEFAULT 10.0")


def downgrade() -> None:
    op.execute("ALTER TABLE app_settings DROP COLUMN referral_first_deposit_bonus_percent")
    op.execute("ALTER TABLE app_settings DROP COLUMN referral_percent")
    op.execute("ALTER TABLE app_settings DROP COLUMN referral_enabled")
