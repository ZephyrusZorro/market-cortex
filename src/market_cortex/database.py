"""Explicit, checksum-locked PostgreSQL migrations and catalog connection."""

from __future__ import annotations

import hashlib
from pathlib import Path

import psycopg


def connect(dsn: str) -> psycopg.Connection:
    if not dsn:
        raise RuntimeError("MARKET_CORTEX_DATABASE_URL is not configured")
    # Never include a psycopg exception or DSN in user-facing logs.
    return psycopg.connect(dsn, connect_timeout=5, application_name="market-cortex")


def migrate(dsn: str, project_root: Path) -> list[str]:
    migrations = sorted((project_root / "infra" / "migrations").glob("[0-9]*.sql"))
    applied: list[str] = []
    with connect(dsn) as connection:
        with connection.transaction():
            connection.execute("SELECT pg_advisory_xact_lock(%s)", (837_241_903,))
            connection.execute("SELECT pg_advisory_xact_lock_shared(%s)", (837_241_904,))
            connection.execute("CREATE TABLE IF NOT EXISTS schema_migrations (name text PRIMARY KEY, checksum text NOT NULL, applied_at timestamptz NOT NULL DEFAULT now())")
            for migration in migrations:
                sql = migration.read_text(encoding="utf-8")
                checksum = hashlib.sha256(sql.encode("utf-8")).hexdigest()
                row = connection.execute("SELECT checksum FROM schema_migrations WHERE name = %s", (migration.name,)).fetchone()
                if row is not None:
                    if row[0] != checksum:
                        raise RuntimeError(f"migration changed after application: {migration.name}")
                    continue
                connection.execute(sql)
                connection.execute("INSERT INTO schema_migrations (name, checksum) VALUES (%s, %s)", (migration.name, checksum))
                applied.append(migration.name)
    return applied
