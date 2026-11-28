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
// Local pages talk to the local backend: the Render API only allows the
// deployed Vercel origin (CORS), so pointing localhost at it would fail.
window.SV_BACKEND_URL = ["localhost", "127.0.0.1", ""].includes(window.location.hostname)
    ? ""
    : "https://stockvista-api.onrender.com";
