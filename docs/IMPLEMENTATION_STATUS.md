# Seven-feature completion status

## Implemented and locally testable

- Immutable datasets and migration of legacy replay sessions; preservation on partial provider failures.
- PostgreSQL observations with user isolation; owned provider credentials encrypted at rest.
- Broader real market dataset catalog, sector summaries, comparisons, intraday-capable charts and currency-aware price display.
- CSV preview/mapping/commit, imported trade history, FIFO fees, separate currencies, duplicate protection and reconciliation.
- Broker authorization and read adapters; explicit missing-connection states for actual options data.
- Durable notification queue, code-based recipient verification, uncertain delivery handling, provider transports and signed receipts.
- Fifty-three three-fold measured experiments with lagged market context, saved run history, scheduled refresh, saved-weight inference on new bars, and later prediction outcome tracking.
- Thirteen lessons, glossary, lesson bookmarks, practice links, persistent quizzes, and replay cost settings.
- Extension source and compiled package; short-lived API pairing and server-side revocation.
- Account email verification and recovery; one-use hashed tokens and session revocation.
- Encrypted backup and isolated PostgreSQL restore verification.

## Still requires actual external access or manual acceptance

- Real Zerodha/Upstox accounts for authorization, source record reconciliation and actual options quotes.
- Verified Telegram/SMTP/WhatsApp recipients for real delivery and receipt acceptance.
- Account SMTP configuration to verify actual recovery email receipt.
- Chrome/Edge manual interaction check, visual acceptance and store-owner publication.
- A working image-build path and hosted HTTPS deployment. Kirat confirmed successful authentication of the `investors-eye` AWS profile; hosted deployment has not been completed.

## Deliberately not represented as complete

- Exchange-specific derivative settlement/margin simulation, corporate-action automation and short-selling support.
- Independently verified licensed fundamentals or a full instrument universe.
- Guaranteed profitable forecasting: current cross-fold results remain experimental.
- Firefox compatibility or extension store approval.

The original vision has substantially more implementation behind it now, but full acceptance of all seven features still depends on the items above. This document is the explicit boundary, not a substitute for those acceptance gates.

### Shared live investor path (14 November 2026)

- Provider-qualified instrument identities now connect live search, quotes, completed candles, technical analysis, saved watchlists, crossing alerts and alert events.
- Live analysis returns the provider candle set, freshness, source, indicators and an explicit unavailable fundamentals state. Forecast evidence is returned only when a saved report matches the instrument's dataset hash.
- Live alerts evaluate only fresh observations with increasing provider timestamps. A feed gap re-baselines the alert instead of claiming a crossing during the outage. Events still enter the durable notification queue.
- The extension now targets `https://investoreye.harkiratsingh.tech`, searches the shared live instrument API, opens shared research, and saves account-owned live watchlists.
- Public crypto live search, quote, candle, analysis and saved forecast checks passed for dynamically discovered BTCUSDT. The hosted Kite tests passed for configuration gating, callback single-use, encrypted user tokens and account isolation.
- The temporary release is still not deployed. Public Indian market display rights, approved multi-user Kite access, the final DNS record and hosting credentials remain external release gates.

### Market workbench feature batch (14 November 2026)

Implemented in the active application:
- Explore: searchable, segment-filtered and sortable observed-price screener; sample sector movement tiles with observation/source provenance.
- Asset comparison: two to four instruments, common-date normalized charts, returns, maximum drawdown, annualized volatility and return correlations. No currency conversion is implied.
- Account-owned named watchlists: create, add/remove symbols, reorder and delete.
- Research chart: candlestick/line views, history ranges, 20-bar simple/exponential averages and Bollinger bands; account-owned saved layouts with restore/delete.
- Fund explorer: observed return cards, drawdown, annualized volatility, zero-risk-free-rate Sharpe, annual growth where history permits, and date-aligned Nifty beta.
- Options: snapshot max-pain calculation and largest open-interest strikes, with provider model-derived delta/implied-volatility columns. Real account verification still requires an eligible Upstox connection.

Verification for this batch: frontend production build and live comparison request (RELIANCE/TCS, 63 common observations through 2026-11-13). Broad regression tests deferred at Kirat's request. Visual and interaction acceptance remains a manual walkthrough under the CLI-only rule.


