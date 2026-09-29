"""Manifest-pinned DuckDB scans for coverage, without unrestricted SQL input."""

from __future__ import annotations

from uuid import UUID

import duckdb

from .storage import ArtifactStore, PostgresCatalog


def manifest_coverage(catalog: PostgresCatalog, manifest_id: UUID) -> list[dict]:
    artifacts = catalog.artifacts_for(manifest_id)
    paths = []
    for artifact in artifacts:
        path = (catalog.artifacts.root / artifact.relative_path).resolve()
        if not path.is_relative_to(catalog.artifacts.root) or ArtifactStore.verify(path) != artifact.content_hash:
            raise OSError("manifest artifact integrity failure")
        paths.append(str(path))
    if not paths:
        return []
    with duckdb.connect(":memory:") as db:
        rows = db.execute("""SELECT instrument_id, count(*) AS physical_rows,
            min(event_at) AS earliest_event_at, max(event_at) AS latest_event_at
            FROM read_parquet(?) GROUP BY instrument_id ORDER BY instrument_id""", [paths]).fetchall()
    # Counts include correction revisions; do not label them unique sessions.
    return [{"instrument_id": row[0], "physical_rows": row[1],
             "earliest_event_at": row[2], "latest_event_at": row[3]} for row in rows]
