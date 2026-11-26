# Deployment: Vercel frontend + Render backend

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
5. Wait for the service to become live and copy its URL, e.g.
   `https://stockvista-api.onrender.com`.
6. Verify:
   ```text
   https://<your-render-service>/health
   https://<your-render-service>/docs
   ```

> Note: the Blueprint uses SQLite for simplicity. Render's filesystem is
> ephemeral, so user accounts and audit logs reset after a redeploy. For
> production persistence, switch `DATABASE_URL` to a managed Postgres database.

## 2. Point the frontend at the backend

Edit `config.js` and set the Render URL:

```js
window.SV_BACKEND_URL = "https://<your-render-service>";
```

## 3. Deploy the frontend to Vercel

1. Sign in to Vercel and choose **Add New → Project**.
2. Import the same GitHub repository.
3. Vercel detects `vercel.json`; no build command is required.
4. Deploy and open the generated `*.vercel.app` URL.

## Local development

Leave `window.SV_BACKEND_URL = ""` in `config.js` and run:

```bash
cd backend
venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Then open `http://localhost:8000/`.
