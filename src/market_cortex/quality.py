"""Deterministic checks and explicit missing/conflict states. No synthetic bars."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

from .calendar import CalendarMissing, SessionCalendar
from .contracts import Bar, utc


def validate_bar(bar: Bar, calendar: SessionCalendar | None) -> tuple[str, ...]:
    codes: list[str] = []
    if bar.low > min(bar.open, bar.close) or bar.high < max(bar.open, bar.close) or bar.low > bar.high:
        codes.append("OHLC_RANGE")
    if min(bar.open, bar.high, bar.low, bar.close) <= 0:
        codes.append("NONPOSITIVE_PRICE")
    if bar.volume is not None and bar.volume < 0:
        codes.append("NEGATIVE_VOLUME")
    if bar.envelope.instrument_id is None or bar.envelope.venue_id == "":
        codes.append("INVALID_IDENTITY")
    if calendar is None:
        codes.append("CALENDAR_UNKNOWN")
    else:
        if bar.envelope.venue_id != calendar.venue.venue_id or bar.calendar_id != calendar.calendar_id:
            codes.append("VENUE_CALENDAR_MISMATCH")
        try:
            session = calendar.session(bar.session_date)
            if session.status == "holiday":
                codes.append("MARKET_HOLIDAY")
            else:
                expected = (calendar.local_day_window(bar.session_date) if
                            bar.aggregation_method.endswith(":local_day") else (session.open_at, session.close_at))
                if (bar.start_at, bar.end_at) != expected:
                    codes.append("SESSION_BOUNDARY")
        except CalendarMissing:
            codes.append("CALENDAR_UNKNOWN")
    if bar.envelope.available_at is not None and bar.envelope.availability_basis == "documented_publication" and bar.envelope.available_at < bar.end_at:
        codes.append("PREMATURE_PUBLICATION")
    return tuple(sorted(set(codes)))


def missing_sessions(calendar: SessionCalendar, first: date, last: date, observed: set[date]) -> tuple[date, ...]:
    return tuple(d for d in calendar.expected_dates(first, last) if d not in observed)


@dataclass(frozen=True)
class Conflict:
    session_date: date
    provider_ids: tuple[str, ...]
    close_values: tuple[Decimal, ...]


def disagreements(bars: list[Bar], tolerance: Decimal = Decimal("0")) -> tuple[Conflict, ...]:
    by_date: dict[date, list[Bar]] = {}
    for bar in bars:
        by_date.setdefault(bar.session_date, []).append(bar)
    return tuple(Conflict(day, tuple(b.envelope.provider_id for b in rows), tuple(b.close for b in rows))
                 for day, rows in sorted(by_date.items()) if len({b.envelope.provider_id for b in rows}) > 1
                 and max(b.close for b in rows) - min(b.close for b in rows) > tolerance)


def freshness(*, latest: Bar | None, as_of: datetime, calendar: SessionCalendar | None,
              grace: timedelta = timedelta(hours=4), provider_error: bool = False) -> str:
    as_of = utc(as_of)
    if provider_error:
        return "provider_outage"
    if latest is None:
        return "no_data"
    if calendar is not None and calendar.venue.session_kind == "regular":
        today = calendar.date_at(as_of)
        try:
            session = calendar.session(today)
        except CalendarMissing:
            return "calendar_unknown"
        if session.status == "holiday" or as_of < session.open_at:
            return "market_closed"
        if as_of <= session.close_at + grace:
            return "session_in_progress"
    if latest.end_at + timedelta(days=2) < as_of:
        return "stale"
    return "current"
