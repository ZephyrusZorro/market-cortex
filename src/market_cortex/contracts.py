"""Typed Phase 1 market contracts, aligned with packages/contracts/registry.schema.json.

Opaque provider identities are scoped to provider and venue. UTC instants and
half-open bar windows are mandatory. Data quality is evaluated separately so a
bad source candle can be quarantined with its validation codes.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SCHEMA_VERSION = "1.0.0-draft"
UTC = timezone.utc


def utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must include an offset")
    return value.astimezone(UTC)


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)
    schema_version: Literal["1.0.0-draft"] = SCHEMA_VERSION


class Instrument(Contract):
    instrument_id: UUID
    asset_class: Literal["equity", "etf", "index", "crypto_spot", "future", "option", "perpetual", "fx", "commodity", "rate_series", "other"]
    instrument_kind: str
    primary_venue_id: str
    trading_currency: str
    price_unit: str
    quantity_unit: str
    listing_status: Literal["active", "halted", "delisted", "expired", "unknown"]
    valid_from: datetime
    valid_to: datetime | None = None
    underlying_instrument_id: UUID | None = None
    issuer_id: str | None = None

    @field_validator("valid_from", "valid_to")
    @classmethod
    def timestamps(cls, value: datetime | None) -> datetime | None:
        return utc(value) if value is not None else None


class IdentifierMapping(Contract):
    mapping_id: UUID
    instrument_id: UUID
    provider_id: str
    venue_id: str
    identifier_type: Literal["ticker", "isin", "cusip", "figi", "provider_token", "exchange_pair", "contract_code", "series_code", "other"]
    identifier_value: str
    valid_from: datetime
    valid_to: datetime | None = None
    available_at: datetime | None = None
    confidence: float = 1.0
    source_batch_id: UUID | None = None

    @field_validator("valid_from", "valid_to", "available_at")
    @classmethod
    def timestamps(cls, value: datetime | None) -> datetime | None:
        return utc(value) if value is not None else None

    @model_validator(mode="after")
    def interval(self) -> "IdentifierMapping":
        if self.valid_to is not None and self.valid_to <= self.valid_from:
            raise ValueError("mapping valid_to must follow valid_from")
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence outside [0,1]")
        return self


class Venue(Contract):
    venue_id: str
    timezone: str
    session_kind: Literal["regular", "24x7"]

    @field_validator("timezone")
    @classmethod
    def zone(cls, value: str) -> str:
        from zoneinfo import ZoneInfo
        ZoneInfo(value)
        return value


class CalendarSession(Contract):
    calendar_id: str
    venue_id: str
    session_date: date
    open_at: datetime
    close_at: datetime
    status: Literal["open", "early_close", "holiday"]
    version: str

    @field_validator("open_at", "close_at")
    @classmethod
    def timestamps(cls, value: datetime) -> datetime:
        return utc(value)

    @model_validator(mode="after")
    def interval(self) -> "CalendarSession":
        if self.status != "holiday" and self.close_at <= self.open_at:
            raise ValueError("session close must follow open")
        return self


class ObservationEnvelope(Contract):
    observation_id: UUID
    instrument_id: UUID | None = None
    series_id: str | None = None
    venue_id: str
    provider_id: str
    provider_record_id: str | None = None
    event_at: datetime
    published_at: datetime | None = None
    available_at: datetime | None = None
    availability_basis: Literal["observed_arrival", "documented_publication", "conservative_proxy", "unknown"]
    ingested_at: datetime
    timestamp_precision: str
    is_final: bool
    quality_state: Literal["valid", "suspect", "quarantined", "corrected"]
    freshness_policy_id: str
    validation_codes: list[str]
    source_ref: str
    source_batch_id: UUID
    raw_content_hash: str
    raw_retention_state: Literal["retained", "hash_only", "prohibited", "expired"]
    normalizer_version: str
    license_policy_id: str
    unit: str
    adjustment_basis: str
    supersedes_observation_id: UUID | None = None
    missing_reason: str | None = None
    currency: str | None = None
    # Provider vintage, if supplied. Catalog correction sequence is separate.
    revision: str | None = None

    @field_validator("event_at", "published_at", "available_at", "ingested_at")
    @classmethod
    def timestamps(cls, value: datetime | None) -> datetime | None:
        return utc(value) if value is not None else None

    @model_validator(mode="after")
    def identity_and_availability(self) -> "ObservationEnvelope":
        if (self.instrument_id is None) == (self.series_id is None):
            raise ValueError("exactly one of instrument_id and series_id required")
        if self.availability_basis == "unknown" and self.available_at is not None:
            raise ValueError("unknown availability cannot have a timestamp")
        if self.availability_basis != "unknown" and self.available_at is None:
            raise ValueError("known availability requires timestamp")
        if self.available_at is not None and self.available_at > self.ingested_at and self.availability_basis == "observed_arrival":
            raise ValueError("observed arrival cannot follow ingestion")
        return self


DecimalString = Annotated[Decimal, Field(allow_inf_nan=False)]


class Bar(Contract):
    envelope: ObservationEnvelope
    interval: str
    start_at: datetime
    end_at: datetime
    session_date: date
    calendar_id: str
    open: DecimalString
    high: DecimalString
    low: DecimalString
    close: DecimalString
    volume: DecimalString | None = None
    trade_count: int | None = None
    aggregation_method: str
    quote_currency: str
    volume_unit: str

    @field_validator("start_at", "end_at")
    @classmethod
    def timestamps(cls, value: datetime) -> datetime:
        return utc(value)

    @model_validator(mode="after")
    def window(self) -> "Bar":
        if self.start_at >= self.end_at:
            raise ValueError("bar window must be half-open and nonempty")
        if self.envelope.event_at != self.end_at:
            raise ValueError("event_at must be bar end_at")
        if self.trade_count is not None and self.trade_count < 0:
            raise ValueError("negative trade count")
        return self


def contract_json(model: Contract) -> dict:
    """Serialize with UTC Z, decimal strings, and UUID strings for registry validation."""
    import json
    return json.loads(model.model_dump_json(exclude_none=True))


def validate_registry(model: Contract, registry_path: Path) -> None:
    import json
    from jsonschema import Draft202012Validator, FormatChecker
    document = json.loads(registry_path.read_text(encoding="utf-8"))
    schema = {"$schema": document["$schema"], "$defs": document["$defs"], "$ref": f"#/$defs/{type(model).__name__}"}
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(contract_json(model))
