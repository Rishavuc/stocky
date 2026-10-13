# Stock & Investing Assistant – Development Plan

Oct 13, 2026 · @Ak

A phased build of an India-focused investing assistant: five market views, analysis, LSTM prediction and learning dashboards, a browser extension, a unified cross-broker trade book and alert bots.

## Scope

The seven features ship over about 24 weeks in five phases (0–4). Market view comes first because every other dashboard reads its data. Version 1 is read-only: no order placement, so broker and SEBI exposure stays low.

| # | Feature | What it delivers | Phase |
| --- | --- | --- | --- |
| 1 | Market view | Quotes, watchlists, heatmaps and charts for Indian stocks, F&O chains, intraday, mutual funds and crypto | 1 |
| 2 | Analysis dashboard | Technical and fundamental indicators, option-chain analytics, fund comparison, crypto metrics | 2 |
| 3 | Prediction dashboard | LSTM forecasts per instrument with a confidence band and a backtest | 3 |
| 4 | Learning dashboard | Lessons, glossary, quizzes and paper trading per segment | 3 |
| 5 | Browser extension | Side panel and overlays on broker and news sites | 4 |
| 6 | Unified trade view | Read-only import of trades and holdings from several brokers and exchanges | 2 |
| 7 | Alert bots | Price, indicator, open-interest, NAV and portfolio rules delivered by Telegram, WhatsApp and email | 2 |

## Architecture

&#91;embedded content: system architecture · clients, one API, 6 backend modules, 3 data stores\]

The web app and the extension share one API; only `market-ingest` talks to data providers, and every other module reads from Redis and TimescaleDB.

## Tech stack

One TypeScript monorepo for the web app and extension, and one Python backend so the API and the LSTM models share a language.

| Layer | Choice | Why |
| --- | --- | --- |
| Web framework | Next.js (React, TypeScript) | Server rendering for public learning pages, client rendering for live dashboards |
| UI kit | Tailwind CSS, shadcn/ui | Fast, consistent, accessible components |
| Candlestick charts | TradingView Lightweight Charts | Built for financial time series, handles intraday density |
| Other charts | Apache ECharts | Heatmaps, option-chain OI bars, allocation and forecast bands |
| Client data | TanStack Query, Zustand, native WebSocket | Cached REST plus a live tick stream, small UI state |
| Extension | WXT or Plasmo, Manifest V3 | Reuses the web app's React packages from the monorepo |
| Monorepo | pnpm, Turborepo | Shared `ui`, `api-client` and `types` packages |
| API | FastAPI (Python 3.12) | Async, typed, auto-generated OpenAPI, same language as ML |
| Real-time | FastAPI WebSocket gateway over Redis Pub/Sub | Fans one ingest stream out to many browsers |
| Jobs | Celery, Redis, Celery beat | Alert evaluation, NAV refresh, EOD loads, retraining |
| Primary DB | PostgreSQL 16 | Users, portfolios, trades, alerts, lessons |
| Time series | TimescaleDB extension | Ticks and candles with compression and continuous aggregates |
| Cache and queues | Redis | Latest quotes, rate limits, pub/sub, job broker |
| ML | PyTorch, pandas, pandas-ta, MLflow | LSTM training, indicator features, model registry |
| Bots | python-telegram-bot, WhatsApp Business Cloud API, Amazon SES | One notifier service, three channels |
| Auth | OAuth login plus JWT sessions; broker tokens encrypted with a KMS-held key | Keeps broker credentials out of the database in plain form |
| Infra | Docker, Terraform, GitHub Actions, AWS Mumbai region | Low latency to Indian users, repeatable deploys |
| Observability | Prometheus, Grafana, Sentry | Feed lag, job failures and model drift in one place |
| Testing | Vitest, Playwright, pytest | Unit, end-to-end and backtest regression tests |

## Data sources

In version 1, take live prices through each user's own broker API session and use public end-of-day files for history, so the app does not redistribute exchange data. Provider terms and prices change often; the options below come from memory, not from pages opened for this plan, so verify each before committing.

