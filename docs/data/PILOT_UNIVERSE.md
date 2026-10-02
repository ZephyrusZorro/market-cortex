# Pilot Universe — Phase 0.6 candidate register

**Status: Binance live Phase 1 pilot supported; India/US candidates `DEFERRED_NOT_CONFIGURED`.** A bounded public Binance probe and seven-day isolated ingestion succeeded on 2026-10-03; see the [exit evidence](../planning/PHASE_1_EXIT_MATRIX_2026-10-03.md). Upstox and Alpaca remain untested without owner credentials. `PENDING` remains intentional for permanent canonical IDs: UUIDs created in the disposable pilot database are not IDs in the owner's main catalog. Sampled first candles do not prove complete historical coverage. [Source selection](SOURCE_MATRIX.md), [probe guide](../operations/PROBE_RUNBOOK.md).

| Candidate | Class | Proposed venue | Currency / quote | Primary candidate | Canonical ID | Native ID | History start | Data type | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| RELIANCE | Equity | NSE cash EQ | INR | Upstox | PENDING | PENDING | PENDING | daily OHLCV | DEFERRED_NOT_CONFIGURED |
| HDFCBANK | Equity | NSE cash EQ | INR | Upstox | PENDING | PENDING | PENDING | daily OHLCV | DEFERRED_NOT_CONFIGURED |
| ICICIBANK | Equity | NSE cash EQ | INR | Upstox | PENDING | PENDING | PENDING | daily OHLCV | DEFERRED_NOT_CONFIGURED |
| INFY | Equity | NSE cash EQ | INR | Upstox | PENDING | PENDING | PENDING | daily OHLCV | DEFERRED_NOT_CONFIGURED |
| TCS | Equity | NSE cash EQ | INR | Upstox | PENDING | PENDING | PENDING | daily OHLCV | DEFERRED_NOT_CONFIGURED |
| SBIN | Equity | NSE cash EQ | INR | Upstox | PENDING | PENDING | PENDING | daily OHLCV | DEFERRED_NOT_CONFIGURED |
| BHARTIARTL | Equity | NSE cash EQ | INR | Upstox | PENDING | PENDING | PENDING | daily OHLCV | DEFERRED_NOT_CONFIGURED |
| LT | Equity | NSE cash EQ | INR | Upstox | PENDING | PENDING | PENDING | daily OHLCV | DEFERRED_NOT_CONFIGURED |
| M&M | Equity | NSE cash EQ | INR | Upstox | PENDING | PENDING | PENDING | daily OHLCV | DEFERRED_NOT_CONFIGURED |
| ITC | Equity | NSE cash EQ | INR | Upstox | PENDING | PENDING | PENDING | daily OHLCV | DEFERRED_NOT_CONFIGURED |
| NVDA | Equity | US listing, verify exchange | USD | Alpaca IEX | PENDING | PENDING | PENDING | daily OHLCV | DEFERRED_NOT_CONFIGURED |
| AAPL | Equity | US listing, verify exchange | USD | Alpaca IEX | PENDING | PENDING | PENDING | daily OHLCV | DEFERRED_NOT_CONFIGURED |
| MSFT | Equity | US listing, verify exchange | USD | Alpaca IEX | PENDING | PENDING | PENDING | daily OHLCV | DEFERRED_NOT_CONFIGURED |
| AMZN | Equity | US listing, verify exchange | USD | Alpaca IEX | PENDING | PENDING | PENDING | daily OHLCV | DEFERRED_NOT_CONFIGURED |
| META | Equity | US listing, verify exchange | USD | Alpaca IEX | PENDING | PENDING | PENDING | daily OHLCV | DEFERRED_NOT_CONFIGURED |
| GOOGL | Equity | US listing, verify exchange | USD | Alpaca IEX | PENDING | PENDING | PENDING | daily OHLCV | DEFERRED_NOT_CONFIGURED |
| TSLA | Equity | US listing, verify exchange | USD | Alpaca IEX | PENDING | PENDING | PENDING | daily OHLCV | DEFERRED_NOT_CONFIGURED |
| AMD | Equity | US listing, verify exchange | USD | Alpaca IEX | PENDING | PENDING | PENDING | daily OHLCV | DEFERRED_NOT_CONFIGURED |
| SPY | ETF | US listing, verify exchange | USD | Alpaca IEX | PENDING | PENDING | PENDING | daily OHLCV | DEFERRED_NOT_CONFIGURED |
| QQQ | ETF | US listing, verify exchange | USD | Alpaca IEX | PENDING | PENDING | PENDING | daily OHLCV | DEFERRED_NOT_CONFIGURED |
| BTCUSDT | Crypto spot pair | Binance Spot | USDT | Binance | PENDING | BTCUSDT | 2017-08-17 sampled | daily OHLCV, UTC | PUBLIC TESTED; isolated 7-day pilot |
| ETHUSDT | Crypto spot pair | Binance Spot | USDT | Binance | PENDING | ETHUSDT | 2017-08-17 sampled | daily OHLCV, UTC | PUBLIC TESTED; isolated 7-day pilot |
| SOLUSDT | Crypto spot pair | Binance Spot | USDT | Binance | PENDING | SOLUSDT | 2020-08-11 sampled | daily OHLCV, UTC | PUBLIC TESTED; isolated 7-day pilot |
| BNBUSDT | Crypto spot pair | Binance Spot | USDT | Binance | PENDING | BNBUSDT | 2017-11-06 sampled | daily OHLCV, UTC | PUBLIC TESTED; isolated 7-day pilot |
| XRPUSDT | Crypto spot pair | Binance Spot | USDT | Binance | PENDING | XRPUSDT | 2018-05-04 sampled | daily OHLCV, UTC | PUBLIC TESTED; isolated 7-day pilot |

## Context candidates

| Desired context | Proposed exact source or proxy | Classification today | Gate |
| --- | --- | --- | --- |
| NIFTY 50 | Upstox NSE_INDEX / NSE Indices | DEFERRED | Resolve native key and daily history on owner account. |
| S&P 500 | SPY US equity proxy if official index unavailable | DEFERRED | Label **SPY ETF proxy**, not SPX; account probe. |
| NASDAQ-100 | QQQ ETF proxy if official NDX unavailable | DEFERRED | Label **QQQ ETF proxy**, not NDX; account probe. |
| VIX | Cboe daily published close | DEFERRED | Verify permitted local download and date/time semantics. |
| DXY | No robust selected source | DEFERRED | Decide benchmark feed or explicit alternate context. |
| US 10Y Treasury yield | US Treasury daily par yield | DEFERRED | Probe feed and publication time; rate is not OHLC. |
| Gold | GLD ETF proxy candidate | DEFERRED | Label proxy and verify US provider coverage. |
| Crude oil | No benchmark selected; USO ETF proxy possible | DEFERRED | Oil futures/spot/ETF differ; choose explicitly after probe. |
| USD/INR | RBI reference rate candidate | DEFERRED | Verify archive access and fix/publication semantics. |

On a successful authenticated equity probe, replace `PENDING` with stable UUID, native ID, venue, first observed history, data source and **SUPPORTED** status; proxy becomes **SUPPORTED VIA LABELED PROXY** only after its feed passes. A failed or unavailable candidate remains **DEFERRED**. `M&M` must match the provider symbol literally. BTCUSDT and BTC-USD remain distinct venue-specific instruments. Avoid hard-coded count or ticker assumptions in contracts.