### Segment analysis and import workflow batch (14 November 2026)

- Crypto board: recorded 24-hour/seven-day/30-day returns when the source window is continuous, 24-hour base-asset volume and range, drawdown, daily volatility and date-matched Bitcoin return correlation. Unsupported market-cap, funding and on-chain figures remain explicitly unavailable.
- Fund rolling-return chart: 21/63/252/756 published-observation windows, worst/median/best return and fraction of positive windows. These are overlapping cumulative returns, not independent forecasts.
- Trade imports: private saved source/column mappings with apply/delete. Applying a mapping or changing the upload invalidates the previous preview; each file must be previewed again.
- Options: adjustable strike window, shared-scale call/put open-interest bars and changes from provider previous OI. External broker acceptance remains pending.
- Learning: segment and level selectors plus a bookmarks-only filter.

The frontend production build passed. Live HTTP requests returned recorded ETHUSDT analysis and 1,248 rolling 252-observation windows for MF120503. Broad regression and manual visual acceptance remain deferred.

### Live investing workspace (14 November 2026)

The default page is now `/live`, backed by provider discovery rather than the bundled dataset manifest.

- Binance exchangeInfo supplied 1,372 active spot instruments; the current ticker supplied 1,370 valid positive-price quotes during the real provider check. These counts are observations, not configured limits.
- A real connection to the public mini-ticker stream received 46 changed-symbol events in the checked message. The worker shares this stream across users and saves changed snapshots every five seconds, with reconnection and REST recovery.
- Live search, provider-derived quote currencies, quote-volume ordering, account-owned live watchlists and provider candles support instruments outside the capstone catalog. Only completed chart candles are displayed.
- Freshness is evaluated using provider timestamps and retrieval time. Failed connections retain visibly stale observations; no bundled data is substituted.
- Indian-market search discovers the signed-in user's Kite NSE catalog. Quotes require that user's broker market-data entitlement. This path is implemented but has not been verified with a real broker account: there are no saved broker connections in this installation.
- Broker-reported holdings have their own screen and retain provider cost/price/ISIN fields when supplied. They are not replaced by virtual portfolios or reconstructed CSV records. Real account acceptance remains pending.
- The earlier research/practice screens are explicitly labelled recorded data. They remain available for replay and experiments, not as proof of current-market coverage.

Build and actual public-provider checks passed. This establishes a live public data path, not readiness for unrestricted public financial use or completed Indian broker acceptance.


### Hosted investor product and shared Kite app (14 November 2026)

- Visitors connect through official Zerodha login using one operator-configured approved application. No developer secret is requested in the new visitor flow.
- Returned tokens are encrypted separately per InvestorsEYE account; server app credentials are resolved only inside backend processes.
- Added connection verification, broker-reported holdings and net positions, and completed provider candles with interval controls. Selected quotes refresh every 15 seconds.
- Added a distinct public HTTPS Compose configuration. This prepares hosting; it is not a deployed public URL.
- Two targeted controlled tests passed for unavailable operator configuration, single-use callback state, server-secret exclusion, token encryption and account isolation. Actual broker acceptance remains unverified.
- External requirements: an approved multi-user Kite application, operator secrets, final public domain, and renewed `investors-eye` cloud authentication. The latest CLI identity call reported session expiry. No resources were provisioned.

### Ported from teammate `stocky` branch (15 November 2026)

Selected features from Rishav's `stocky` commit `150634a` were re-implemented in the v2 modules rather than merged, because that commit edits the legacy routes/services stack that v2 no longer mounts.

- Technical analysis: ATR, ADX/+DI/-DI and Stochastic %K/%D (`backend/app/indicators.py`), shown in both live and historical analysis. Verified against an independent pandas calculation.
- NSE reference list: 116 symbols with editorial sector labels, no prices (`backend/app/nse_reference.py`). Tags Kite catalog search results, adds a sector filter and `/v1/reference/nse`.
- Learning: eight quiz items turned into lessons (three corrected for accuracy) and a "Further learning" page of external resources. Unverified ratings, durations and lesson counts were dropped.
- Deliberately not ported: synthetic fallback prices, randomized options chains and the hardcoded JWT secret.