| Segment | Candidate sources | Notes |
| --- | --- | --- |
| Indian stocks | Broker APIs (Zerodha Kite Connect, Upstox, Angel One SmartAPI, Dhan, Fyers); NSE and BSE end-of-day bhavcopy files | Live streaming needs the user's broker login; bhavcopy fills history |
| Intraday | Same broker WebSockets; 1-minute candles built and stored by the app | Store raw ticks briefly, keep 1m and 5m candles long term |
| F&O | Broker instrument master and option-chain endpoints | Reload the instrument master daily: lot sizes, strikes and expiries change |
| Mutual funds | AMFI daily NAV file; community NAV APIs such as MFapi.in; CAMS and KFintech consolidated statements for holdings | NAV is end-of-day only; holdings import is a user-uploaded statement |
| Crypto | CoinGecko API for reference data; Binance and CoinDCX public WebSockets for live prices | Quote in INR and USDT; mind per-key rate limits |
| Fundamentals and news | A licensed fundamentals vendor, exchange filings, RSS from news publishers | Scraping retail sites risks terms-of-service breaches |

Build a provider adapter interface (`get_quote`, `stream_ticks`, `get_history`, `get_instruments`) so a source can be swapped without touching dashboards.

## Database design

PostgreSQL holds relational data; TimescaleDB hypertables hold prices. One `instruments` table covers all five segments, so watchlists, alerts, trades and predictions reference a single key.

| Domain | Table | Key columns |
| --- | --- | --- |
| Identity | `users` | id, email, auth\_provider, plan, created\_at |
| Identity | `broker_accounts` | id, user\_id, broker, account\_ref, encrypted\_token, token\_expires\_at, status |
| Reference | `instruments` | id, segment (EQ, FNO, MF, CRYPTO), symbol, exchange, isin, amfi\_code, lot\_size, expiry, strike, option\_type, underlying\_id |
| Market data | `candles` (hypertable) | instrument\_id, timeframe, ts, open, high, low, close, volume, oi |
| Market data | `ticks` (hypertable, short retention) | instrument\_id, ts, price, volume |
| Market data | `mf_nav` | instrument\_id, nav\_date, nav |
| Market data | `option_chain_snapshots` (hypertable) | underlying\_id, expiry, ts, strike, ce\_oi, pe\_oi, ce\_iv, pe\_iv, ce\_ltp, pe\_ltp |
| Portfolio | `trades` | id, user\_id, broker\_account\_id, instrument\_id, side, qty, price, fees, product, traded\_at, source\_trade\_id |
| Portfolio | `holdings` | user\_id, instrument\_id, qty, avg\_cost, as\_of |
| Watchlists | `watchlists`, `watchlist_items` | user\_id, name; watchlist\_id, instrument\_id, position |
| Alerts | `alert_rules` | id, user\_id, instrument\_id, type, condition\_json, channels, cooldown\_sec, active |
| Alerts | `alert_events` | id, rule\_id, fired\_at, payload\_json, channel, status, delivered\_at |
| Alerts | `notification_channels` | user\_id, type (telegram, whatsapp, email), address, verified\_at |
| ML | `model_versions` | id, scope (instrument or segment), artifact\_uri, params\_json, metrics\_json, trained\_at, status |
| ML | `predictions` | id, model\_version\_id, instrument\_id, made\_at, horizon, predicted, lower, upper, actual, abs\_error |
| Learning | `lessons`, `quiz_questions`, `user_progress` | segment, level, body; lesson\_id, answer, score; user\_id, lesson\_id, status |
| Learning | `paper_accounts`, `paper_trades` | user\_id, cash; account\_id, instrument\_id, side, qty, price, ts |

Design rules:

- Store money as `NUMERIC(18,4)` and timestamps in UTC; the UI shows IST.
- Make trade import idempotent with a unique key on `(broker_account_id, source_trade_id)`.
- Build 1m candles first; derive 5m, 15m, 1h and 1d with continuous aggregates, and compress chunks older than 7 days.
- Keep tick data for days, candles for years, so storage stays bounded.
- Index `alert_rules` on `(instrument_id, active)` so the evaluator can match a tick to its rules in one lookup.

