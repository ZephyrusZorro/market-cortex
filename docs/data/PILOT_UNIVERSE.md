# Pilot Universe — Phase 0.6 candidate register

**Status: NOT FROZEN.** No owner-machine provider/account probes have succeeded. `PENDING` is an intentional empty value; no canonical UUID, native ID or history date is invented. Assign opaque IDs only after venue/product resolution. This validates architecture, not permanent coverage. [Source selection](SOURCE_MATRIX.md), [probe guide](../operations/PROBE_RUNBOOK.md).

| Candidate | Class | Proposed venue | Currency / quote | Primary candidate | Canonical ID | Native ID | History start | Data type | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| RELIANCE | Equity | NSE cash EQ | INR | Upstox | PENDING | PENDING | PENDING | daily OHLCV | PROVISIONAL |
| HDFCBANK | Equity | NSE cash EQ | INR | Upstox | PENDING | PENDING | PENDING | daily OHLCV | PROVISIONAL |
| ICICIBANK | Equity | NSE cash EQ | INR | Upstox | PENDING | PENDING | PENDING | daily OHLCV | PROVISIONAL |
| INFY | Equity | NSE cash EQ | INR | Upstox | PENDING | PENDING | PENDING | daily OHLCV | PROVISIONAL |
| TCS | Equity | NSE cash EQ | INR | Upstox | PENDING | PENDING | PENDING | daily OHLCV | PROVISIONAL |
| SBIN | Equity | NSE cash EQ | INR | Upstox | PENDING | PENDING | PENDING | daily OHLCV | PROVISIONAL |
| BHARTIARTL | Equity | NSE cash EQ | INR | Upstox | PENDING | PENDING | PENDING | daily OHLCV | PROVISIONAL |
| LT | Equity | NSE cash EQ | INR | Upstox | PENDING | PENDING | PENDING | daily OHLCV | PROVISIONAL |
| M&M | Equity | NSE cash EQ | INR | Upstox | PENDING | PENDING | PENDING | daily OHLCV | PROVISIONAL |
| ITC | Equity | NSE cash EQ | INR | Upstox | PENDING | PENDING | PENDING | daily OHLCV | PROVISIONAL |
| NVDA | Equity | US listing, verify exchange | USD | Alpaca IEX | PENDING | PENDING | PENDING | daily OHLCV | PROVISIONAL |
| AAPL | Equity | US listing, verify exchange | USD | Alpaca IEX | PENDING | PENDING | PENDING | daily OHLCV | PROVISIONAL |
| MSFT | Equity | US listing, verify exchange | USD | Alpaca IEX | PENDING | PENDING | PENDING | daily OHLCV | PROVISIONAL |
| AMZN | Equity | US listing, verify exchange | USD | Alpaca IEX | PENDING | PENDING | PENDING | daily OHLCV | PROVISIONAL |
| META | Equity | US listing, verify exchange | USD | Alpaca IEX | PENDING | PENDING | PENDING | daily OHLCV | PROVISIONAL |
| GOOGL | Equity | US listing, verify exchange | USD | Alpaca IEX | PENDING | PENDING | PENDING | daily OHLCV | PROVISIONAL |
| TSLA | Equity | US listing, verify exchange | USD | Alpaca IEX | PENDING | PENDING | PENDING | daily OHLCV | PROVISIONAL |
| AMD | Equity | US listing, verify exchange | USD | Alpaca IEX | PENDING | PENDING | PENDING | daily OHLCV | PROVISIONAL |
| SPY | ETF | US listing, verify exchange | USD | Alpaca IEX | PENDING | PENDING | PENDING | daily OHLCV | PROVISIONAL |
| QQQ | ETF | US listing, verify exchange | USD | Alpaca IEX | PENDING | PENDING | PENDING | daily OHLCV | PROVISIONAL |
| BTCUSDT | Crypto spot pair | Binance Spot | USDT | Binance | PENDING | PENDING | PENDING | daily OHLCV, UTC | PROVISIONAL |
| ETHUSDT | Crypto spot pair | Binance Spot | USDT | Binance | PENDING | PENDING | PENDING | daily OHLCV, UTC | PROVISIONAL |
| SOLUSDT | Crypto spot pair | Binance Spot | USDT | Binance | PENDING | PENDING | PENDING | daily OHLCV, UTC | PROVISIONAL |
| BNBUSDT | Crypto spot pair | Binance Spot | USDT | Binance | PENDING | PENDING | PENDING | daily OHLCV, UTC | PROVISIONAL |
| XRPUSDT | Crypto spot pair | Binance Spot | USDT | Binance | PENDING | PENDING | PENDING | daily OHLCV, UTC | PROVISIONAL |

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

On a successful probe, replace `PENDING` with stable UUID, native ID, venue, first observed history, data source and **SUPPORTED** status; proxy becomes **SUPPORTED VIA LABELED PROXY** only after its feed passes. A failed or unavailable candidate becomes **DEFERRED**. `M&M` must match the provider symbol literally. BTCUSDT and BTC-USD remain distinct venue-specific instruments. Avoid hard-coded count or ticker assumptions in contracts.
