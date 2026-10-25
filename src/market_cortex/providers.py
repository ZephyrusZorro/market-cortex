"""Read-only daily-bar adapters. Native IDs never become canonical IDs.

Only fixed public/history/instrument endpoints are reachable. No order, account
mutation, broker write, or streaming endpoint exists in this module.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Protocol
from urllib.parse import quote
from uuid import UUID, uuid4

import httpx

from .calendar import CalendarMissing, SessionCalendar
from .contracts import Bar, IdentifierMapping, Instrument, ObservationEnvelope, utc

HOSTS = {
    "fapi.binance.com": (r"/fapi/v1/exchangeInfo", r"/fapi/v1/fundingRate", r"/futures/data/openInterestHist", r"/fapi/v1/premiumIndex"),
    "api.fiscaldata.treasury.gov": (r"/services/api/fiscal_service/v2/accounting/od/avg_interest_rates",),
    "data-api.binance.vision": (r"/api/v3/klines", r"/api/v3/exchangeInfo"),
    "data.alpaca.markets": (r"/v2/stocks/[A-Z0-9]+(?:\.[A-Z0-9]+)?/bars",),
    "paper-api.alpaca.markets": (r"/v2/assets", r"/v2/calendar"),
    "api.alpaca.markets": (r"/v2/assets", r"/v2/calendar"),
    "api.upstox.com": (r"/v2/instruments/search", r"/v3/feed/market-data-feed/authorize", r"/v3/historical-candle/(?:NSE|BSE)_EQ%7C[A-Z0-9]+/(?:minutes|hours|days|weeks|months)/[0-9]+/\d{4}-\d{2}-\d{2}/\d{4}-\d{2}-\d{2}"),
}
MAX_RESPONSE_BYTES = 4_000_000
MAX_PAGES = 30


class ProviderFailure(Exception):
    """Code only; never include URLs, headers, response bodies, or raw exceptions."""

    def __init__(self, code: str, retryable: bool = False):
        self.code = code
        self.retryable = retryable
        super().__init__(code)


class NotConfigured(ProviderFailure):
    def __init__(self):
        super().__init__("NOT_CONFIGURED")


@dataclass(frozen=True)
class Page:
    data: object
    content_hash: str
    status: int
    rate_limit_headers: dict[str, int] = field(default_factory=dict)


class ReadTransport:
    def __init__(self, client: httpx.Client | None = None, *, max_response_bytes=MAX_RESPONSE_BYTES):
        self.client = client or httpx.Client(timeout=httpx.Timeout(10.0, connect=5.0), follow_redirects=False)
        self.max_response_bytes = max_response_bytes

    def before_attempt(self, host: str, path: str) -> None:
        """Optional independent-provider budget hook; default transport unchanged."""

    def observe_response(self, host: str, status: int, headers) -> None:
        """Optional quota/cooldown hook. Never persist raw response headers."""

    def get(self, host: str, path: str, *, params: dict | None = None, headers: dict | None = None) -> Page:
        if host not in HOSTS or not any(re.fullmatch(pattern, path) for pattern in HOSTS[host]):
            raise ProviderFailure("ENDPOINT_NOT_ALLOWED")
        if params and any(key.lower() in ("api_key", "secret", "token", "authorization") for key in params):
            raise ProviderFailure("CREDENTIAL_IN_QUERY_FORBIDDEN")
        for attempt in range(3):
            self.before_attempt(host, path)
            try:
                with self.client.stream("GET", f"https://{host}{path}", params=params, follow_redirects=False,
                                        headers={"Accept": "application/json", **(headers or {})}) as response:
                    status = response.status_code
                    self.observe_response(host, status, response.headers)
                    if status in (401, 403):
                        raise ProviderFailure("ACCESS_DENIED")
                    if status in (429, 500, 502, 503, 504):
                        if attempt < 2:
                            # Bounded by design; no unbounded provider Retry-After.
                            time.sleep(min(2.0, 0.25 * (2 ** attempt)))
                            continue
                        raise ProviderFailure("RATE_LIMITED" if status == 429 else "PROVIDER_UNAVAILABLE", retryable=True)
                    if status != 200:
                        raise ProviderFailure("HTTP_ERROR")
                    length = response.headers.get("Content-Length")
                    if length and length.isdigit() and int(length) > self.max_response_bytes:
                        raise ProviderFailure("RESPONSE_TOO_LARGE")
                    payload = bytearray()
                    for chunk in response.iter_bytes():
                        payload.extend(chunk)
                        if len(payload) > self.max_response_bytes:
                            raise ProviderFailure("RESPONSE_TOO_LARGE")
                    body = bytes(payload)
                    try:
                        safe_limits = {}
                        for name in ('x-ratelimit-limit','x-ratelimit-remaining','x-ratelimit-reset','x-mbx-used-weight-1m'):
                            value = response.headers.get(name,'')
                            if value.isdigit() and len(value) <= 12:
                                safe_limits[name] = int(value)
                        return Page(json.loads(body), hashlib.sha256(body).hexdigest(), status, safe_limits)
                    except (ValueError, UnicodeError):
                        raise ProviderFailure("MALFORMED_JSON") from None
            except ProviderFailure:
                raise
            except (httpx.TimeoutException, httpx.NetworkError):
                if attempt == 2:
                    raise ProviderFailure("NETWORK_TIMEOUT_OR_ERROR", retryable=True) from None
                time.sleep(min(2.0, 0.25 * (2 ** attempt)))
            except httpx.HTTPError:
                raise ProviderFailure("NETWORK_ERROR", retryable=True) from None
        raise ProviderFailure("PROVIDER_UNAVAILABLE", retryable=True)


@dataclass(frozen=True)
class FetchBatch:
    batch_id: UUID
    provider_id: str
    fetched_at: datetime
    raw_hash: str
    bars: tuple[Bar, ...]
    pages: int
    feed_class: str
    adjustment_basis: str


class DailyProvider(Protocol):
    provider_id: str
    def fetch_daily(self, instrument: Instrument, mapping: IdentifierMapping,
                    calendar: SessionCalendar, start: datetime, end: datetime) -> FetchBatch: ...


def require_identity(provider_id: str, instrument: Instrument, mapping: IdentifierMapping,
                     calendar: SessionCalendar, identifier_type: str,
                     start: datetime, end: datetime) -> None:
    if (mapping.provider_id != provider_id or mapping.instrument_id != instrument.instrument_id or
        mapping.venue_id != instrument.primary_venue_id or mapping.venue_id != calendar.venue.venue_id or
        mapping.identifier_type != identifier_type):
        raise ProviderFailure("IDENTITY_MISMATCH")
    start, end = utc(start), utc(end)
    if start >= end:
        raise ValueError("invalid interval")
    if (start < mapping.valid_from or mapping.valid_to is not None and end > mapping.valid_to or
        start < instrument.valid_from or instrument.valid_to is not None and end > instrument.valid_to):
        raise ProviderFailure("IDENTITY_OUTSIDE_VALID_INTERVAL")


def prices(raw: object) -> Decimal:
    try:
        value = Decimal(str(raw))
        if not value.is_finite():
            raise InvalidOperation
        return value
    except (InvalidOperation, TypeError, ValueError):
        raise ProviderFailure("MALFORMED_CANDLE") from None


def build_bar(*, instrument: Instrument, mapping: IdentifierMapping, calendar: SessionCalendar,
              provider: str, batch_id: UUID, fetched_at: datetime, source_hash: str,
              record_id: str, session_date: date, open_: object, high: object, low: object,
              close: object, volume: object | None, feed: str, adjustment: str,
              timestamp_precision: str = "day", window_basis: str = "session") -> Bar:
    try:
        session = calendar.session(session_date)
    except CalendarMissing:
        raise ProviderFailure("CALENDAR_UNKNOWN") from None
    if session.status == "holiday":
        raise ProviderFailure("CANDLE_ON_HOLIDAY")
    start_at, end_at = calendar.local_day_window(session_date) if window_basis == "local_day" else (session.open_at, session.close_at)
    envelope = ObservationEnvelope(
        observation_id=uuid4(), instrument_id=instrument.instrument_id, venue_id=mapping.venue_id,
        provider_id=provider, provider_record_id=record_id, event_at=end_at,
        available_at=fetched_at, availability_basis="observed_arrival", ingested_at=fetched_at,
        timestamp_precision=timestamp_precision, is_final=True, quality_state="valid",
        freshness_policy_id=f"{provider}:{feed}:daily", validation_codes=[],
        source_ref=f"{provider}:daily:{batch_id}", source_batch_id=batch_id,
        raw_content_hash=source_hash, raw_retention_state="hash_only", normalizer_version="daily_v1",
        license_policy_id="hash_only", currency=instrument.trading_currency, unit=instrument.price_unit,
        adjustment_basis=adjustment,
    )
    return Bar(envelope=envelope, interval="P1D", start_at=start_at, end_at=end_at,
               session_date=session_date, calendar_id=calendar.calendar_id,
               open=prices(open_), high=prices(high), low=prices(low), close=prices(close),
               volume=prices(volume) if volume is not None else None,
               aggregation_method=f"provider_{feed}:{window_basis}", quote_currency=instrument.trading_currency,
               volume_unit=instrument.quantity_unit)


def finish(batch_id: UUID, provider: str, fetched: datetime, hashes: list[str],
           bars: list[Bar], feed: str, adjustment: str) -> FetchBatch:
    combined = hashlib.sha256("".join(hashes).encode("ascii")).hexdigest()
    return FetchBatch(batch_id, provider, fetched, combined, tuple(bars), len(hashes), feed, adjustment)


class BinanceDaily:
    provider_id = "binance"

    def __init__(self, transport: ReadTransport | None = None):
        self.transport = transport or ReadTransport()

    def fetch_daily(self, instrument: Instrument, mapping: IdentifierMapping,
                    calendar: SessionCalendar, start: datetime, end: datetime) -> FetchBatch:
        require_identity(self.provider_id, instrument, mapping, calendar, "exchange_pair", start, end)
        if calendar.venue.session_kind != "24x7" or not re.fullmatch(r"[A-Z0-9]{3,20}", mapping.identifier_value):
            raise ProviderFailure("UNSUPPORTED_IDENTITY_OR_CALENDAR")
        start, end = utc(start), utc(end)
        if start >= end:
            raise ValueError("invalid interval")
        batch_id, fetched = uuid4(), datetime.now(timezone.utc)
        hashes, bars = [], []
        cursor = int(start.timestamp() * 1000)
        stop = int(end.timestamp() * 1000)
        last_open_seen = None
        for _ in range(MAX_PAGES):
            page = self.transport.get("data-api.binance.vision", "/api/v3/klines", params={
                "symbol": mapping.identifier_value, "interval": "1d", "startTime": cursor,
                "endTime": stop - 1, "timeZone": "0", "limit": 1000})
            hashes.append(page.content_hash)
            if not isinstance(page.data, list):
                raise ProviderFailure("MALFORMED_CANDLE_RESPONSE")
            for row in page.data:
                if (not isinstance(row, list) or len(row) < 7 or type(row[0]) is not int
                        or type(row[6]) is not int):
                    raise ProviderFailure("MALFORMED_CANDLE")
                if row[0] % 86_400_000 or row[6] != row[0] + 86_400_000 - 1:
                    raise ProviderFailure("UNEXPECTED_DAILY_WINDOW")
                open_at = datetime.fromtimestamp(row[0] / 1000, timezone.utc)
                if row[0] < cursor or last_open_seen is not None and row[0] <= last_open_seen:
                    raise ProviderFailure("NONMONOTONIC_PAGE")
                last_open_seen = row[0]
                if open_at + timedelta(days=1) > fetched or not start <= open_at < end:
                    continue  # in-progress day is never a complete daily candle
                bars.append(build_bar(instrument=instrument, mapping=mapping, calendar=calendar,
                                      provider=self.provider_id, batch_id=batch_id, fetched_at=fetched,
                                      source_hash=page.content_hash, record_id=f"{mapping.identifier_value}:{row[0]}",
                                      session_date=open_at.date(), open_=row[1], high=row[2], low=row[3],
                                      close=row[4], volume=row[5], feed="spot_public", adjustment="raw"))
            if not page.data or len(page.data) < 1000:
                break
            next_cursor = page.data[-1][0] + 86_400_000
            if next_cursor <= cursor:
                raise ProviderFailure("PAGINATION_STALLED")
            cursor = next_cursor
        else:
            raise ProviderFailure("PAGE_LIMIT_REACHED")
        return finish(batch_id, self.provider_id, fetched, hashes, bars, "spot_public", "raw")


class AlpacaDaily:
    provider_id = "alpaca"

    def __init__(self, transport: ReadTransport | None = None, feed: str = "iex"):
        if feed not in ("iex", "sip"):
            raise ValueError("unsupported feed")
        self.transport, self.feed = transport or ReadTransport(), feed

    def fetch_daily(self, instrument: Instrument, mapping: IdentifierMapping,
                    calendar: SessionCalendar, start: datetime, end: datetime) -> FetchBatch:
        require_identity(self.provider_id, instrument, mapping, calendar, "ticker", start, end)
        if calendar.venue.session_kind != "regular" or calendar.venue.timezone != "America/New_York":
            raise ProviderFailure("UNSUPPORTED_IDENTITY_OR_CALENDAR")
        key, secret = os.environ.get("APCA_API_KEY_ID"), os.environ.get("APCA_API_SECRET_KEY")
        if not key or not secret:
            raise NotConfigured()
        symbol = mapping.identifier_value
        if not re.fullmatch(r"[A-Z0-9]+(?:\.[A-Z0-9]+)?", symbol) or len(symbol) > 15:
            raise ProviderFailure("INVALID_NATIVE_SYMBOL")
        start, end = utc(start), utc(end)
        batch_id, fetched = uuid4(), datetime.now(timezone.utc)
        hashes, bars, page_token = [], [], None
        seen = set()
        for _ in range(MAX_PAGES):
            params = {"timeframe": "1Day", "start": start.isoformat(), "end": end.isoformat(),
                      "feed": self.feed, "adjustment": "raw", "asof": "-", "limit": 1000}
            if page_token:
                params["page_token"] = page_token
            page = self.transport.get("data.alpaca.markets", f"/v2/stocks/{symbol}/bars", params=params,
                                      headers={"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret})
            hashes.append(page.content_hash)
            if not isinstance(page.data, dict) or not isinstance(page.data.get("bars"), list):
                raise ProviderFailure("MALFORMED_CANDLE_RESPONSE")
            for row in page.data["bars"]:
                try:
                    timestamp = datetime.fromisoformat(row["t"].replace("Z", "+00:00"))
                    session_date = calendar.date_at(timestamp)
                    session = calendar.session(session_date)
                    day_start, day_end = calendar.local_day_window(session_date)
                    if day_end > fetched or not start <= day_start < end:
                        continue
                    bars.append(build_bar(instrument=instrument, mapping=mapping, calendar=calendar,
                                          provider=self.provider_id, batch_id=batch_id, fetched_at=fetched,
                                          source_hash=page.content_hash, record_id=f"{symbol}:{session_date}",
                                          session_date=session_date, open_=row["o"], high=row["h"], low=row["l"],
                                          close=row["c"], volume=row.get("v"), feed=self.feed, adjustment="raw",
                                          window_basis="local_day"))
                except CalendarMissing:
                    raise ProviderFailure('CALENDAR_UNKNOWN') from None
                except (KeyError, AttributeError, ValueError, TypeError):
                    raise ProviderFailure("MALFORMED_CANDLE") from None
            page_token = page.data.get("next_page_token")
            if page_token is None:
                break
            if not isinstance(page_token, str) or page_token in seen:
                raise ProviderFailure("PAGINATION_STALLED")
            seen.add(page_token)
        else:
            raise ProviderFailure("PAGE_LIMIT_REACHED")
        return finish(batch_id, self.provider_id, fetched, hashes, bars, self.feed, "raw")


class UpstoxDaily:
    provider_id = "upstox"

    def __init__(self, transport: ReadTransport | None = None):
        self.transport = transport or ReadTransport()

    def fetch_daily(self, instrument: Instrument, mapping: IdentifierMapping,
                    calendar: SessionCalendar, start: datetime, end: datetime) -> FetchBatch:
        require_identity(self.provider_id, instrument, mapping, calendar, "provider_token", start, end)
        if (calendar.venue.venue_id not in ("XNSE", "XBOM") or calendar.venue.timezone != "Asia/Kolkata" or
            calendar.venue.session_kind != "regular"):
            raise ProviderFailure("UNSUPPORTED_IDENTITY_OR_CALENDAR")
        token = os.environ.get("UPSTOX_ACCESS_TOKEN")
        if not token:
            raise NotConfigured()
        native_key = mapping.identifier_value
        prefix = 'NSE_EQ' if calendar.venue.venue_id == 'XNSE' else 'BSE_EQ'
        if not re.fullmatch(prefix + r"\|[A-Z0-9]{8,30}", native_key):
            raise ProviderFailure("INVALID_NATIVE_KEY")
        start, end = utc(start), utc(end)
        if start >= end:
            raise ValueError("invalid interval")
        batch_id, fetched = uuid4(), datetime.now(timezone.utc)
        hashes, bars = [], []
        first = calendar.date_at(start)
        last = calendar.date_at(end - timedelta(microseconds=1))
        cursor = first
        while cursor <= last:
            if len(hashes) >= MAX_PAGES:
                raise ProviderFailure("PAGE_LIMIT_REACHED")
            chunk_end = min(cursor + timedelta(days=180), last)
            path = f"/v3/historical-candle/{quote(native_key, safe='')}/days/1/{chunk_end}/{cursor}"
            page = self.transport.get("api.upstox.com", path, headers={"Authorization": f"Bearer {token}"})
            hashes.append(page.content_hash)
            candles = page.data.get("data", {}).get("candles") if isinstance(page.data, dict) else None
            if not isinstance(candles, list):
                raise ProviderFailure("MALFORMED_CANDLE_RESPONSE")
            for row in candles:
                try:
                    timestamp = datetime.fromisoformat(row[0].replace("Z", "+00:00"))
                    session_date = calendar.date_at(timestamp)
                    session = calendar.session(session_date)
                    if not first <= session_date <= last or session.close_at > fetched or not start <= session.open_at < end:
                        continue
                    bars.append(build_bar(instrument=instrument, mapping=mapping, calendar=calendar,
                                          provider=self.provider_id, batch_id=batch_id, fetched_at=fetched,
                                          source_hash=page.content_hash, record_id=f"{native_key}:{session_date}",
                                          session_date=session_date, open_=row[1], high=row[2], low=row[3],
                                          close=row[4], volume=row[5], feed="historical_v3", adjustment="provider_unspecified"))
                except CalendarMissing:
                    raise ProviderFailure('CALENDAR_UNKNOWN') from None
                except (IndexError, KeyError, AttributeError, ValueError, TypeError):
                    raise ProviderFailure("MALFORMED_CANDLE") from None
            cursor = chunk_end + timedelta(days=1)
        return finish(batch_id, self.provider_id, fetched, hashes, bars, "historical_v3", "provider_unspecified")