## Backend plan

Start as a modular monolith with eight clearly separated modules, run as separate processes from day one, so any of them can later become its own service.

| Module | Responsibility | Talks to |
| --- | --- | --- |
| `market-ingest` | Holds provider WebSockets, normalises ticks, builds 1m candles, publishes to Redis | Providers, Redis, TimescaleDB |
| `api` | REST endpoints, auth, validation, OpenAPI schema | Postgres, Redis, other modules |
| `ws-gateway` | Pushes subscribed symbols to browsers and the extension | Redis Pub/Sub |
| `analysis` | Indicators, option-chain metrics, fund and crypto statistics, cached | TimescaleDB, Redis |
| `ml-service` | Training jobs, batch inference, model registry | MLflow, TimescaleDB |
| `trade-sync` | Broker adapters: OAuth, import, de-duplication, reconciliation | Broker APIs, Postgres |
| `alert-engine` | Matches ticks and schedules against rules, applies cooldowns | Redis, Postgres |
| `notifier` | Sends messages to Telegram, WhatsApp and email, retries failures | Channel APIs |

Core REST endpoints, all under `/v1` and all returning typed JSON:

| Feature | Endpoints |
| --- | --- |
| Market view | `GET /instruments/search`, `/quotes`, `/candles`, `/fno/chain`, `/mf/{code}/nav`, `/crypto/markets` |
| Analysis | `GET /analysis/technical`, `/analysis/option-chain`, `/analysis/funds`, `/analysis/crypto` |
| Prediction | `GET /predictions/{instrument}`, `/predictions/{instrument}/backtest` |
| Learning | `GET /learn/lessons`, `POST /learn/quiz/{id}/answer`, `POST /paper/orders` |
| Trades | `POST /brokers/{broker}/connect`, `POST /trades/sync`, `GET /trades`, `GET /portfolio` |
| Alerts | `GET/POST/PATCH/DELETE /alerts`, `POST /channels/telegram/link` |
| Streaming | `WS /ws/stream` with subscribe and unsubscribe messages per symbol |

Cross-cutting rules:

- Cache latest quotes in Redis with a 1-second TTL and indicator results for the length of one candle.
- Rate-limit per user and per provider key; queue the excess instead of failing.
- Generate the TypeScript API client from the OpenAPI schema so frontend and backend cannot drift.
- Schedule jobs in IST: AMFI NAV after publication in the evening, end-of-day loads after market close, retraining on weekends.

## LSTM prediction pipeline

Train one global LSTM per segment and timeframe to forecast the next return with a 10th-to-90th percentile band, and show a forecast only when it beats a naive baseline in walk-forward tests. Price series are noisy, so the band and the backtest matter more than the point estimate.

| Segment | Timeframes and horizons | Segment-specific features |
| --- | --- | --- |
| Stocks | Daily: 1 and 5 days | Nifty return, India VIX, sector index return, volume z-score |
| Intraday | 5m and 15m: next 3 bars | Time of day, opening gap, VWAP distance |
| F&O | Forecast the underlying, not option premiums: daily, 1 and 5 days | Open-interest change, put-call ratio, implied-volatility rank |
| Mutual funds | NAV: 21 trading days | Benchmark index return, category average return |
| Crypto | 1h and 1d: 1 and 24 steps | BTC return as market factor, 24h volume, funding rate where available |

Pipeline steps:

1. **Features.** Build windows of 60 steps from candles: log returns, RSI, MACD, ATR, volume z-score, plus the segment features above. Scale with statistics from the training window only.
2. **Target.** Predict log return rather than price, with three outputs (10th, 50th and 90th percentile) trained on pinball loss.
3. **Model.** Two LSTM layers of 64 to 128 units, dropout 0.2, and an instrument embedding so one model serves many symbols.
4. **Validation.** Walk-forward splits with an expanding window and a purge gap between train and test; never shuffle across time.
5. **Baselines.** Compare with last-value, moving-average and gradient-boosted models; ship an LSTM only where it wins on pinball loss and directional accuracy after costs.
6. **Serving.** Run batch inference after each candle close, write results to `predictions`, and let the API read from that table instead of running the model per request.
7. **Monitoring.** Fill in `actual` and `abs_error` when the horizon passes; compare rolling error with the baseline weekly and hide any forecast whose model has fallen behind it.
8. **Registry.** Track every run in MLflow, promote a challenger to champion only after it beats the current model on the latest walk-forward fold.

