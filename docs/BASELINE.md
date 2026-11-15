# Starting point

Upstream: TechSnail7/InvestorsEYE, commit `35222181b9dc88b8c7c10e2ae196614af1b12987`.

The initial assessment inspected source, route wiring, requirements, and history. It did not establish that the upstream application ran successfully. The v2 application has separate runtime verification.

| Area | Starting state | v2 change |
| --- | --- | --- |
| Interface | Substantial standalone HTML/CSS pages | One React application, common selected instrument, connected views |
| Authentication | Password hashes, predictable unsigned identity tokens | Hashed random sessions, HTTP-only cookies, server-side expiry and logout |
| File delivery | Entire repository mounted as public static files | Only the built index and assets served |
| Market prices | Provider attempts mixed with synthetic ticks/fallbacks | Attributed historical observations; authenticated fresh quotes required for current-market fills |
| Analysis | Some calculated indicators; fixed company and options figures | Calculated historical indicators, unavailable fundamentals explicitly stated |
| Predictions | Random upward-biased paths and hardcoded evaluation | Saved baseline/boosting/LSTM experiments with chronological splits |
| Trading | Shared process-memory wallet with seeded positions | User-owned transactional wallets, reservations, order lifecycle, decimal accounting |
| Replay | Missing | Isolated saved sessions, next-bar fills, hidden future observations, benchmark |
| Learning | Routes and presentation content | Saved quizzes and progress integrated with the workspace |
| Operations | Loose dependency constraints, no test suite in the tree | Locked frontend, pinned Python inputs, integration tests, container package |

Original pages and unused backend modules remain in Git for reference. They are not mounted in the v2 application. The public entry point is `backend/app/main.py`; the v2 modules are `store`, `market`, `trading`, `worker`, and `model_training`.
