"""Add a BM25/lexical search column to memories.

The service docstring long promised a hybrid dense+sparse+RRF retrieval, but only the
dense (vector) leg was ever implemented. The missing lexical leg is exactly what a
store like this needs: vector search matches paraphrase but drifts on exact terms
(a symbol name, an error string, a hostname), while lexical search nails those and
misses paraphrase. Fused, they cover each other's blind spots.

This adds a generated `search_vector` tsvector over title+content+context+keywords, with
a GIN index. Generated means Postgres maintains it on every write with no application
code and no backfill step — the column is correct for all 28k existing rows the moment
the migration runs, and stays correct for every insert after.

Revision ID: 20260729_bm25_tsvector
Revises: 20260408_provenance_all
"""

from alembic import op

revision = "20260729_bm25_tsvector"
down_revision = "20260408_provenance_all"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # A generated tsvector so Postgres keeps it in sync with no writer changes. Weights
    # (A=title, B=content, C=context/keywords) let ts_rank favour a title hit over a
    # passing mention deep in the body. coalesce guards the nullable columns.
    op.execute(
        """
        ALTER TABLE memories
        ADD COLUMN IF NOT EXISTS search_vector tsvector
        GENERATED ALWAYS AS (
            setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
            setweight(to_tsvector('english', coalesce(content, '')), 'B') ||
            setweight(to_tsvector('english', coalesce(context, '')), 'C') ||
            setweight(to_tsvector('english', coalesce(array_to_string(keywords, ' '), '')), 'C')
        ) STORED
        """
    )
    # CONCURRENTLY cannot run in Alembic's transaction; a plain GIN build is fine here
    # (the table is small and this runs at deploy, not under live write load).
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_memories_search_vector "
        "ON memories USING gin (search_vector)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_memories_search_vector")
    op.execute("ALTER TABLE memories DROP COLUMN IF EXISTS search_vector")