On screen, always show the band, the model's backtest hit rate and the data timestamp. Forecasts shown to the public may fall under SEBI rules for research analysts or investment advice, so get legal review before launch.

## Frontend plan

One app shell with a segment switcher (Stocks, F&O, Intraday, Mutual funds, Crypto) and five areas beneath it: Market, Analysis, Predict, Learn and Portfolio. Every area reads the active segment, so each dashboard is built once and configured per segment.

| Area | Main screens | Interactive elements |
| --- | --- | --- |
| Market | Watchlist, index and sector heatmap, instrument page, F&O option chain, MF explorer, crypto board | Live-updating prices with flash on change, candlestick chart with timeframe and indicator toggles, drag-to-reorder watchlist, strike-range slider on the option chain |
| Analysis | Technical panel, option-chain analytics (max pain, OI build-up, put-call ratio), fund comparison, crypto metrics | Indicator picker, side-by-side compare of up to 4 instruments, SIP calculator and rolling-return charts for funds, saved layouts |
| Predict | Forecast chart with confidence band, model scorecard, backtest view | Horizon selector, toggle between forecast and baseline, hover to see predicted against actual after the horizon passes |
| Learn | Course map per segment, lesson reader, glossary, quiz, paper-trading terminal | Progress tracking, inline definitions on any dashboard term, practice orders against live prices with virtual cash |
| Portfolio | Unified trade book, holdings, P&L by broker and segment, broker connections | Filter by broker, segment and date, CSV export, one-click broker connect |
| Alerts | Rule builder, alert history, channel setup | Condition builder with live preview of the current value, test message button |

Build notes:

- Organise code by feature folder (`features/market`, `features/analysis` and so on) on top of shared `ui`, `charts` and `api-client` packages.
- Open one WebSocket per tab and share it through a subscription manager that adds and removes symbols as components mount and unmount.
- Throttle repaint to animation frames and virtualise long tables so a 200-row watchlist stays smooth.
- Offer light and dark themes, and keep gain and loss readable without relying on red and green alone.
- Run the core flows (search, chart, alert creation, trade import) through Playwright tests on every pull request.
- Show the data timestamp and provider on every price, and a "delayed" badge whenever the feed lags.

## Browser extension

Ship a Manifest V3 extension built from the same React packages as the web app, so the extension is a second shell over the existing API rather than a second product. Build once with WXT or Plasmo for Chrome, Edge and Firefox.

| Surface | Purpose | Notes |
| --- | --- | --- |
| Side panel | Full dashboards next to any page: watchlist, analysis, forecast, alerts | Chrome side panel API; Firefox sidebar for the same bundle |
| Popup | Quick quote search, today's alerts, open side panel | Smallest bundle, loads instantly |
| Content script | Detects a symbol on supported broker, news and charting sites and shows a mini-card with price, forecast band and an "Add alert" button | Runs only on an allow-listed set of hosts |
| Background service worker | Token refresh, alarms, desktop notifications for fired alerts | Wakes on `chrome.alarms` and push; do not hold long-lived state in memory |
| Options page | Account, connected brokers, site allow-list, theme | Reuses web app settings components |

Design decisions:

- **Login.** Sign in through the web app's OAuth flow with `chrome.identity.launchWebAuthFlow`; keep the session token in `chrome.storage.session`, not in page-accessible storage.
- **Live prices.** Open the WebSocket from the side panel while it is visible; service workers sleep after short idle periods, so use polling and alarms for background alerts.
- **Permissions.** Request narrow host permissions for named sites and `activeTab` for everything else; never read order forms, passwords or account numbers on broker pages.
- **Symbol detection.** Prefer reading the symbol from the page URL or a known DOM element per site; fall back to matching text against the instrument list only on user action.
- **Updates and review.** Publish through the Chrome Web Store and Edge Add-ons with a privacy policy that lists exactly what is read; keep remote code out, since Manifest V3 forbids it.
- **Other platforms.** The same packages can also ship as an installable PWA and an embeddable iframe widget, if you later want presence beyond browsers.

