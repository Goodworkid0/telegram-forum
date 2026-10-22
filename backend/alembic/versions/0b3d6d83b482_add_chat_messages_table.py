"""add_chat_messages_table

Revision ID: 0b3d6d83b482
Revises: 28214411edc7
Create Date: 2026-06-16 19:07:55.555082

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0b3d6d83b482'
down_revision: Union[str, None] = '28214411edc7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES users(id),
            content TEXT NOT NULL,
            is_deleted BOOLEAN DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_chat_messages_user_id ON chat_messages(user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_chat_messages_created_at ON chat_messages(created_at)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_chat_messages_created_at")
    op.execute("DROP INDEX IF EXISTS ix_chat_messages_user_id")
    op.execute("DROP TABLE IF EXISTS chat_messages")
