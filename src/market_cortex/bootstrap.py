"""Public Binance instrument discovery with provider-native mapping provenance."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from uuid import uuid4

from .contracts import IdentifierMapping, Instrument, Venue
from .providers import ProviderFailure, ReadTransport
from .storage import PostgresCatalog

DEFAULT_CRYPTO_CANDIDATES = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT")


def discover_crypto(catalog: PostgresCatalog, symbols: list[str] | tuple[str, ...],
                    transport: ReadTransport | None = None) -> list[dict]:
    transport = transport or ReadTransport()
    if not symbols or len(symbols) > 50 or len(symbols) != len(set(symbols)):
        raise ValueError("provide 1-50 distinct symbols")
    now = datetime.now(timezone.utc)
    instruments, mappings = catalog.load_identity()
    results = []
    venue = Venue(venue_id="BINANCE_SPOT", timezone="UTC", session_kind="24x7")
    for symbol in symbols:
        if not re.fullmatch(r"[A-Z0-9]{3,20}", symbol):
            raise ValueError("invalid Binance symbol")
        existing = [m for m in mappings if m.provider_id == "binance" and m.venue_id == venue.venue_id
                    and m.identifier_type == "exchange_pair" and m.identifier_value == symbol and
                    m.valid_to is None]
        if existing:
            if len({m.instrument_id for m in existing}) != 1:
                raise ProviderFailure("AMBIGUOUS_EXISTING_IDENTITY")
            results.append({"symbol": symbol, "instrument_id": str(existing[0].instrument_id), "status": "existing"})
            continue
        info = transport.get("data-api.binance.vision", "/api/v3/exchangeInfo", params={"symbol": symbol})
        rows = info.data.get("symbols") if isinstance(info.data, dict) else None
        if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
            raise ProviderFailure("MALFORMED_EXCHANGE_INFO")
        asset = rows[0]
        if asset.get("symbol") != symbol or asset.get("status") != "TRADING":
            raise ProviderFailure("SYMBOL_NOT_TRADING")
        base, quote = asset.get("baseAsset"), asset.get("quoteAsset")
        if not isinstance(base, str) or not isinstance(quote, str) or not re.fullmatch(r"[A-Z0-9]{2,20}", base) or not re.fullmatch(r"[A-Z0-9]{2,20}", quote):
            raise ProviderFailure("MALFORMED_EXCHANGE_INFO")
        first = transport.get("data-api.binance.vision", "/api/v3/klines",
                              params={"symbol": symbol, "interval": "1d", "startTime": 0, "limit": 1})
        if not isinstance(first.data, list) or not first.data or not isinstance(first.data[0], list) or not isinstance(first.data[0][0], int):
            raise ProviderFailure("FIRST_CANDLE_UNAVAILABLE")
        valid_from = datetime.fromtimestamp(first.data[0][0] / 1000, timezone.utc)
        instrument = Instrument(instrument_id=uuid4(), asset_class="crypto_spot", instrument_kind="spot_pair",
                                primary_venue_id=venue.venue_id, trading_currency=quote,
                                price_unit="quote_currency", quantity_unit=base, listing_status="active",
                                valid_from=valid_from)
        mapping = IdentifierMapping(mapping_id=uuid4(), instrument_id=instrument.instrument_id,
                                    provider_id="binance", venue_id=venue.venue_id,
                                    identifier_type="exchange_pair", identifier_value=symbol,
                                    valid_from=valid_from, available_at=now, confidence=1)
        catalog.register_identity([venue], [instrument], [mapping])
        results.append({"symbol": symbol, "instrument_id": str(instrument.instrument_id),
                        "status": "registered", "earliest_sampled_session_utc": valid_from.isoformat(),
                        "exchange_info_sha256": info.content_hash, "first_candle_sha256": first.content_hash,
                        "coverage_verified": False})
    return results