## Unified trade view

Each broker gets a small adapter that turns its trades, positions and holdings into one canonical shape, so the trade book, P&L and alerts work the same whatever the source. Start read-only with two brokers and one CSV importer, then add adapters one at a time.

| Source | Connection method | Data pulled | Caveat |
| --- | --- | --- | --- |
| Zerodha, Upstox, Angel One, Dhan, Fyers | Broker login flow or API key plus TOTP, depending on the broker | Trades, positions, holdings, fund balance | Tokens expire often (daily for some); APIs may return only recent trades, so older history needs a tradebook upload |
| Mutual funds | Consolidated account statement from CAMS and KFintech, uploaded as PDF | Folios, units, transactions | Statement parsing breaks when layouts change; add tests with sample files |
| Crypto exchanges | Read-only API keys | Trades, balances | Store keys encrypted and refuse keys that carry withdrawal rights |
| Any other platform | CSV upload with a column-mapping step | Trades | Save the mapping per source so the second upload is one click |

How a sync runs:

1. **Connect.** The user authorises read-only access; the token goes to the encrypted store.
2. **Backfill.** Pull everything the source allows, then ask for a tradebook upload to fill older gaps.
3. **Normalise.** Map each broker symbol to an `instruments` row through ISIN or exchange token, and convert side, product, fees and timestamps to the canonical schema.
4. **De-duplicate.** Upsert on `(broker_account_id, source_trade_id)` so repeated syncs never double-count.
5. **Compute.** Match buys to sells first-in, first-out for realised P\&L; adjust for splits and bonuses; settle expired F&O contracts at the exchange settlement price.
6. **Reconcile.** Compare computed positions with the broker's own holdings and flag any mismatch for the user instead of silently correcting it.
7. **Refresh.** Poll every few minutes in market hours and once after close; show a "last synced" time per broker.

The Portfolio screen then offers one table of all trades with filters by broker, segment and date, a combined holdings view, and P&L split by broker, segment and intraday against delivery.

## Alert bots

A rules engine evaluates streaming and scheduled conditions, writes each firing to `alert_events`, and a notifier delivers it to Telegram, WhatsApp or email. Telegram ships first because it needs no message-template approval.

| Rule type | Example | Evaluated |
| --- | --- | --- |
| Price | RELIANCE crosses 3,000 | On every tick |
| Percent move | Any Nifty 50 stock moves 3% in 15 minutes | On each candle close |
| Indicator | RSI(14) on TCS daily falls below 30 | On each candle close |
| F&O | Bank Nifty put-call ratio above 1.3, or open interest jumps 10% at a strike | Every option-chain snapshot |
| Mutual fund | NAV falls 2% in a day, or a new NAV is published | After the daily NAV load |
| Crypto | BTC moves 5% in an hour | On each tick |
| Portfolio | Daily portfolio loss exceeds a set amount, or a broker token is about to expire | After each trade sync |
| Forecast | A model's 5-day band turns negative for a watchlist stock | After each inference run |

How the engine works:

- Keep active rules indexed by instrument in Redis, so each tick matches only its own rules instead of scanning all of them.
- Apply a cooldown per rule, optional quiet hours, and a daily cap per user, so a volatile market does not flood anyone.
- Treat `alert_events` as an outbox: the notifier reads pending rows, sends with an idempotency key, retries with backoff, and records delivery status.

Channels:

- **Telegram.** A bot with a one-time link code to bind an account, commands such as `/price`, `/alerts` and `/pause`, and inline buttons to snooze or disable a rule from the message.
- **WhatsApp.** The Business Cloud API with explicit opt-in; messages outside the 24-hour reply window need pre-approved templates, so submit templates early.
- **Email.** Amazon SES for instant alerts and a daily digest after market close.
- **Extension.** Desktop notifications from the background worker for users with the extension installed.

