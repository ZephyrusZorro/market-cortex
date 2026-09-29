"""Windows-compatible local CLI. Never prints connection strings or tokens."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from uuid import UUID

from .config import Settings
from .database import migrate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="market-cortex")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="Show safe configuration status")
    sub.add_parser("migrate", help="Apply PostgreSQL migrations")
    backup = sub.add_parser("backup", help="Create encrypted PostgreSQL + Parquet backup")
    backup.add_argument("--output", type=Path, required=True)
    restore = sub.add_parser("restore", help="Restore to an empty separate database and data directory")
    restore.add_argument("--input", type=Path, required=True)
    restore.add_argument("--data-root", type=Path, required=True)
    crypto = sub.add_parser("bootstrap-crypto", help="Resolve public Binance native spot identities")
    crypto.add_argument("--symbols", nargs="+", default=None)
    sync = sub.add_parser("sync-daily", help="Fetch and ingest a bounded daily history interval")
    sync.add_argument("--provider", choices=["binance", "alpaca", "upstox"], required=True)
    sync.add_argument("--instrument-id", type=UUID, required=True)
    sync.add_argument("--start", type=datetime.fromisoformat, required=True)
    sync.add_argument("--end", type=datetime.fromisoformat, required=True)
    sync.add_argument("--calendar-id")
    sync.add_argument("--calendar-version")
    inspect = sub.add_parser("inspect-manifest", help="Verify and summarize a pinned Parquet manifest")
    inspect.add_argument("--manifest-id", type=UUID, required=True)
    sub.add_parser("scan-storage", help="Read-only orphan, missing-file and checksum inventory")
    serve = sub.add_parser("serve", help="Start the loopback read API")
    serve.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    try:
        settings = Settings.load()
        if args.command == "doctor":
            print(json.dumps(settings.safe_summary(), indent=2))
            return 0
        if args.command == "migrate":
            if not settings.database_url:
                print("DATABASE_NOT_CONFIGURED", file=sys.stderr)
                return 2
            root = Path(__file__).resolve().parents[2]
            print(json.dumps({"applied_migrations": migrate(settings.database_url, root)}))
            return 0
        if args.command in ("bootstrap-crypto", "sync-daily", "inspect-manifest", "scan-storage"):
            if not settings.database_url:
                print("DATABASE_NOT_CONFIGURED", file=sys.stderr)
                return 2
            from .storage import ArtifactStore, PostgresCatalog
            catalog = PostgresCatalog(settings.database_url, ArtifactStore(settings.data_root))
            if args.command == "scan-storage":
                print(json.dumps(catalog.scan_storage()))
                return 0
            if args.command == "inspect-manifest":
                from .analytics import manifest_coverage
                print(json.dumps({"manifest_id": str(args.manifest_id),
                                  "coverage": manifest_coverage(catalog, args.manifest_id)}))
                return 0
            if args.command == "bootstrap-crypto":
                from .bootstrap import DEFAULT_CRYPTO_CANDIDATES, discover_crypto
                print(json.dumps(discover_crypto(catalog, args.symbols or DEFAULT_CRYPTO_CANDIDATES)))
                return 0
            from .calendar import SessionCalendar
            from .contracts import utc
            from .identity import IdentityRegistry
            from .providers import AlpacaDaily, BinanceDaily, UpstoxDaily
            start, end = utc(args.start), utc(args.end)
            if start >= end:
                print("INVALID_INTERVAL", file=sys.stderr)
                return 2
            instruments, mappings = catalog.load_identity()
            instrument = next((i for i in instruments if i.instrument_id == args.instrument_id), None)
            if instrument is None:
                print("INSTRUMENT_NOT_FOUND", file=sys.stderr)
                return 2
            kind = {"binance": "exchange_pair", "alpaca": "ticker", "upstox": "provider_token"}[args.provider]
            mapping = IdentityRegistry(instruments, mappings).mapping_for(args.instrument_id, args.provider, kind, start)
            calendar = catalog.load_calendar(instrument.primary_venue_id, start, end,
                                             args.calendar_id, args.calendar_version)
            adapter = {"binance": BinanceDaily, "alpaca": AlpacaDaily, "upstox": UpstoxDaily}[args.provider]()
            fetched = adapter.fetch_daily(instrument, mapping, calendar, start, end)
            result = catalog.ingest(list(fetched.bars), calendar, source_batch_id=fetched.batch_id,
                                    provider_id=fetched.provider_id, raw_hash=fetched.raw_hash,
                                    fetched_at=fetched.fetched_at)
            print(json.dumps({"manifest_id": str(result.manifest_id) if result.manifest_id else None,
                              "stored": result.stored, "duplicates": result.duplicates,
                              "quarantined": result.quarantined, "pages": fetched.pages,
                              "feed_class": fetched.feed_class, "adjustment_basis": fetched.adjustment_basis}))
            return 0
        if args.command in ("backup", "restore"):
            from .backup import backup as create_backup, restore as restore_backup
            passphrase = os.environ.get("MARKET_CORTEX_BACKUP_PASSPHRASE")
            if not passphrase:
                print("BACKUP_PASSPHRASE_NOT_CONFIGURED", file=sys.stderr)
                return 2
            if args.command == "backup":
                result = create_backup(settings, args.output, passphrase)
            else:
                target = os.environ.get("MARKET_CORTEX_RESTORE_DATABASE_URL")
                if not target:
                    print("RESTORE_DATABASE_NOT_CONFIGURED", file=sys.stderr)
                    return 2
                result = restore_backup(args.input, args.data_root.resolve(), target, settings.database_url, passphrase)
            print(json.dumps(result))
            return 0
        if args.command == "serve":
            import uvicorn
            uvicorn.run("market_cortex.api:app", host="127.0.0.1", port=args.port, access_log=False)
            return 0
    except Exception as exc:
        # Exception messages from drivers can contain credentials or URLs.
        print(f"OPERATION_FAILED: {type(exc).__name__}", file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
