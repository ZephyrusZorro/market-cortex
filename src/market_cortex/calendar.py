"""Explicit sessions; holidays and early closes are data, not weekday guesses."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from .contracts import CalendarSession, Venue


class CalendarMissing(ValueError):
    pass


class SessionCalendar:
    def __init__(self, venue: Venue, calendar_id: str, version: str, sessions: list[CalendarSession] = ()):
        self.venue = venue
        self.calendar_id = calendar_id
        self.version = version
        self._sessions = {s.session_date: s for s in sessions}
        if any(s.calendar_id != calendar_id or s.venue_id != venue.venue_id or s.version != version
               for s in sessions):
            raise ValueError("calendar session identity mismatch")

    def session(self, session_date: date) -> CalendarSession:
        if self.venue.session_kind == "24x7":
            start = datetime.combine(session_date, time.min, timezone.utc)
            return CalendarSession(calendar_id=self.calendar_id, venue_id=self.venue.venue_id,
                                   session_date=session_date, open_at=start, close_at=start + timedelta(days=1),
                                   status="open", version=self.version)
        result = self._sessions.get(session_date)
        if result is None:
            raise CalendarMissing(f"calendar session unavailable for {session_date}")
        return result

    def date_at(self, event_at: datetime) -> date:
        if event_at.tzinfo is None:
            raise ValueError("aware timestamp required")
        return event_at.astimezone(ZoneInfo(self.venue.timezone)).date()

    def local_day_window(self, session_date: date) -> tuple[datetime, datetime]:
        """Venue-local midnight boundaries account for 23/25-hour DST days."""
        zone = ZoneInfo(self.venue.timezone)
        first = datetime.combine(session_date, time.min, zone).astimezone(timezone.utc)
        following = datetime.combine(session_date + timedelta(days=1), time.min, zone).astimezone(timezone.utc)
        return first, following

    def expected_dates(self, first: date, last: date) -> list[date]:
        if first > last:
            return []
        days = (last - first).days + 1
        result = []
        for offset in range(days):
            day = first + timedelta(days=offset)
            if self.session(day).status != "holiday":
                result.append(day)
        return result
