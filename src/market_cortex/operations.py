"""Explicit profiles, read-only preflight and bounded daily-refresh jobs.

Use python -m market_cortex.operations. No service or schedule is installed.
Database credentials are resolved from a named environment variable only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from psycopg.conninfo import conninfo_to_dict
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field

from .config import Settings
from .contracts import utc
from .database import connect
from .identity import IdentityRegistry
from .jobs import JobQueue
from .providers import BinanceDaily, ProviderFailure
from .storage import ArtifactStore, PostgresCatalog

ROOT = Path(__file__).resolve().parents[2]
KIND = "operational_daily_refresh_v1"


class Profile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    environment: str = Field(pattern=r"^(OWNER_MAIN|PILOT_TEST|DEVELOPMENT_TEST)$")
    database_env: str = Field(pattern=r"^MARKET_CORTEX_[A-Z_]+$")
    data_root: str = Field(min_length=1, max_length=512)
    symbols: tuple[str, ...] = Field(default=("BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"), min_length=1, max_length=50)
    refresh_time: str = Field(default="07:00", pattern=r"^([01][0-9]|2[0-3]):[0-5][0-9]$")
    timezone: str = "Asia/Kolkata"
    correction_overlap_days: int = Field(default=3, ge=1, le=30)


class RefreshPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profile_key: str
    symbol: str = Field(pattern=r"^[A-Z0-9]{3,20}$")
    start: datetime
    end: datetime


def load_profile(path: Path) -> tuple[Profile, Settings]:
    if path.stat().st_size > 8192:
        raise ValueError("PROFILE_TOO_LARGE")
    profile = Profile.model_validate_json(path.read_text(encoding="utf-8"))
    ZoneInfo(profile.timezone)
    if len(set(profile.symbols)) != len(profile.symbols) or any(not re.fullmatch(r"[A-Z0-9]{3,20}", s) for s in profile.symbols):
        raise ValueError("INVALID_SYMBOLS")
    root = Path(profile.data_root).expanduser()
    if not root.is_absolute():
        root = ROOT / root
    root = root.resolve()
    dsn = os.environ.get(profile.database_env)
    if not dsn:
        raise ValueError("DATABASE_NOT_CONFIGURED")
    parts = conninfo_to_dict(dsn)
    if parts.get("host") not in {"127.0.0.1", "localhost", "::1"} or parts.get("hostaddr") not in {None, "127.0.0.1", "::1"}:
        raise ValueError("DATABASE_MUST_BE_LOOPBACK")
    if parts.get("options") or parts.get("service"):
        raise ValueError("PROFILE_DATABASE_OPTIONS_FORBIDDEN")
    name = parts.get("dbname", "").lower()
    owner_root = Path("C:/MarketCortexData").resolve()
    overlaps_owner = root == owner_root or owner_root in root.parents or root in owner_root.parents
    if profile.environment != "OWNER_MAIN" and (not name.endswith("_test") or overlaps_owner):
        raise ValueError("TEST_PROFILE_ISOLATION_REQUIRED")
    if profile.environment == "OWNER_MAIN" and (not name or name.endswith("_test") or not overlaps_owner or root != owner_root):
        raise ValueError("OWNER_PROFILE_ISOLATION_REQUIRED")
    base = Settings.load(ROOT)
    return profile, Settings(dsn, root, base.owner_timezone, base.base_currency,
                             base.cloud_model_allowed, base.owner_configured, profile.environment)


def profile_key(settings: Settings) -> str:
    parts = conninfo_to_dict(settings.database_url)
    return hashlib.sha256(json.dumps([settings.environment, parts.get("host"), parts.get("port", "5432"),
                                     parts.get("dbname"), str(settings.data_root)], separators=(",", ":")).encode()).hexdigest()


def preflight(settings: Settings, *, integrity: bool = False) -> dict:
    report = {"settings": settings.safe_summary(), "status": "FAILED", "checks": {}}
    if not settings.database_url:
        report["checks"]["database"] = "DATABASE_NOT_CONFIGURED"
        return report
    try:
        with connect(settings.database_url) as connection:
            connection.execute("SET TRANSACTION READ ONLY")
            encoding = connection.execute("SHOW server_encoding").fetchone()[0]
            report["checks"]["encoding"] = encoding
            present = connection.execute("SELECT to_regclass('schema_migrations')").fetchone()[0]
            applied = dict(connection.execute("SELECT name,checksum FROM schema_migrations").fetchall()) if present else {}
            pending, changed = [], []
            for path in sorted((ROOT / "infra/migrations").glob("[0-9]*.sql")):
                expected = hashlib.sha256(path.read_text(encoding="utf-8").encode()).hexdigest()
                if path.name not in applied:
                    pending.append(path.name)
                elif applied[path.name] != expected:
                    changed.append(path.name)
            report["checks"].update(database="CONNECTED_READ_ONLY", pending_migrations=pending, changed_migrations=changed,
                                    data_root_exists=settings.data_root.is_dir())
        if encoding == "UTF8" and not pending and not changed and settings.data_root.is_dir():
            report["status"] = "VALIDATED"
            if integrity:
                inventory = PostgresCatalog(settings.database_url, ArtifactStore(settings.data_root)).scan_storage()
                report["checks"]["storage"] = inventory
                if inventory["missing"] or inventory["corrupt"]:
                    report["status"] = "FAILED"
    except Exception as error:
        report["checks"]["database"] = "UNAVAILABLE:" + type(error).__name__
    return report


def catalog_for(settings: Settings) -> PostgresCatalog:
    return PostgresCatalog(settings.database_url, ArtifactStore(settings.data_root))


def refresh_plan(profile: Profile, settings: Settings, now: datetime, *, start: datetime | None = None) -> list[RefreshPayload]:
    now = utc(now)
    end = now.replace(hour=0, minute=0, second=0, microsecond=0)
    catalog = catalog_for(settings)
    instruments, mappings = catalog.load_identity()
    registry = IdentityRegistry(instruments, mappings)
    plans = []
    for symbol in profile.symbols:
        instrument = registry.resolve(provider_id="binance", identifier_type="exchange_pair", identifier_value=symbol,
                                      venue_id="BINANCE_SPOT", at=now, known_at=now)
        with connect(settings.database_url) as connection:
            latest = connection.execute("""SELECT max(session_date) FROM observations
                WHERE instrument_id=%s AND provider_id='binance' AND interval='P1D' AND adjustment_basis='raw'
                  AND quality_state IN ('valid','corrected') AND available_at <= %s""", (instrument.instrument_id, now)).fetchone()[0]
        first = utc(start) if start else (datetime.combine(latest, datetime.min.time(), timezone.utc)
                - timedelta(days=profile.correction_overlap_days - 1) if latest else end - timedelta(days=30))
        first = max(first, instrument.valid_from)
        if first.hour or first.minute or first.second or first.microsecond or first >= end or (end - first).days > 366:
            raise ValueError("REFRESH_REQUIRES_UTC_MIDNIGHT_RANGE_1_TO_366_DAYS")
        plans.append(RefreshPayload(profile_key=profile_key(settings), symbol=symbol, start=first, end=end))
    return plans


def due_slot(profile: Profile, now: datetime) -> str:
    local = utc(now).astimezone(ZoneInfo(profile.timezone))
    hour, minute = map(int, profile.refresh_time.split(":"))
    planned = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if local < planned:
        planned -= timedelta(days=1)
    return planned.isoformat()  # one catch-up batch for the latest missed slot


def enqueue_refresh(profile: Profile, settings: Settings, now: datetime, *, scheduled: bool = False,
                    start: datetime | None = None) -> list[str]:
    plans = refresh_plan(profile, settings, now, start=start)
    queue = JobQueue(settings.database_url)
    slot = due_slot(profile, now) if scheduled else utc(now).isoformat()
    return [str(queue.enqueue(KIND, f"{KIND}:{plan.profile_key}:{slot}:{plan.symbol}", plan.model_dump(mode="json"))) for plan in plans]


def worker(profile: Profile, settings: Settings, *, adapter=None) -> dict:
    queue = JobQueue(settings.database_url)
    with connect(settings.database_url) as connection:
        candidate = connection.execute("""SELECT job_id FROM jobs WHERE kind=%s AND payload->>'profile_key'=%s
            AND ((state='ready' AND next_attempt_at<=now()) OR (state='leased' AND lease_until<now()))
            ORDER BY next_attempt_at,job_id LIMIT 1""", (KIND, profile_key(settings))).fetchone()
    job = queue.claim(600, kind=KIND, job_id=candidate[0]) if candidate else None
    if job is None:
        return {"status": "IDLE"}
    try:
        plan = RefreshPayload.model_validate(job.payload)
        if plan.profile_key != profile_key(settings) or plan.symbol not in profile.symbols:
            raise ValueError("REFRESH_PROFILE_MISMATCH")
        start, end = utc(plan.start), utc(plan.end)
        if start >= end or (end-start) > timedelta(days=366) or end > datetime.now(timezone.utc).replace(hour=0,minute=0,second=0,microsecond=0):
            raise ValueError("INVALID_REFRESH_RANGE")
        catalog = catalog_for(settings)
        instruments, mappings = catalog.load_identity()
        registry = IdentityRegistry(instruments, mappings)
        instrument = registry.resolve(provider_id="binance", identifier_type="exchange_pair", identifier_value=plan.symbol,
                                      venue_id="BINANCE_SPOT", at=end, known_at=datetime.now(timezone.utc))
        mapping = registry.mapping_for(instrument.instrument_id, "binance", "exchange_pair", start)
        calendar = catalog.load_calendar(instrument.primary_venue_id, start, end)
        fetched = (adapter or BinanceDaily()).fetch_daily(instrument, mapping, calendar, start, end)
        result = catalog.ingest(list(fetched.bars), calendar, source_batch_id=fetched.batch_id,
                                provider_id=fetched.provider_id, raw_hash=fetched.raw_hash, fetched_at=fetched.fetched_at)
        output = {"symbol": plan.symbol, "stored": result.stored, "duplicates": result.duplicates,
                  "quarantined": result.quarantined, "manifest_id": str(result.manifest_id) if result.manifest_id else None,
                  "completed_at": datetime.now(timezone.utc).isoformat(), "pages": fetched.pages}
        # Result and successful completion are atomic. Interrupted ingestion remains idempotent.
        with connect(settings.database_url) as connection:
            row = connection.execute("""UPDATE jobs SET state='done',lease_until=NULL,error_code=NULL,
                payload=jsonb_set(payload,'{operational_result}',%s) WHERE job_id=%s AND state='leased'
                AND attempts=%s AND lease_until>now() RETURNING job_id""", (Jsonb(output), job.job_id, job.attempts)).fetchone()
            if not row:
                raise RuntimeError("STALE_REFRESH_LEASE")
        return {"status": "DONE", "job_id": str(job.job_id), **output}
    except ProviderFailure as error:
        state = queue.finish(job.job_id, job.attempts, error.code, max_attempts=3 if error.retryable else 1)
        return {"status": state.upper(), "job_id": str(job.job_id), "code": error.code}
    except Exception as error:
        code = "REFRESH_FAILED:" + type(error).__name__
        state = queue.finish(job.job_id, job.attempts, code, max_attempts=1 if isinstance(error, ValueError) else 3)
        return {"status": state.upper(), "job_id": str(job.job_id), "code": code}


def status(settings: Settings, now: datetime) -> dict:
    with connect(settings.database_url) as connection:
        rows = connection.execute("""SELECT j.job_id,j.state,j.attempts,j.next_attempt_at,j.error_code,j.payload
            FROM jobs j WHERE kind=%s AND payload->>'profile_key'=%s ORDER BY next_attempt_at DESC LIMIT 50""", (KIND,profile_key(settings))).fetchall()
        latest = connection.execute("""SELECT instrument_id,max(session_date) FROM observations
            WHERE provider_id='binance' AND adjustment_basis='raw' AND quality_state IN ('valid','corrected')
                AND available_at <= %s GROUP BY instrument_id""", (utc(now),)).fetchall()
    expected = utc(now).date() - timedelta(days=1)
    return {"environment": settings.environment, "expected_closed_session": expected.isoformat(),
            "freshness_policy": "binance_utc_daily_closed_session_v1", "items": [
                {"instrument_id": str(i), "last_session": day.isoformat(), "freshness": "FRESH" if day == expected else "STALE"}
                for i, day in latest], "jobs": [
                {"job_id": str(r[0]), "state": r[1], "attempts": r[2], "next_attempt_at": r[3].isoformat(),
                 "error_code": r[4], "symbol": r[5].get("symbol"), "result": r[5].get("operational_result")} for r in rows]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["preflight", "plan", "refresh", "schedule", "worker", "status"])
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--integrity", action="store_true")
    parser.add_argument("--start", type=datetime.fromisoformat)
    parser.add_argument("--confirm-owner-writes", action="store_true")
    args = parser.parse_args()
    try:
        profile, settings = load_profile(args.profile)
        now = datetime.now(timezone.utc)
        if args.command in {"refresh", "schedule", "worker"} and settings.environment == "OWNER_MAIN" and not args.confirm_owner_writes:
            raise ValueError("OWNER_WRITE_AUTHORIZATION_REQUIRED")
        if args.command == "preflight":
            result = preflight(settings, integrity=args.integrity)
        elif args.command == "plan":
            result = {"environment": settings.environment, "next_slot": due_slot(profile, now),
                      "items": [p.model_dump(mode="json") for p in refresh_plan(profile,settings,now,start=args.start)], "writes": False}
        elif args.command in {"refresh", "schedule"}:
            result = {"environment": settings.environment, "jobs": enqueue_refresh(profile,settings,now,
                        scheduled=args.command == "schedule", start=args.start)}
        elif args.command == "worker":
            result = worker(profile, settings)
        else:
            result = status(settings, now)
        print(json.dumps(result, ensure_ascii=True))
        return 1 if result.get("status") in {"FAILED", "DEAD", "READY"} else 0
    except Exception as error:
        # Validation errors can contain input/credentials: whitelist our codes only.
        code = str(error) if type(error) is ValueError and re.fullmatch(r"[A-Z_0-9]+", str(error)) else type(error).__name__
        print(json.dumps({"status": "FAILED", "code": code}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
