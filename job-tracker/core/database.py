"""
SQLite storage layer.

Handles schema creation/migration and insert-if-new logic. A job is
considered "new" if its content_hash isn't already in the database — this
is the whole dedup mechanism, so JobListing.content_hash needs to be
stable across runs (see core/models.py).

As of the dashboard update, ALL scraped jobs are saved here (not just ones
matching your fixed search_criteria.yaml) so the dashboard can filter
across everything live. `matched_criteria` marks which ones would trigger
an email digest under your current saved criteria — it's informational,
not a save-time gate anymore.
"""
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable

from core.models import JobListing

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS jobs (
    content_hash TEXT PRIMARY KEY,
    site TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    organisation TEXT,
    location TEXT,
    salary TEXT,
    contract_type TEXT,
    description TEXT,
    posted_date TEXT,
    scraped_at TEXT NOT NULL,
    notified INTEGER NOT NULL DEFAULT 0,
    matched_criteria INTEGER NOT NULL DEFAULT 0
);
"""

# Indexes are created AFTER migrations run (see _init_schema/_run_migrations
# ordering below) since some reference columns that only exist on older
# databases once ALTER TABLE has added them.
CREATE_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_jobs_site ON jobs(site);
CREATE INDEX IF NOT EXISTS idx_jobs_notified ON jobs(notified);
CREATE INDEX IF NOT EXISTS idx_jobs_matched ON jobs(matched_criteria);
"""

# Columns added after the initial release. Each entry: (column_name, sql_type_and_default)
# Existing databases (like one already committed to your repo) get these
# added automatically via ALTER TABLE the first time this runs against them
# — no manual migration needed on your end.
MIGRATIONS = [
    ("contract_type", "TEXT"),
    ("matched_criteria", "INTEGER NOT NULL DEFAULT 0"),
]


class JobDatabase:
    def __init__(self, db_path: str = "data/jobs.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()
        self._run_migrations()
        self._create_indexes()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self):
        with self._connect() as conn:
            conn.executescript(CREATE_TABLE)

    def _run_migrations(self):
        with self._connect() as conn:
            existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(jobs)")}
            for col_name, col_def in MIGRATIONS:
                if col_name not in existing_cols:
                    conn.execute(f"ALTER TABLE jobs ADD COLUMN {col_name} {col_def}")

    def _create_indexes(self):
        with self._connect() as conn:
            conn.executescript(CREATE_INDEXES)

    def save_new_jobs(self, jobs: Iterable[JobListing]) -> list[JobListing]:
        """
        Insert jobs that aren't already in the DB. Returns the list of jobs
        that were actually new (i.e. what should go in the email digest,
        pending filter matching). Existing jobs are silently skipped —
        INSERT OR IGNORE keyed on content_hash primary key.
        """
        new_jobs = []
        with self._connect() as conn:
            for job in jobs:
                d = job.to_dict()
                cursor = conn.execute(
                    """
                    INSERT OR IGNORE INTO jobs
                        (content_hash, site, title, url, organisation, location,
                         salary, contract_type, description, posted_date, scraped_at)
                    VALUES (:content_hash, :site, :title, :url, :organisation, :location,
                             :salary, :contract_type, :description, :posted_date, :scraped_at)
                    """,
                    d,
                )
                if cursor.rowcount > 0:
                    new_jobs.append(job)
        return new_jobs

    def mark_notified(self, jobs: Iterable[JobListing]):
        with self._connect() as conn:
            for job in jobs:
                conn.execute(
                    "UPDATE jobs SET notified = 1 WHERE content_hash = ?",
                    (job.content_hash,),
                )

    def mark_matched(self, jobs: Iterable[JobListing]):
        """Flags jobs as matching the current saved search criteria (for email/dashboard badge use)."""
        with self._connect() as conn:
            for job in jobs:
                conn.execute(
                    "UPDATE jobs SET matched_criteria = 1 WHERE content_hash = ?",
                    (job.content_hash,),
                )

    def get_all_jobs(self, site: str | None = None) -> list[sqlite3.Row]:
        with self._connect() as conn:
            if site:
                return conn.execute(
                    "SELECT * FROM jobs WHERE site = ? ORDER BY scraped_at DESC", (site,)
                ).fetchall()
            return conn.execute("SELECT * FROM jobs ORDER BY scraped_at DESC").fetchall()

    def get_unnotified_jobs(self) -> list[sqlite3.Row]:
        with self._connect() as conn:
            return conn.execute(
                "SELECT * FROM jobs WHERE notified = 0 ORDER BY scraped_at DESC"
            ).fetchall()

    def count_jobs(self) -> int:
        with self._connect() as conn:
            return conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
