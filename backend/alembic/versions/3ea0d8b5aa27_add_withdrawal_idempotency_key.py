"""add_withdrawal_idempotency_key

Revision ID: 3ea0d8b5aa27
Revises: cee2376923b5
Create Date: auto
"""
from alembic import op

revision = '3ea0d8b5aa27'
down_revision = 'cee2376923b5'
branch_labels = None
depends_on = None

def upgrade():
    op.execute("ALTER TABLE withdrawal_requests ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_withdrawal_requests_idempotency_key ON withdrawal_requests (idempotency_key)")

def downgrade():
    op.execute("DROP INDEX IF EXISTS ix_withdrawal_requests_idempotency_key")
    op.execute("ALTER TABLE withdrawal_requests DROP COLUMN IF EXISTS idempotency_key")
