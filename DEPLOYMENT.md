# Deployment: Vercel frontend + Render backend

## Deployed URLs

- **Frontend:** https://stockvista-analysis-platform.vercel.app
- **Backend:** https://stockvista-api.onrender.com
- **API docs:** https://stockvista-api.onrender.com/docs
- **Health:** https://stockvista-api.onrender.com/health

## Architecture

- **Frontend:** static HTML/CSS/JS in the repository root, deployed to Vercel.
- **Backend:** FastAPI app in `backend/`, deployed to Render using `render.yaml`.
- The frontend reads `window.SV_BACKEND_URL` from `config.js` so it can call the
  Render service and open its WebSocket stream.

## 1. Deploy the backend to Render

1. Sign in to Render and choose **New + → Blueprint**.
2. Connect the GitHub repository `Rishavuc/stocky`.
3. Render detects `render.yaml` and creates the `stockvista-api` web service.
4. Set any optional credentials in the Render dashboard:
   - `GOOGLE_CLIENT_ID` (for Google sign-in)
   - Zerodha keys if you want broker-backed live data
5. Wait for the service to become live. The current service is
   `stockvista-api` at `https://stockvista-api.onrender.com`.
6. Verify:
   ```text
   https://<your-render-service>/health
   https://<your-render-service>/docs
   ```

> Note: the Blueprint uses SQLite for simplicity. Render's filesystem is
> ephemeral, so user accounts and audit logs reset after a redeploy. For
> production persistence, switch `DATABASE_URL` to a managed Postgres database.

> Memory: Render sets `RENDER=true`, which automatically switches the estimate
> endpoint to its low-memory empirical quantile estimator so a single LSTM
> training request cannot exhaust the free 512 MB instance. Local development
> still uses the real PyTorch LSTM. On a paid Render plan you can force the
> LSTM back on with `STOCKVISTA_DISABLE_TORCH=false`.

## 2. Point the frontend at the backend

Edit `config.js` and set the Render URL:

```js
window.SV_BACKEND_URL = "https://<your-render-service>";
```

## 3. Deploy the frontend to Vercel

1. Sign in to Vercel and choose **Add New → Project**.
2. Import the same GitHub repository.
3. Vercel detects `vercel.json`; no build command is required.
4. Deploy and open the generated `*.vercel.app` URL. The current production
   URL is `https://stockvista-analysis-platform.vercel.app`.

## Enable automatic frontend deploys

The first deployment was uploaded with the Vercel CLI. To deploy automatically
on every push to `main`, authorize Vercel's GitHub app for `Rishavuc/stocky`,
then run:

```bash
vercel git connect --project stockvista-analysis-platform --yes
```

If the GitHub app is not yet authorized, that command fails with a repository
access error; the deployed site itself is unaffected.

## Local development

Leave `window.SV_BACKEND_URL = ""` in `config.js` and run:

```bash
cd backend
venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Then open `http://localhost:8000/`.

## Security settings (backend)

- In production the backend serves **no static files** (`SERVE_FRONTEND=false`); Vercel hosts the frontend.
- CORS allows only the Vercel production URL, `FRONTEND_URL`, and any extra origins in `CORS_ORIGINS` (comma-separated). Add Vercel preview URLs there if previews need the API.
- `ADMIN_USER_IDS`: comma-separated user ids allowed to set the shared Kite session or view the Binance account. Empty means nobody.
- `KITE_CALLBACK_ENABLED`: off by default in production. Turn it on only while the admin re-authorizes Kite.
- Rate limits read the client IP from the rightmost `X-Forwarded-For` entry on Render. Do not add `--forwarded-allow-ips='*'` to the start command.
- Security regression checks: `cd backend && ../.venv/bin/python tests/security_checks.py`
