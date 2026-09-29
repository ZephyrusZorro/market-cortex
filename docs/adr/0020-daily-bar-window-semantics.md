# ADR 0020 — Provider daily aggregation windows

## Context

The Phase 0 baseline requires a UTC half-open bar interval and a separate venue-local `session_date`. [Alpaca's Market Data FAQ](https://docs.alpaca.markets/us/docs/market-data-faq) documents its daily aggregate timestamp as the left edge of a New York calendar day. A venue's regular trading hours therefore cannot automatically be substituted for a provider's daily aggregation window.

## Decision

Record daily window semantics per provider feed. The Alpaca adapter uses `[New York local midnight, next local midnight)` and stores its named IEX/SIP feed; the Binance adapter uses the UTC daily window. Upstox currently uses the registered session boundaries with `provider_unspecified` adjustment and remains account-validation gated. Calendar sessions still determine holidays and early closes. A future verified source can use its own explicit boundary policy without changing `Bar` or `ObservationEnvelope`.

## Alternatives

Force all daily bars to regular session hours; or force all to UTC midnight. Both lose source aggregation meaning.

## Consequences

Alpaca daily intervals can span 23/25 UTC hours at daylight-saving transitions. Completion is conservative until the interval ends. Raw and adjusted values remain separate. Live provider samples must verify the remaining Upstox assumption.

## Reconsideration triggers

Provider documentation or account samples show a different aggregation window; a provider separates regular/extended aggregates; a feed requires explicit publication time for same-day decisions.
