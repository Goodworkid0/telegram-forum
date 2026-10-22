"""add_account_setup_pin

Revision ID: cee2376923b5
Revises: a7e3f1b9c2d4
Create Date: 2026-06-20 14:30:35.075764

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cee2376923b5'
down_revision: Union[str, None] = 'a7e3f1b9c2d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN is_setup_complete BOOLEAN DEFAULT 0")
    op.execute("ALTER TABLE users ADD COLUMN pin_hash VARCHAR")


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN is_setup_complete")
    op.execute("ALTER TABLE users DROP COLUMN pin_hash")
