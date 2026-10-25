"""Read-only, UTC-normalized fingerprints of every application table."""
from psycopg import sql

from .database import connect
from .owner_migration import digest, require
from .owner_onboarding import schema_fingerprint


def inventory(connection):
    connection.execute("SET LOCAL timezone='UTC'")
    connection.execute("SET LOCAL statement_timeout='60s'")
    schema = connection.execute('SELECT current_schema()').fetchone()[0]
    tables = connection.execute("""SELECT schemaname,tablename FROM pg_tables
        WHERE schemaname !~ '^pg_' AND schemaname <> 'information_schema' ORDER BY 1,2""").fetchall()
    require(all(s == schema for s, _ in tables), 'UNINSPECTED_SCHEMA_TABLES_PRESENT')
    counts, hashes = {}, {}
    for _, name in tables:
        records = connection.execute(sql.SQL('SELECT to_jsonb(r) FROM {} r').format(sql.Identifier(schema, name)))
        fingerprints = []
        for row in records:
            require(len(fingerprints) < 1_000_000, 'PROTECTION_INVENTORY_LIMIT')
            fingerprints.append(digest(row[0]))
        counts[name] = len(fingerprints)
        hashes[name] = digest(sorted(fingerprints))
    ledger = dict(connection.execute('SELECT name,checksum FROM schema_migrations ORDER BY name'))
    head = connection.execute('SELECT manifest_id FROM dataset_head WHERE singleton=true').fetchone()
    return {'schema': schema, 'schema_hash': schema_fingerprint(connection), 'counts': counts, 'row_hashes': hashes,
            'ledger': ledger, 'head': str(head[0]) if head and head[0] else None}


def read_inventory(dsn, schema=None):
    with connect(dsn) as c:
        c.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
        if schema:
            c.execute(sql.SQL('SET LOCAL search_path TO {}').format(sql.Identifier(schema)))
        return inventory(c)
