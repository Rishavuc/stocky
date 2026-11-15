# Current verification and remaining gates

Verification date: 14 November 2026, Asia/Kolkata.

## Automated and real-service checks

- 32 integration tests pass. They cover the original trading/account flows plus immutable replay inputs, partial-refresh preservation, CSV validation/FIFO/duplicates, private imported records, encrypted credentials, recipient verification, durable and uncertain delivery states, recovery-token reuse, extension pairing/revocation, financial facts, actual monthly NAV SIP calculations private broker observations, inference without refitting, market-context timing, unknown-fee enrichment and broker timestamp formats.
- Production React/TypeScript build passes. The Chrome/Edge companion package builds from shared React chart components.
- The original real-HTTP acceptance journey passes against PostgreSQL: delivered assets, fresh account, watchlist, replay next-session fills, alerts, lesson progress, journal, session persistence, private-file denial and WebSocket snapshot.
- The expanded real-HTTP acceptance journey passes: five market segments, new connected pages, CSV/FIFO import, duplicate prevention, unchanged virtual wallet, 13 lessons, bookmarks, four segment-specific forecast types, operations and extension pairing.
- PostgreSQL acceptance passes for eight concurrent duplicate submissions, eight competing whole-account reservations and a full web-process restart.
- A real encrypted backup restored into an isolated disposable PostgreSQL database with user, record and migration counts matched to the exported source snapshot, while background workers remained active.
- Actual provider downloads succeeded: Yahoo chart observations, Binance daily bars, AMFI's latest published NAV file and attributed MFapi historical NAV. There are 29 stored datasets and 53 latest forecasting reports, each with three chronological test folds.
- Real Binance public ticker retrieval succeeded for BTCUSDT, ETHUSDT and SOLUSDT. Public quotes cannot spend the INR paper wallet.
- The independent scheduled process completed a market refresh, retraining and prediction-outcome update. Job state is persisted and exposed in Operations.
- Python and frontend dependency audits report zero known vulnerabilities in the checked installed sets.
- Base and production Compose configurations, shell syntax, Python compilation and Git whitespace checks pass. API request contracts are generated from the current server schema.

Tests use controlled fixtures for broker/notification behavior and do not send messages to external recipients. HTTP acceptance scripts delete only their temporary accounts. Existing user data is preserved.

## Not yet accepted as working external integrations

- Real Kite/Upstox authorization, account reconciliation and option-chain retrieval: eligible broker accounts have not been configured.
- Real Telegram, SMTP or WhatsApp receipt: recipient verification credentials have not been configured. A coded transport and a passing fixture test are not successful real delivery.
- Actual recovery-email receipt: account SMTP is not configured.
- Browser layout, popup/side-panel behavior and supported-page detection: no browser was opened under the CLI-only instruction. Follow EXTENSION.md for manual acceptance.
- Container image execution: the Docker daemon is unavailable. Configuration validation is not an image-build result.
- Hosted HTTPS release: default AWS credentials are absent; the existing `mailflow` login session is expired. No cloud resources have been created and no hosted URL is claimed.
- Extension store publication: owner developer access and manual review are still required.

Exchange-specific derivatives settlement/margin, automated corporate actions, licensed fundamentals and Firefox compatibility are not represented as complete. See IMPLEMENTATION_STATUS.md for the full boundary.

## Local handoff

- Workspace: http://127.0.0.1:8000
- Source: `/Users/harkiratkalra/harkirat/projects/finance/investors-eye`
- Branch: `codex/capstone-platform`; changes remain local, not pushed to the classmate's repository.
- Start: `scripts/start.sh`; stop app/worker/scheduler: `scripts/stop.sh`.
- Stop database separately: `scripts/database.sh stop`.
- Provider setup: `docs/PROVIDER_SETUP.md`; extension: `docs/EXTENSION.md`.
