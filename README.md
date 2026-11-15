# InvestorsEYE

A private educational investing workspace with real market observations, historical replay, virtual portfolios, measured forecasting experiments, a unified imported trade book, notifications, learning, and a Chrome/Edge companion.

## Start the installed checkout

```bash
cd /Users/harkiratkalra/harkirat/projects/finance/investors-eye
scripts/start.sh
```

Open [the workspace](http://127.0.0.1:8000), register your own account, and use **All markets** or **Market replay**. `scripts/stop.sh` stops the application, notification worker and scheduler without deleting data.

The installed database is project-local PostgreSQL on port 55432. Its credentials and data are ignored by Git. The database helper is `scripts/database.sh start|stop|status`. The application uses new `eye_*` tables and versioned migrations; it does not overwrite the upstream database.

## What has working implementation

| Original feature | Current implementation |
| --- | --- |
| Market view | 29 attributed datasets: 12 equities, 3 indices, 2 five-minute series, 9 crypto series and 3 funds; saved watchlists, sector summaries, comparison API and market explorer |
| Analysis | Calculated technical indicators, fund return analysis, source-attributed user-entered financial statements and ratios, authenticated Upstox options-chain adapter |
| Predictions | 53 saved experiments; 3 expanding chronological evaluations per experiment; price, moving-average, boosting and quantile LSTM comparisons; versioned run registry; prediction outcomes and scheduled refresh/training |
| Learning and paper trading | 13 lessons across five segments, glossary, bookmarks, saved quiz progress, decision journal, persistent wallets, orders, replay, costs and benchmarks |
| Browser extension | Buildable Chrome/Edge popup and side panel, API pairing, watchlist/alert actions, supported URL/title symbol detection, explicit token revocation |
| Unified trade view | CSV preview/mapping/validation, duplicate-safe import, FIFO accounting with fees and currency separation, transaction filters/export, broker connection/authorization/sync adapters and reconciliation |
| Alert bots | Price, percent, RSI, NAV and portfolio-loss conditions; open-interest adapter; encrypted channels, recipient verification, Telegram/SMTP/WhatsApp transports, persistent delivery state, quiet hours, bounded connection retries and signed WhatsApp receipts |

**Implementation is not the same as external verification.** Real broker authorization, real external notification delivery, extension browser interaction, Docker image execution and hosted deployment still require the integrations or manual acceptance described below. No dummy options chains, company fundamentals, prices, confidence figures or successful delivery claims fill those gaps.

## Data integrity

Histories live in content-addressed immutable files. A catalog refresh atomically publishes new versions and retains previous valid instruments when one provider fails. Replay sessions pin their dataset checksum, so rolling refreshes cannot change their historical clock. The schema migration pins existing saved sessions before switching data.

Each dataset records its provider, retrieval time, observation dates, currency and checksum. Yahoo data is explicitly unofficial. Binance pairs retain USDT denominations; USD references are separate instruments. AMFI supplies the current fund publication and MFapi history is separately attributed. No price conversion is invented.

Provider access does not imply permission for public redistribution. This checkout targets a private educational audience.

## Forecasting

```bash
.venv/bin/python scripts/refresh_markets.py
PYTHONPATH=backend OMP_NUM_THREADS=2 .venv/bin/python -m app.research
.venv/bin/python scripts/results.py
```

Each model run saves weights, preprocessing, dataset version, settings, chronological folds, held-out results and latest inference. The final web-serving image does not require PyTorch. A separate job process refreshes data after 17:00 Asia/Kolkata and trains the new observations. Completed intraday/hourly bars refresh every five minutes, with inference using saved preprocessing and weights. Nifty/Bitcoin context is joined only from earlier available bars and its dataset lineage is saved. The operations page shows durable job status and failures. Successful daily refreshes also create an encrypted database backup; backup failures are recorded separately from model-job success.

The LSTM estimates 0.1, 0.5 and 0.9 return quantiles using pinball loss. Simpler selected models use measured validation-residual intervals. Coverage is empirical, not guaranteed. Every current run is labeled experimental unless it passes the stated cross-fold gate; a poor experiment is retained rather than disguised as a successful model. Research forecasts trained on later observations never appear inside historical replay.

Horizon defaults: equities/indices 1 and 5 observations; intraday 3 bars; fund NAV 21 observations; crypto 1 and 24 observations. Data is capped at 4,000 observed bars per experiment to keep local training practical.

## Set up a fresh machine

Python 3.12 and Node.js 22+ are required. Use the local implementation branch after it has been shared; changes are not automatically pushed upstream.

```bash
scripts/setup.sh
cp .env.example .env
# Set DATABASE_URL for PostgreSQL before starting.
scripts/start.sh
```

`backend/requirements.txt` contains serving dependencies; training and development dependencies are separate. SQLite is supported for tests and temporary local trials, while PostgreSQL is the deployment and concurrency target.

Generate the frontend request contracts after changing API schemas:

```bash
PYTHONPATH=backend .venv/bin/python scripts/export_contracts.py
```

## Verification

```bash
PYTHONPATH=backend .venv/bin/pytest -q
npm --prefix frontend run build
scripts/build_extension.sh
.venv/bin/python scripts/verify_running.py
.venv/bin/python scripts/verify_platform.py
.venv/bin/python scripts/verify_postgres.py
.venv/bin/python scripts/backup.py --verify
```

The HTTP scripts need the server running. They clean up only their generated verification accounts. The PostgreSQL acceptance script uses its own web process and checks concurrent requests and restart persistence. The backup command creates an encrypted backup, restores into a disposable local database, compares counts and removes that test database. Back up the encryption key separately.

No browser automation is used. See [extension acceptance](docs/EXTENSION.md), [provider setup](docs/PROVIDER_SETUP.md), and [current verification](docs/VERIFICATION.md).

## Deployment

```bash
docker-compose up --build -d
```

Compose runs PostgreSQL, web, provider/notification worker and the independent training scheduler. Dataset, model and runtime volumes are shared across those processes. `compose.production.yaml` adds HTTPS and a private-team IP allowlist. It requires a real domain, encryption key and access configuration. The configuration has a validation gate; a container build and cloud release must still be verified on an available runtime.

The available AWS `mailflow` session is expired. The local Docker daemon is unavailable and the existing Colima profile is broken; only 8.8 GiB of local disk was free at the last check, so a large new virtual-machine build was not started. No cloud resources or public deployment have been created. [Provider setup](docs/PROVIDER_SETUP.md) lists required configuration without requesting secrets in chat.

## Explicit limits

- Broker APIs and delivery transports have controlled test coverage. Actual provider acceptance requires the user's eligible accounts and verified recipients.
- Financial facts are user-supplied and source-attributed, not independently audited vendor fundamentals. Unsupported corporate actions and incomplete opening histories are reconciliation issues, not silently corrected balances.
- Replay uses observed bars, optional fixed basis-point fees, whole-unit simulation and no shorting/leverage. It cannot reproduce intrabar ordering or exchange-specific settlement/margin rules. Derivatives are currently research-only; a production-grade derivatives simulator is not claimed.
- Some source timestamps or publications can be delayed. Stale data cannot authorize current-market fills.
- The extension is built and API-tested. Visual/browser acceptance and store publication remain manual, and Firefox is not part of this build.
- The original HTML pages and unused backend modules remain reference-only. The active app is FastAPI's current route tree plus `frontend/src`.

The upstream README claimed MIT licensing without a license file in the inspected tree; no new license grant is assumed.
