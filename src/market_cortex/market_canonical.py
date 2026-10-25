"""Explicit bridge from discovery evidence to the existing canonical contracts.

This function returns Bars in memory. It cannot bootstrap or persist a catalog.
An approved import must supply verified, time-bounded identity and calendars.
"""
from __future__ import annotations

from uuid import uuid4

from .calendar import CalendarMissing
from .contracts import Bar, ObservationEnvelope
from .market_history import SourceCandle
from .providers import ProviderFailure, build_bar, require_identity


def canonical_bars(samples, instrument, mapping, calendar):
    result, batch = [], uuid4()
    for raw in samples:
        source = SourceCandle.model_validate(raw)
        identifier_type = {'binance':'exchange_pair','upstox':'provider_token','alpaca':'ticker'}[source.provider]
        native = source.symbol if source.provider == 'alpaca' else source.native_id
        if (mapping.identifier_value != native or source.currency != instrument.trading_currency or
            mapping.available_at > source.available_at):
            raise ProviderFailure('VERIFIED_MAPPING_MISMATCH')
        require_identity(source.provider,instrument,mapping,calendar,identifier_type,source.start_at,source.end_at)
        date = calendar.date_at(source.start_at)
        try:
            session = calendar.session(date)
        except CalendarMissing:
            raise ProviderFailure('CALENDAR_UNKNOWN') from None
        if session.status == 'holiday':
            raise ProviderFailure('CANDLE_ON_HOLIDAY')
        if source.interval == 'P1D':
            record_id = f'{native}:{int(source.start_at.timestamp()*1000)}' if source.provider == 'binance' else f'{native}:{date}'
            item = build_bar(instrument=instrument,mapping=mapping,calendar=calendar,provider=source.provider,
                batch_id=batch,fetched_at=source.available_at,source_hash=source.source_hash,
                record_id=record_id,session_date=date,
                open_=source.open,high=source.high,low=source.low,close=source.close,volume=source.volume,
                feed=source.feed,adjustment=source.adjustment_basis,
                window_basis='local_day' if source.provider in {'binance','alpaca'} else 'session')
        else:
            if source.interval not in {'PT1M','PT5M','PT15M','PT1H','PT4H'}:
                raise ProviderFailure('AGGREGATE_CALENDAR_REQUIRES_VERIFICATION')
            if (calendar.venue.session_kind != '24x7' and
                not session.open_at <= source.start_at < source.end_at <= session.close_at):
                raise ProviderFailure('UNVERIFIED_EXTENDED_HOURS_WINDOW')
            envelope = ObservationEnvelope(observation_id=uuid4(),instrument_id=instrument.instrument_id,
                venue_id=mapping.venue_id,provider_id=source.provider,provider_record_id=f'{native}:{source.interval}:{source.start_at.isoformat()}',
                event_at=source.end_at,available_at=source.available_at,availability_basis='observed_arrival',
                ingested_at=source.available_at,timestamp_precision='millisecond',is_final=True,quality_state='valid',
                freshness_policy_id=f'{source.provider}:{source.feed}:{source.interval}',source_ref=f'{source.provider}:history:{batch}',
                source_batch_id=batch,raw_content_hash=source.source_hash,raw_retention_state='hash_only',
                normalizer_version='multi_market_v1',license_policy_id='private_research_pending_terms',
                currency=source.currency,unit=instrument.price_unit,adjustment_basis=source.adjustment_basis)
            item = Bar(envelope=envelope,interval=source.interval,start_at=source.start_at,end_at=source.end_at,
                session_date=date,calendar_id=calendar.calendar_id,open=source.open,high=source.high,low=source.low,
                close=source.close,volume=source.volume,aggregation_method=f'provider_{source.feed}:verified_window',
                quote_currency=source.currency,volume_unit=instrument.quantity_unit)
        result.append(item)
    return result
