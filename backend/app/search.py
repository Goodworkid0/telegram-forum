"""Full-text search support.

On PostgreSQL we use real linguistic full-text search: generated `tsvector`
columns on threads (title weighted above body) and posts, with GIN indexes, and
ranked results via `ts_rank` over `websearch_to_tsquery` (so users can type
quoted "phrases", OR, and -negation). Username/name search is accelerated with
pg_trgm GIN indexes so the existing ILIKE stays fast and gains typo tolerance.

The FTS columns/indexes are created idempotently by `ensure_search_schema()`,
called on startup, because fresh production databases are stamped (not migrated)
by the entrypoint. A migration also performs the same DDL for explicit history.
"""
import logging

from sqlalchemy import func, literal_column, text

from app.database import engine

logger = logging.getLogger(__name__)

IS_POSTGRES = engine.dialect.name == "postgresql"
_TS_CONFIG = "english"

# Idempotent DDL — safe to run on every startup and re-run by the migration.
SEARCH_DDL = (
    "CREATE EXTENSION IF NOT EXISTS pg_trgm",
    # threads: title (weight A) + content (weight B)
    "ALTER TABLE threads ADD COLUMN IF NOT EXISTS search_vector tsvector "
    "GENERATED ALWAYS AS ("
    "  setweight(to_tsvector('english', coalesce(title, '')), 'A') || "
    "  setweight(to_tsvector('english', coalesce(content, '')), 'B')"
    ") STORED",
    "CREATE INDEX IF NOT EXISTS ix_threads_search_vector ON threads USING gin (search_vector)",
    # posts: content
    "ALTER TABLE posts ADD COLUMN IF NOT EXISTS search_vector tsvector "
    "GENERATED ALWAYS AS (to_tsvector('english', coalesce(content, ''))) STORED",
    "CREATE INDEX IF NOT EXISTS ix_posts_search_vector ON posts USING gin (search_vector)",
    # trigram acceleration for handle/name ILIKE search
    "CREATE INDEX IF NOT EXISTS ix_users_username_trgm ON users USING gin (username gin_trgm_ops)",
    "CREATE INDEX IF NOT EXISTS ix_users_first_name_trgm ON users USING gin (first_name gin_trgm_ops)",
)


async def ensure_search_schema() -> None:
    """Create the FTS columns/indexes if missing.

    Each statement runs in its own transaction and swallows errors so a race
    between multiple workers (or an already-present object) can't break startup.
    """
    if not IS_POSTGRES:
        return
    for stmt in SEARCH_DDL:
        try:
            async with engine.begin() as conn:
                await conn.execute(text(stmt))
        except Exception as e:  # pragma: no cover - depends on live PG
            logger.warning("ensure_search_schema skipped a statement: %s — %s", stmt[:48], e)


def _tsquery(q: str):
    # websearch_to_tsquery never raises on arbitrary input (unlike to_tsquery).
    return func.websearch_to_tsquery(_TS_CONFIG, q)


def fts_match(table: str, q: str):
    """A `search_vector @@ websearch_to_tsquery(...)` predicate for `table`."""
    return literal_column(f"{table}.search_vector").op("@@")(_tsquery(q))


def fts_rank(table: str, q: str):
    """`ts_rank(...)` relevance expression for ORDER BY (descending)."""
    return func.ts_rank(literal_column(f"{table}.search_vector"), _tsquery(q))
