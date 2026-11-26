/**
 * StockVista Analysis Platform — runtime backend configuration.
 *
 * Local development:
 *   Leave SV_BACKEND_URL empty. The app uses same-origin /v1 and ws://...:8000.
 *
 * Vercel frontend + Render backend:
 *   This points to the deployed Render service.
 *
 * Keep this file committed; it contains no secrets.
 */
window.SV_BACKEND_URL = "https://stockvista-api.onrender.com";
