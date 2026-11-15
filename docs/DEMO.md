# Five-minute capstone demonstration

## Before presenting

Run `scripts/start.sh`, open the local address, and register your own account. No broker credentials are required for historical replay. Complete the steps once and resume the saved session for the actual presentation if needed. Keep a fresh replay ready if the evaluator wants to choose a different date.

Use RELIANCE, pick an available date about six months before the dataset end, and leave future candles hidden. All capital is virtual.

## 0:00 to 0:40: The product

“This is InvestorsEYE, a research and practice workspace. I can follow a company, investigate the evidence, make a virtual decision, and review the outcome. Each price shows its source and date.”

Open Markets, search for RELIANCE, and save it to the watchlist. Open its research page. Point out that historical daily closes are labeled, not presented as a live stream.

## 0:40 to 1:20: Connected research

Move the chart and explain one indicator in plain language. Open the model lab and identify the four competing models, dated training/test periods, and measured price errors.

“The app retains disappointing results. We choose the model using validation data before evaluating it on the final test period. Predicting tomorrow equals today is an important baseline.”

Do not claim that the neural network always wins or that a measured interval guarantees an outcome.

## 1:20 to 2:50: The memorable interaction

Open Market replay. Start a session, record a reason, and buy ten virtual shares. Show that the order is pending, then advance one session and inspect its next-open fill. Advance five more sessions. Compare portfolio value with simply holding the stock.

“The server reveals only observations through this date. The order could not fill at a price that was already visible. The portfolio, journal, and analysis share the replay clock.”

Pause playback before interacting with the evaluator. The controls deliberately avoid simultaneous advance requests.

## 2:50 to 3:35: Alerts and learning

Open Alerts, choose the active replay, and enter a threshold near the current price. Advance one session at a time until it crosses. Open the event trail. If it does not cross, explain that it correctly has not fired; use the prepared saved crossing for the rehearsal.

Open a lesson, answer the quiz, and show the saved progress.

## 3:35 to 4:20: Imports, persistence and accountability

Briefly open Unified trade book and its CSV preview. Imported real-account records are separate from virtual capital. Then open the journal and inspect the reasoning, observed price, fill price, and marked price change. Refresh the page, sign in if needed, and resume the saved replay. The holdings and history remain. Explain that another account cannot access this session.

## 4:20 to 5:00: Engineering and limits

Show the architecture and the passing integration tests. Explain user-row database locks, idempotent order IDs, and private asset serving using one concrete example: two simultaneous purchases cannot spend the same cash twice.

“Broker-fed current-market execution is optional and requires fresh authenticated quotes. The reliable credential-free demonstration is historical replay. This build does not place real-money orders.”

## Likely viva questions

- Why LSTM? It is one tested sequence model, not an assumed winner. Compare its measured result with boosting and the last-price baseline.
- Where is the novelty? The connected decision-to-outcome workflow, isolated historical clocks, honest model comparison, reproducible replay, and attributable decision journal.
- How do you prevent looking into the future? The server slices replay history, indicators use that cutoff, fills happen on later bars, and research forecasts are unavailable inside replay.
- What happens without the internet? The bundled attributed history, trained reports, local database, replay, lessons, and journal continue to work. Current-market data is unavailable rather than fabricated.
- What remains? Real broker and notification acceptance, manual extension/browser verification, hosted deployment, and exchange-specific derivatives settlement rules. CSV imports, notification transports, wider observed data, and rolling evaluation are now implemented.

## Prepared crossing for the bundled dataset

Start a RELIANCE replay on **2026-04-07**. Before advancing, create an alert in that replay for a crossing **above ₹1,326.20**. Advance one session. The observed close on 2026-04-08 crosses the threshold, so the saved event should appear. These rehearsal values come from the bundled dataset; regenerate them if the dataset is refreshed.
