"""add PostgreSQL full-text search (tsvector + GIN) and pg_trgm indexes

PostgreSQL only — adds generated `search_vector` tsvector columns to threads and
posts (with GIN indexes) and pg_trgm GIN indexes on users.username/first_name.
No-op on SQLite (dev/tests fall back to ILIKE). The same idempotent DDL also runs
at app startup (ensure_search_schema), so this migration mainly documents the
change and covers operators who run `alembic upgrade` on an existing database.

Revision ID: d3e4f5a6b7c8
Revises: c7d8e9f0a1b2
Create Date: 2026-06-21

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'd3e4f5a6b7c8'
down_revision: Union[str, Sequence[str], None] = 'c7d8e9f0a1b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_UPGRADE = (
    "CREATE EXTENSION IF NOT EXISTS pg_trgm",
    "ALTER TABLE threads ADD COLUMN IF NOT EXISTS search_vector tsvector "
    "GENERATED ALWAYS AS ("
    "  setweight(to_tsvector('english', coalesce(title, '')), 'A') || "
    "  setweight(to_tsvector('english', coalesce(content, '')), 'B')"
    ") STORED",
    "CREATE INDEX IF NOT EXISTS ix_threads_search_vector ON threads USING gin (search_vector)",
    "ALTER TABLE posts ADD COLUMN IF NOT EXISTS search_vector tsvector "
    "GENERATED ALWAYS AS (to_tsvector('english', coalesce(content, ''))) STORED",
    "CREATE INDEX IF NOT EXISTS ix_posts_search_vector ON posts USING gin (search_vector)",
    "CREATE INDEX IF NOT EXISTS ix_users_username_trgm ON users USING gin (username gin_trgm_ops)",
    "CREATE INDEX IF NOT EXISTS ix_users_first_name_trgm ON users USING gin (first_name gin_trgm_ops)",
)

_DOWNGRADE = (
    "DROP INDEX IF EXISTS ix_users_first_name_trgm",
    "DROP INDEX IF EXISTS ix_users_username_trgm",
    "DROP INDEX IF EXISTS ix_posts_search_vector",
    "ALTER TABLE posts DROP COLUMN IF EXISTS search_vector",
    "DROP INDEX IF EXISTS ix_threads_search_vector",
    "ALTER TABLE threads DROP COLUMN IF EXISTS search_vector",
)


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for stmt in _UPGRADE:
        op.execute(stmt)


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for stmt in _DOWNGRADE:
        op.execute(stmt)
