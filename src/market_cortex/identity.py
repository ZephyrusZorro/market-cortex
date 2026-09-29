"""Venue-scoped, valid-time identity resolution without symbol guessing."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from .contracts import IdentifierMapping, Instrument, utc


class IdentityError(ValueError):
    code = "IDENTITY_ERROR"


class AmbiguousIdentity(IdentityError):
    code = "AMBIGUOUS_IDENTITY"


class UnknownIdentity(IdentityError):
    code = "UNKNOWN_IDENTITY"


class IdentityRegistry:
    def __init__(self, instruments: list[Instrument] | tuple[Instrument, ...], mappings: list[IdentifierMapping] | tuple[IdentifierMapping, ...]):
        self.instruments = {i.instrument_id: i for i in instruments}
        self.mappings = tuple(mappings)

    def resolve(self, *, provider_id: str, identifier_type: str, identifier_value: str,
                at: datetime, venue_id: str | None = None, known_at: datetime | None = None) -> Instrument:
        at = utc(at)
        cutoff = utc(known_at) if known_at else None
        matches = []
        for mapping in self.mappings:
            if (mapping.provider_id, mapping.identifier_type, mapping.identifier_value) != (provider_id, identifier_type, identifier_value):
                continue
            if venue_id is not None and mapping.venue_id != venue_id:
                continue
            if at < mapping.valid_from or mapping.valid_to is not None and at >= mapping.valid_to:
                continue
            if cutoff is not None and (mapping.available_at is None or mapping.available_at > cutoff):
                continue
            instrument = self.instruments.get(mapping.instrument_id)
            if instrument is None or instrument.primary_venue_id != mapping.venue_id:
                continue
            if at < instrument.valid_from or instrument.valid_to is not None and at >= instrument.valid_to:
                continue
            matches.append(instrument)
        ids: set[UUID] = {item.instrument_id for item in matches}
        if not ids:
            raise UnknownIdentity("no matching instrument at the specified time")
        if len(ids) != 1:
            raise AmbiguousIdentity("multiple venue-scoped instruments match")
        return matches[0]

    def mapping_for(self, instrument_id: UUID, provider_id: str, identifier_type: str, at: datetime) -> IdentifierMapping:
        at = utc(at)
        matches = [m for m in self.mappings if m.instrument_id == instrument_id and m.provider_id == provider_id
                   and m.identifier_type == identifier_type and m.valid_from <= at
                   and (m.valid_to is None or at < m.valid_to)]
        if not matches:
            raise UnknownIdentity("no provider mapping at the specified time")
        if len({m.identifier_value for m in matches}) > 1:
            raise AmbiguousIdentity("multiple native identifiers at the specified time")
        current = matches[0]
        if any(m.instrument_id != instrument_id and m.provider_id == provider_id
               and m.venue_id == current.venue_id and m.identifier_type == identifier_type
               and m.identifier_value == current.identifier_value and m.valid_from <= at
               and (m.valid_to is None or at < m.valid_to) for m in self.mappings):
            raise AmbiguousIdentity("native identifier overlaps another listing")
        return matches[0]