Alerts describe a condition that was met; they do not tell anyone to buy or sell.

## Security and compliance

The biggest exposures are stored broker credentials and anything that reads like a buy or sell recommendation, so design for read-only access and informational output. This is an engineering outline, not legal advice; confirm the points below with an Indian securities lawyer before launch.

| Area | Control |
| --- | --- |
| Login | OAuth sign-in, optional multi-factor, short-lived JWT with rotating refresh tokens, `httpOnly` cookies on the web |
| Broker credentials | Read-only scopes only; envelope encryption with a KMS-held key; never logged; deleted when the user disconnects |
| Personal data | Consent and purpose limits under India's Digital Personal Data Protection Act, 2023; user-triggered export and deletion; host data in an Indian region |
| SEBI exposure | Personalised buy or sell calls may require registration as a research analyst or investment adviser; keep outputs informational (data, user-defined alerts, labelled model forecasts) and show clear disclaimers |
| Exchange data | Real-time redistribution of NSE and BSE data needs a licence; v1 relies on the user's own broker feed and delayed or end-of-day data for public pages |
| API protection | Per-user rate limits, input validation, WAF, dependency scanning, secrets in a manager rather than in code |
| Auditability | Append-only audit log for broker connect and disconnect, alert changes and data exports |
| Extension | Narrow host permissions, strict content security policy, no remote code, privacy policy listing every data point read |
| Resilience | Daily encrypted backups, point-in-time recovery for Postgres, tested restore each quarter |

## Roadmap

&#91;embedded content: roadmap · 5 phases, 8 workstreams, 5 gates\]

Market view comes first, analysis, trades and alerts follow once data flows, and forecasts and learning wait until there is history to train and test on. A phase starts only when the previous gate is met:

- **Gate 0, week 3.** One NSE stock streams from a provider adapter into TimescaleDB and onto a browser chart in staging, from login to candle.
- **Gate 1, week 9.** All five segments show live or end-of-day data, feed-lag monitoring is on, and the app is load-tested at the expected number of simultaneous users.
- **Gate 2, week 15.** Two brokers and one CSV import reconcile with the brokers' own holdings, and alerts reach Telegram and email within their cooldown rules.
- **Gate 3, week 21.** Every forecast on screen beats the naive baseline in walk-forward tests, or is hidden; lessons cover all five segments.
- **Gate 4, week 24.** The extension has passed store review, the security review is closed, legal sign-off on disclaimers is done, and a database restore has been tested.

## Risks and open questions

The 24-week estimate assumes a team of three to four engineers and one part-time ML engineer; it grows if live-data licensing or SEBI review delays launch.

| Risk | Effect | Mitigation |
| --- | --- | --- |
| Data licensing or provider terms change | Live prices disappear or become costly | Provider adapters, user-own-broker feeds, delayed and end-of-day fallbacks |
| LSTM does not beat naive baselines | Prediction dashboard has little value | Gate every forecast on walk-forward results; ship as an "experimental" label and show baselines |
| Users read forecasts as advice | Regulatory and reputational exposure | Bands, hit rates and disclaimers on screen; legal review before public launch |
| Broker API changes or daily token expiry | Trade sync silently stops | Per-broker contract tests, "last synced" badge, expiry alerts to the user |
| Feed outage or lag during market hours | Wrong prices and missed alerts | Heartbeat monitoring, "delayed" badge, failover provider where licensed |
| Mutual fund statement formats change | Holdings import fails | Sample-file test suite, CSV fallback |
| Extension store rejection | Delays phase 4 | Minimal permissions, privacy policy ready, early test submission |

Open questions:

- Is the first release a private tool for you, or a public product? This decides how much SEBI and licensing work comes before launch.
- Which two brokers should the trade view support first?
- Is one-second snapshot data enough for intraday, or do you need tick-by-tick and market depth?
- What monthly budget is available for data and hosting?
- Should Hindi or other Indian languages be in scope for the learning dashboard?
