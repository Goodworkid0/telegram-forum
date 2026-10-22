"""add_custom_handle_to_users

Revision ID: d525ba42ab46
Revises: d8a77a086715
Create Date: 2026-06-16 19:07:50.419658

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd525ba42ab46'
down_revision: Union[str, None] = 'd8a77a086715'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # NB: use sa.false() for the server default — a literal "DEFAULT 0" is valid
    # in SQLite but rejected by Postgres (boolean column, integer default).
    op.add_column(
        'users',
        sa.Column('uses_custom_handle', sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column('users', 'uses_custom_handle')
