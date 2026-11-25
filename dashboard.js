/* =============================================
   INVESTOR'S EYE — Shared Dashboard JavaScript
   ============================================= */

// ===== SIDEBAR TOGGLE (Mobile) =====
function initSidebar() {
    const sidebar = document.getElementById('dashSidebar');
    const overlay = document.getElementById('sidebarOverlay');
    const openBtn = document.getElementById('topbarHamburger');
    const closeBtn = document.getElementById('sidebarClose');

    if (openBtn) {
        openBtn.addEventListener('click', () => {
            sidebar.classList.add('open');
            overlay.classList.add('visible');
        });
    }

    function closeSidebar() {
        sidebar.classList.remove('open');
        overlay.classList.remove('visible');
    }

    if (closeBtn) closeBtn.addEventListener('click', closeSidebar);
    if (overlay) overlay.addEventListener('click', closeSidebar);
}

// ===== SEARCH SHORTCUT (Ctrl+K) =====
function initDashSearch() {
    document.addEventListener('keydown', (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
            e.preventDefault();
            const input = document.getElementById('dashSearchInput');
            if (input) input.focus();
        }
    });
}

// ===== SPARKLINE CHART HELPER =====
function drawSparkline(canvasId, data, color, fillColor) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;

    canvas.width = canvas.offsetWidth * dpr;
    canvas.height = canvas.offsetHeight * dpr;
    ctx.scale(dpr, dpr);

    const w = canvas.offsetWidth;
    const h = canvas.offsetHeight;
    const padding = 2;
    const min = Math.min(...data);
    const max = Math.max(...data);
    const range = max - min || 1;

    ctx.clearRect(0, 0, w, h);

    // Fill
    if (fillColor && fillColor !== 'transparent') {
        const grad = ctx.createLinearGradient(0, 0, 0, h);
        grad.addColorStop(0, fillColor);
        grad.addColorStop(1, 'transparent');
        ctx.beginPath();
        ctx.moveTo(padding, h);
        data.forEach((val, i) => {
            const x = padding + (i / (data.length - 1)) * (w - padding * 2);
            const y = h - padding - ((val - min) / range) * (h - padding * 2);
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        });
        ctx.lineTo(w - padding, h);
        ctx.lineTo(padding, h);
        ctx.closePath();
        ctx.fillStyle = grad;
        ctx.fill();
    }

    // Line
    ctx.beginPath();
    data.forEach((val, i) => {
        const x = padding + (i / (data.length - 1)) * (w - padding * 2);
        const y = h - padding - ((val - min) / range) * (h - padding * 2);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
    });
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.lineJoin = 'round';
    ctx.lineCap = 'round';
    ctx.stroke();
}

// ===== GENERATE CHART DATA =====
function generateChartData(baseVal, volatility, points = 30, trend = 'up') {
    const data = [];
    let val = baseVal;
    for (let i = 0; i < points; i++) {
        const trendBias = trend === 'up' ? 0.6 : trend === 'down' ? -0.6 : 0;
        val += (Math.random() - 0.5 + trendBias * 0.15) * volatility;
        data.push(val);
    }
    return data;
}

// ===== DRAW BAR CHART =====
function drawBarChart(canvasId, labels, values, colors) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;

    canvas.width = canvas.offsetWidth * dpr;
    canvas.height = canvas.offsetHeight * dpr;
    ctx.scale(dpr, dpr);

    const w = canvas.offsetWidth;
    const h = canvas.offsetHeight;
    const padding = { top: 10, right: 10, bottom: 30, left: 10 };
    const chartW = w - padding.left - padding.right;
    const chartH = h - padding.top - padding.bottom;
    const maxVal = Math.max(...values.map(Math.abs));
    const barWidth = (chartW / values.length) * 0.6;
    const gap = (chartW / values.length) * 0.4;

    values.forEach((val, i) => {
        const barH = (Math.abs(val) / maxVal) * chartH;
        const x = padding.left + i * (barWidth + gap) + gap / 2;
        const y = padding.top + chartH - barH;

        // Bar with rounded top
        const radius = 4;
        ctx.beginPath();
        ctx.moveTo(x, y + radius);
        ctx.arcTo(x, y, x + barWidth, y, radius);
        ctx.arcTo(x + barWidth, y, x + barWidth, y + barH, radius);
        ctx.lineTo(x + barWidth, y + barH);
        ctx.lineTo(x, y + barH);
        ctx.closePath();
        ctx.fillStyle = colors ? colors[i] : (val >= 0 ? '#00d09c' : '#ff5252');
        ctx.fill();

        // Label
        ctx.fillStyle = '#5a6478';
        ctx.font = '11px Inter, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(labels[i], x + barWidth / 2, h - 8);
    });
}

// ===== DRAW AREA CHART =====
function drawAreaChart(canvasId, data, color, fillColor, showDots = false, labels = []) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;

    canvas.width = canvas.offsetWidth * dpr;
    canvas.height = canvas.offsetHeight * dpr;
    ctx.scale(dpr, dpr);

    const w = canvas.offsetWidth;
    const h = canvas.offsetHeight;
    const pad = { top: 16, right: 16, bottom: labels.length ? 30 : 16, left: 16 };
    const chartW = w - pad.left - pad.right;
    const chartH = h - pad.top - pad.bottom;
    const min = Math.min(...data) * 0.995;
    const max = Math.max(...data) * 1.005;
    const range = max - min || 1;

    function getX(i) { return pad.left + (i / (data.length - 1)) * chartW; }
    function getY(v) { return pad.top + chartH - ((v - min) / range) * chartH; }

    // Grid lines
    ctx.strokeStyle = 'rgba(255,255,255,0.04)';
    ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i++) {
        const y = pad.top + (i / 4) * chartH;
        ctx.beginPath();
        ctx.moveTo(pad.left, y);
        ctx.lineTo(w - pad.right, y);
        ctx.stroke();
    }

    // Fill
    const grad = ctx.createLinearGradient(0, pad.top, 0, pad.top + chartH);
    grad.addColorStop(0, fillColor);
    grad.addColorStop(1, 'transparent');
    ctx.beginPath();
    data.forEach((v, i) => {
        if (i === 0) ctx.moveTo(getX(i), getY(v));
        else ctx.lineTo(getX(i), getY(v));
    });
    ctx.lineTo(getX(data.length - 1), pad.top + chartH);
    ctx.lineTo(getX(0), pad.top + chartH);
    ctx.closePath();
    ctx.fillStyle = grad;
    ctx.fill();

    // Line
    ctx.beginPath();
    data.forEach((v, i) => {
        if (i === 0) ctx.moveTo(getX(i), getY(v));
        else ctx.lineTo(getX(i), getY(v));
    });
    ctx.strokeStyle = color;
    ctx.lineWidth = 2.5;
    ctx.lineJoin = 'round';
    ctx.lineCap = 'round';
    ctx.stroke();

    // Dots
    if (showDots) {
        data.forEach((v, i) => {
            ctx.beginPath();
            ctx.arc(getX(i), getY(v), 3, 0, Math.PI * 2);
            ctx.fillStyle = color;
            ctx.fill();
        });
    }

    // Labels
    if (labels.length) {
        ctx.fillStyle = '#5a6478';
        ctx.font = '10px Inter, sans-serif';
        ctx.textAlign = 'center';
        labels.forEach((lbl, i) => {
            ctx.fillText(lbl, getX(i), h - 6);
        });
    }
}

// ===== DRAW DOUGHNUT CHART =====
function drawDoughnut(canvasId, segments, centerText = '') {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;

    canvas.width = canvas.offsetWidth * dpr;
    canvas.height = canvas.offsetHeight * dpr;
    ctx.scale(dpr, dpr);

    const w = canvas.offsetWidth;
    const h = canvas.offsetHeight;
    const cx = w / 2;
    const cy = h / 2;
    const radius = Math.min(w, h) / 2 - 12;
    const innerRadius = radius * 0.65;
    const total = segments.reduce((s, seg) => s + seg.value, 0);

    let startAngle = -Math.PI / 2;
    segments.forEach(seg => {
        const sliceAngle = (seg.value / total) * Math.PI * 2;
        ctx.beginPath();
        ctx.arc(cx, cy, radius, startAngle, startAngle + sliceAngle);
        ctx.arc(cx, cy, innerRadius, startAngle + sliceAngle, startAngle, true);
        ctx.closePath();
        ctx.fillStyle = seg.color;
        ctx.fill();
        startAngle += sliceAngle;
    });

    // Center text
    if (centerText) {
        ctx.fillStyle = '#e8ecf4';
        ctx.font = 'bold 16px Inter, sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(centerText, cx, cy);
    }
}

// ===== TAB SWITCHER =====
function initTabSwitcher(containerId, callback) {
    const container = document.getElementById(containerId);
    if (!container) return;
    container.addEventListener('click', (e) => {
        const tab = e.target.closest('.dash-tab');
        if (!tab) return;
        container.querySelectorAll('.dash-tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        if (callback) callback(tab.dataset.tab);
    });
}

// ===== API & BROKER FEEDS MODAL =====
function initApiIntegrationsModal() {
    const targetContainer = document.querySelector('.topbar__right') || document.querySelector('.navbar__actions');
    if (!targetContainer || document.getElementById('apiFeedBadge')) return;

    // Create badge button
    const badge = document.createElement('button');
    badge.id = 'apiFeedBadge';
    badge.className = 'api-feed-badge';
    badge.title = 'Live Market Feeds & Broker Integrations';
    badge.innerHTML = `<span class="api-feed-dot pulse"></span><span>Live Feeds</span>`;

    // Insert before theme toggle if present
    const themeBtn = targetContainer.querySelector('#themeToggleBtn');
    if (themeBtn) {
        targetContainer.insertBefore(badge, themeBtn);
    } else {
        targetContainer.appendChild(badge);
    }

    // Modal Template
    const modalHTML = `
    <div class="api-modal-overlay" id="apiModalOverlay">
        <div class="api-modal">
            <div class="api-modal__header">
                <div class="api-modal__title">
                    <span class="api-feed-dot pulse"></span>
                    Live Feeds & Broker Integration
                </div>
                <button class="api-modal__close" id="apiModalClose">✕</button>
            </div>

            <!-- Binance Card -->
            <div class="api-card">
                <div class="api-card__top">
                    <div class="api-card__name">
                        <span>⚡</span> Binance Exchange (Crypto Feed)
                    </div>
                    <span class="api-status-pill api-status-pill--active" id="binanceStatusPill">CONNECTED</span>
                </div>
                <div class="api-card__desc">
                    Streaming real-time 24h ticker quotes and OHLCV candlestick data directly from Binance Spot API.
                </div>
                <div class="api-card__details">
                    <div class="api-card__detail-item"><span>Status</span><strong style="color:var(--c-accent)">Active & Verified</strong></div>
                    <div class="api-card__detail-item"><span>Trading Mode</span><strong>Spot Execution</strong></div>
                    <div class="api-card__detail-item"><span>Live Pairs</span><strong>BTC, ETH, SOL, BNB</strong></div>
                    <div class="api-card__detail-item"><span>Latency</span><strong style="color:var(--c-accent)">~45ms</strong></div>
                </div>
            </div>

            <!-- Kite Connect Card -->
            <div class="api-card">
                <div class="api-card__top">
                    <div class="api-card__name">
                        <span>🪁</span> Zerodha Kite Connect (Equities & F&O)
                    </div>
                    <span class="api-status-pill api-status-pill--pending" id="kiteStatusPill">KEYS CONFIGURED</span>
                </div>
                <div class="api-card__desc">
                    API Key & Secret are linked. Zerodha requires daily 2FA token generation as per regulatory compliance.
                </div>
                <div class="api-card__details">
                    <div class="api-card__detail-item"><span>API Key</span><strong style="font-family:var(--ff-mono)">40fk...f4z9</strong></div>
                    <div class="api-card__detail-item"><span>Exchange Feed</span><strong>NSE / BSE / NFO</strong></div>
                </div>
                <div class="api-card__actions" style="margin-top: 8px;">
                    <a href="https://kite.zerodha.com/connect/login?api_key=40fk01s422b5f4z9&v=3" target="_blank" class="btn btn--secondary" style="font-size:12px; padding:7px 14px; text-decoration:none;">
                        1. Login with Kite ↗
                    </a>
                    <input type="text" class="api-token-input" id="kiteRequestTokenInput" placeholder="2. Paste request_token here">
                    <button class="btn btn--primary" id="kiteActivateBtn" style="font-size:12px; padding:7px 14px;">
                        Activate
                    </button>
                </div>
                <div id="kiteFeedback" style="font-size:12px; margin-top:8px; display:none;"></div>
            </div>

            <!-- Fallback Engine Card -->
            <div class="api-card" style="margin-bottom:0;">
                <div class="api-card__top">
                    <div class="api-card__name">
                        <span>📈</span> Indian Indices & Stock Feed
                    </div>
                    <span class="api-status-pill api-status-pill--active">LIVE BACKUP ACTIVE</span>
                </div>
                <div class="api-card__desc">
                    Continuously streaming live prices and historical candles for NIFTY 50, SENSEX, BANK NIFTY, RELIANCE, TCS, INFY, etc.
                </div>
            </div>
        </div>
    </div>
    `;

    document.body.insertAdjacentHTML('beforeend', modalHTML);

    const overlay = document.getElementById('apiModalOverlay');
    const closeBtn = document.getElementById('apiModalClose');
    const activateBtn = document.getElementById('kiteActivateBtn');
    const tokenInput = document.getElementById('kiteRequestTokenInput');
    const feedback = document.getElementById('kiteFeedback');

    function openModal() {
        overlay.classList.add('open');
        refreshStatus();
    }

    function closeModal() {
        overlay.classList.remove('open');
    }

    badge.addEventListener('click', openModal);
    closeBtn.addEventListener('click', closeModal);
    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) closeModal();
    });
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && overlay.classList.contains('open')) closeModal();
    });

    async function refreshStatus() {
        if (!window.apiClient) return;
        const status = await window.apiClient.getIntegrationsStatus();
        if (status) {
            const kitePill = document.getElementById('kiteStatusPill');
            if (kitePill && status.zerodha_kite?.access_token_active) {
                kitePill.textContent = 'SESSION ACTIVE';
                kitePill.className = 'api-status-pill api-status-pill--active';
            }
        }
    }

    if (activateBtn) {
        activateBtn.addEventListener('click', async () => {
            const token = tokenInput.value.trim();
            if (!token) {
                feedback.style.display = 'block';
                feedback.style.color = 'var(--c-negative)';
                feedback.textContent = 'Please enter the request_token from the redirect URL';
                return;
            }

            activateBtn.disabled = true;
            activateBtn.textContent = 'Activating...';
            feedback.style.display = 'none';

            try {
                const res = await window.apiClient.setKiteToken({ request_token: token });
                if (res && res.success) {
                    feedback.style.display = 'block';
                    feedback.style.color = 'var(--c-accent)';
                    feedback.textContent = '✓ Kite Session activated! Live data connected.';
                    refreshStatus();
                } else {
                    feedback.style.display = 'block';
                    feedback.style.color = 'var(--c-negative)';
                    feedback.textContent = (res && res.detail) || 'Failed to exchange token. Check expiration.';
                }
            } catch (err) {
                feedback.style.display = 'block';
                feedback.style.color = 'var(--c-negative)';
                feedback.textContent = err.message || 'Error communicating with server';
            } finally {
                activateBtn.disabled = false;
                activateBtn.textContent = 'Activate';
            }
        });
    }
}

// ===== WATCHLIST STORE (shared by all dashboard pages) =====
const WatchlistStore = (() => {
    const STORAGE_KEY = 'ie_watchlist';
    const DEFAULT_SYMBOLS = ['RELIANCE', 'TCS', 'INFY', 'BTCUSDT', 'ETHUSDT'];
    const quoteCache = new Map();
    const changeListeners = new Set();

    function normalize(value) {
        return String(value || '').trim().toUpperCase().replace(/\s+/g, '');
    }

    function read() {
        try {
            const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null');
            if (!Array.isArray(saved)) return [...DEFAULT_SYMBOLS];
            const cleaned = [...new Set(saved.map(normalize).filter(Boolean))];
            return cleaned.length ? cleaned : [...DEFAULT_SYMBOLS];
        } catch (e) {
            return [...DEFAULT_SYMBOLS];
        }
    }

    let symbols = read();

    function emitChange() {
        window.dispatchEvent(new CustomEvent('watchlistchange', { detail: { symbols: [...symbols] } }));
        changeListeners.forEach(fn => {
            try { fn([...symbols]); } catch (e) { console.warn('Watchlist listener error', e); }
        });
    }

    function emitQuotes() {
        window.dispatchEvent(new CustomEvent('watchlistquotes'));
    }

    function persist() {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(symbols));
        emitChange();
    }

    function get() {
        return [...symbols];
    }

    function has(symbol) {
        return symbols.includes(normalize(symbol));
    }

    function add(symbol) {
        const sym = normalize(symbol);
        if (!sym || has(sym)) return false;
        symbols.push(sym);
        persist();
        return true;
    }

    function remove(symbol) {
        const sym = normalize(symbol);
        const before = symbols.length;
        symbols = symbols.filter(s => s !== sym);
        if (symbols.length === before) return false;
        persist();
        return true;
    }

    function toggle(symbol) {
        return has(symbol) ? (remove(symbol), false) : (add(symbol), true);
    }

    async function addVerified(rawSymbol) {
        const sym = normalize(rawSymbol);
        if (!sym) return { ok: false, message: 'Enter a ticker symbol first.' };
        if (has(sym)) return { ok: false, message: `${sym} is already in your watchlist.` };

        try {
            const results = await window.apiClient.searchInstruments(sym) || [];
            const exact = results.find(item => normalize(item.symbol) === sym);
            if (!exact) {
                const suggestion = results.length ? results[0].symbol : null;
                return {
                    ok: false,
                    message: suggestion
                        ? `No verified instrument named ${sym}. Did you mean ${suggestion}?`
                        : `No verified instrument found for ${sym}.`
                };
            }
            add(exact.symbol);
            await refreshQuotes();
            return { ok: true, symbol: exact.symbol, message: `${exact.symbol} added to your watchlist.` };
        } catch (e) {
            return { ok: false, message: `Could not verify ${sym}: ${e.message}` };
        }
    }

    function getQuote(symbol) {
        return quoteCache.get(normalize(symbol)) || null;
    }

    async function refreshQuotes() {
        const missing = get().filter(sym => !quoteCache.has(sym));
        if (missing.length && window.apiClient) {
            await Promise.all(missing.map(async sym => {
                try {
                    const q = await window.apiClient.getQuote(sym);
                    if (q && !q.is_synthetic && q.symbol) quoteCache.set(normalize(q.symbol), q);
                } catch (e) {
                    console.warn(`Watchlist quote unavailable for ${sym}:`, e.message);
                }
            }));
        }
        emitQuotes();
    }

    function onChange(fn) {
        changeListeners.add(fn);
        fn([...symbols]);
        return () => changeListeners.delete(fn);
    }

    function onQuotes(fn) {
        window.addEventListener('watchlistquotes', fn);
        return () => window.removeEventListener('watchlistquotes', fn);
    }

    window.addEventListener('storage', (e) => {
        if (e.key === STORAGE_KEY) {
            symbols = read();
            emitChange();
        }
    });

    if (window.apiClient) {
        window.apiClient.onTick((ticks) => {
            if (!Array.isArray(ticks)) return;
            ticks.forEach(q => {
                if (q && q.symbol) quoteCache.set(normalize(q.symbol), q);
            });
            emitQuotes();
        });
        window.apiClient.connectWebSocket();
    }

    // Generic add/remove buttons anywhere on the app.
    document.addEventListener('click', async (e) => {
        const toggleBtn = e.target.closest('[data-watchlist-toggle]');
        const removeBtn = e.target.closest('[data-watchlist-remove]');
        const btn = toggleBtn || removeBtn;
        if (!btn) return;
        e.preventDefault();
        const sym = normalize(toggleBtn ? toggleBtn.dataset.watchlistToggle : removeBtn.dataset.watchlistRemove);
        if (!sym) return;
        const added = toggleBtn ? toggle(sym) : (remove(sym), false);
        await refreshQuotes();
        if (typeof window.showToast === 'function') {
            window.showToast(added ? `${sym} added to watchlist` : `${sym} removed from watchlist`, 'success');
        }
    });

    return { get, has, add, remove, toggle, addVerified, getQuote, refreshQuotes, onChange, onQuotes };
})();
window.Watchlist = WatchlistStore;

// ===== GLOBAL VERIFIED SYMBOL SEARCH =====
function initGlobalSearch() {
    const selectors = ['#dashSearchInput', '#searchInput', '#analysisSearchInput'];

    selectors.forEach((selector) => {
        const input = document.querySelector(selector);
        if (!input || input.dataset.globalSearchReady) return;
        input.dataset.globalSearchReady = '1';

        const host = input.parentElement || input;
        if (window.getComputedStyle(host).position === 'static') host.style.position = 'relative';

        const dropdown = document.createElement('div');
        dropdown.className = 'global-search-results';
        Object.assign(dropdown.style, {
            position: 'absolute', top: 'calc(100% + 8px)', left: '0', right: '0',
            zIndex: '1200', background: 'var(--c-bg-elevated, #111827)',
            border: '1px solid var(--c-border)', borderRadius: '10px',
            boxShadow: '0 16px 40px rgba(0,0,0,0.35)', display: 'none',
            maxHeight: '340px', overflowY: 'auto'
        });
        host.appendChild(dropdown);

        let items = [];
        let active = -1;
        let timer = null;
        let requestId = 0;

        function hide() {
            dropdown.style.display = 'none';
            active = -1;
        }

        function message(text, color) {
            dropdown.innerHTML = `<div style="padding:13px 14px; font-size:12px; color:${color || 'var(--c-text-secondary)'};">${text}</div>`;
            dropdown.style.display = 'block';
        }

        function render() {
            if (!items.length) {
                message('No verified instrument found for this search.');
                return;
            }
            dropdown.innerHTML = items.map((item, i) => {
                const price = Number.isFinite(Number(item.price))
                    ? Number(item.price).toLocaleString('en-IN', { maximumFractionDigits: 2 })
                    : '—';
                return `
                    <button type="button" class="global-search-result" data-index="${i}" style="display:block; width:100%; text-align:left; border:0; cursor:pointer; padding:10px 14px; background:${i === active ? 'rgba(0,208,156,0.10)' : 'transparent'}; color:var(--c-text-primary); border-bottom:1px solid var(--c-border);">
                        <div style="display:flex; justify-content:space-between; gap:12px;">
                            <strong style="font-family:var(--ff-mono);">${item.symbol}</strong>
                            <span style="font-family:var(--ff-mono); font-size:12px; color:var(--c-accent);">${price}</span>
                        </div>
                        <div style="font-size:11px; color:var(--c-text-secondary); margin-top:3px;">${item.name || ''} · ${item.segment || item.exchange || ''}</div>
                    </button>
                `;
            }).join('');
            dropdown.style.display = 'block';
            dropdown.querySelectorAll('.global-search-result').forEach(btn => {
                btn.addEventListener('click', () => choose(items[Number(btn.dataset.index)]));
            });
        }

        async function search() {
            const q = input.value.trim();
            if (q.length < 2) {
                items = [];
                hide();
                return;
            }
            const myRequest = ++requestId;
            if (!window.apiClient) return;
            try {
                const results = await window.apiClient.searchInstruments(q);
                if (myRequest !== requestId) return;
                items = Array.isArray(results) ? results : [];
                active = items.length ? 0 : -1;
                render();
            } catch (e) {
                if (myRequest !== requestId) return;
                items = [];
                message(`Search unavailable: ${e.message}`, 'var(--c-negative)');
            }
        }

        function choose(item) {
            if (!item || !item.symbol) return;
            const sym = String(item.symbol).toUpperCase().trim();
            hide();
            input.value = sym;
            const url = `analysis.html?symbol=${encodeURIComponent(sym)}`;
            if (window.location.pathname.endsWith('analysis.html')) {
                history.replaceState(null, '', url);
                window.dispatchEvent(new CustomEvent('analysis:symbol', { detail: { symbol: sym } }));
            } else {
                window.location.href = url;
            }
        }

        input.addEventListener('input', () => {
            clearTimeout(timer);
            timer = setTimeout(search, 220);
        });
        input.addEventListener('focus', () => {
            if (items.length) render();
        });
        input.addEventListener('blur', () => setTimeout(hide, 160));
        input.addEventListener('keydown', async (e) => {
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                if (!items.length) await search();
                active = Math.min(items.length - 1, active + 1);
                render();
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                active = Math.max(0, active - 1);
                render();
            } else if (e.key === 'Escape') {
                hide();
            } else if (e.key === 'Enter') {
                e.preventDefault();
                if (active >= 0 && items[active]) return choose(items[active]);
                await search();
                if (items.length) {
                    const typed = input.value.trim().toUpperCase();
                    const exact = items.find(i => i.symbol.toUpperCase() === typed);
                    choose(exact || items[0]);
                } else {
                    message(`No verified instrument named "${input.value.trim()}". Try a symbol like RELIANCE, TCS, or BTCUSDT.`, 'var(--c-negative)');
                }
            }
        });
    });
}

// ===== QUICK TOOLS (SIP CALCULATOR, WATCHLIST, NOTIFICATIONS) =====
function initQuickTools() {
    // 1. SIP Calculator Modal
    if (!document.getElementById('sipModalOverlay')) {
        const sipModalHTML = `
        <div class="api-modal-overlay" id="sipModalOverlay">
            <div class="api-modal" style="max-width: 580px;">
                <div class="api-modal__header">
                    <div class="api-modal__title">
                        <span>📊</span> Systematic Investment Plan (SIP) Calculator
                    </div>
                    <button class="api-modal__close" id="sipModalClose">✕</button>
                </div>
                <div>
                    <div class="sip-slider-group">
                        <div class="sip-slider-header">
                            <span>Monthly Investment</span>
                            <span class="sip-slider-val" id="sipMonthlyVal">₹10,000</span>
                        </div>
                        <input type="range" class="sip-slider-input" id="sipMonthly" min="500" max="100000" step="500" value="10000">
                    </div>

                    <div class="sip-slider-group">
                        <div class="sip-slider-header">
                            <span>Expected Annual Return Rate (p.a)</span>
                            <span class="sip-slider-val" id="sipRateVal">12%</span>
                        </div>
                        <input type="range" class="sip-slider-input" id="sipRate" min="1" max="30" step="0.5" value="12">
                    </div>

                    <div class="sip-slider-group">
                        <div class="sip-slider-header">
                            <span>Time Period</span>
                            <span class="sip-slider-val" id="sipYearsVal">10 Years</span>
                        </div>
                        <input type="range" class="sip-slider-input" id="sipYears" min="1" max="35" step="1" value="10">
                    </div>

                    <div class="sip-results-grid">
                        <div>
                            <div class="sip-res-item__label">Invested Amount</div>
                            <div class="sip-res-item__val" id="sipInvestedRes" style="color:var(--c-text-primary);">₹12,00,000</div>
                        </div>
                        <div>
                            <div class="sip-res-item__label">Estimated Wealth Gain</div>
                            <div class="sip-res-item__val" id="sipGainRes" style="color:var(--c-accent);">₹11,23,391</div>
                        </div>
                        <div>
                            <div class="sip-res-item__label">Total Maturity Value</div>
                            <div class="sip-res-item__val" id="sipTotalRes" style="color:var(--c-accent);">₹23,23,391</div>
                        </div>
                    </div>

                    <div style="margin-top:20px; display:flex; justify-content:flex-end;">
                        <button class="btn btn--primary" onclick="document.getElementById('sipModalOverlay').classList.remove('open')">Done</button>
                    </div>
                </div>
            </div>
        </div>
        `;
        document.body.insertAdjacentHTML('beforeend', sipModalHTML);

        const sipOverlay = document.getElementById('sipModalOverlay');
        const sipClose = document.getElementById('sipModalClose');
        if (sipClose) sipClose.addEventListener('click', () => sipOverlay.classList.remove('open'));
        if (sipOverlay) {
            sipOverlay.addEventListener('click', (e) => {
                if (e.target === sipOverlay) sipOverlay.classList.remove('open');
            });
        }

        const mInput = document.getElementById('sipMonthly');
        const rInput = document.getElementById('sipRate');
        const yInput = document.getElementById('sipYears');

        function updateSip() {
            const p = parseFloat(mInput.value);
            const rate = parseFloat(rInput.value);
            const years = parseInt(yInput.value);

            document.getElementById('sipMonthlyVal').textContent = '₹' + p.toLocaleString('en-IN');
            document.getElementById('sipRateVal').textContent = rate + '%';
            document.getElementById('sipYearsVal').textContent = years + ' Years';

            const i = (rate / 100) / 12;
            const n = years * 12;
            const total = p * ((Math.pow(1 + i, n) - 1) / i) * (1 + i);
            const invested = p * n;
            const gain = Math.max(0, total - invested);

            document.getElementById('sipInvestedRes').textContent = '₹' + Math.round(invested).toLocaleString('en-IN');
            document.getElementById('sipGainRes').textContent = '₹' + Math.round(gain).toLocaleString('en-IN');
            document.getElementById('sipTotalRes').textContent = '₹' + Math.round(total).toLocaleString('en-IN');
        }

        if (mInput && rInput && yInput) {
            mInput.addEventListener('input', updateSip);
            rInput.addEventListener('input', updateSip);
            yInput.addEventListener('input', updateSip);
            updateSip();
        }
    }

    // 2. Watchlist Modal
    if (!document.getElementById('watchlistModalOverlay')) {
        const watchlistModalHTML = `
        <div class="api-modal-overlay" id="watchlistModalOverlay">
            <div class="api-modal" style="max-width: 680px;">
                <div class="api-modal__header">
                    <div class="api-modal__title">
                        <span>⭐</span> My Tracked Watchlist
                    </div>
                    <button class="api-modal__close" id="watchlistModalClose">✕</button>
                </div>
                <div>
                    <div style="display:flex; gap:10px; margin-bottom:8px;">
                        <input type="text" class="api-token-input" id="addWatchlistInput" placeholder="Add verified ticker (e.g. TCS, INFY, BTCUSDT)..." style="font-family:var(--ff-mono);">
                        <button class="btn btn--primary" id="addWatchlistBtn" style="padding:8px 16px; font-size:13px;">+ Add</button>
                    </div>
                    <div id="watchlistStatus" style="font-size:12px; min-height:18px; margin-bottom:12px; color:var(--c-text-secondary);"></div>
                    <div id="watchlistItemsList" style="display:flex; flex-direction:column; gap:8px; max-height:360px; overflow-y:auto;"></div>
                    <div style="font-size:11px; color:var(--c-text-tertiary); margin-top:12px;">
                        Prices update every second from simulated live ticks anchored to verified market quotes. Watchlist is saved in this browser.
                    </div>
                </div>
            </div>
        </div>
        `;
        document.body.insertAdjacentHTML('beforeend', watchlistModalHTML);

        const wOverlay = document.getElementById('watchlistModalOverlay');
        const wClose = document.getElementById('watchlistModalClose');
        if (wClose) wClose.addEventListener('click', () => wOverlay.classList.remove('open'));
        if (wOverlay) {
            wOverlay.addEventListener('click', (e) => {
                if (e.target === wOverlay) wOverlay.classList.remove('open');
            });
        }

        function money(value, sym) {
            if (!Number.isFinite(value)) return '—';
            const prefix = sym.includes('USDT') ? '$' : '₹';
            return prefix + value.toLocaleString('en-IN', {
                minimumFractionDigits: 2,
                maximumFractionDigits: sym.includes('USDT') && value < 10 ? 4 : 2
            });
        }

        function renderWatchlist() {
            const list = document.getElementById('watchlistItemsList');
            const status = document.getElementById('watchlistStatus');
            if (!list) return;

            const items = window.Watchlist.get();
            if (status) {
                const liveCount = items.filter(sym => window.Watchlist.getQuote(sym)).length;
                status.textContent = items.length
                    ? `${items.length} instrument${items.length === 1 ? '' : 's'} tracked · ${liveCount}/${items.length} quotes from verified feed`
                    : 'Your watchlist is empty. Add a verified symbol above.';
            }

            if (!items.length) {
                list.innerHTML = `<div style="padding:24px; text-align:center; color:var(--c-text-tertiary); font-size:13px;">No instruments tracked yet.</div>`;
                return;
            }

            list.innerHTML = items.map(sym => {
                const q = window.Watchlist.getQuote(sym);
                const isPos = q && q.change >= 0;
                const price = q ? money(q.price, sym) : 'Loading…';
                const change = q && Number.isFinite(q.change_pct)
                    ? `${q.change_pct >= 0 ? '+' : ''}${q.change_pct.toFixed(2)}%`
                    : '—';
                const source = q?.source || 'awaiting feed';
                return `
                <div style="display:flex; justify-content:space-between; align-items:center; gap:12px; padding:10px 14px; background:rgba(255,255,255,0.03); border:1px solid var(--c-border); border-radius:var(--r-sm);">
                    <div style="min-width:0;">
                        <div style="font-weight:700; font-family:var(--ff-mono);">${sym}</div>
                        <div style="font-size:11px; color:var(--c-text-tertiary); margin-top:2px;">${q?.name || sym} · ${source}</div>
                    </div>
                    <div style="text-align:right; font-family:var(--ff-mono); font-size:12px;">
                        <div style="font-weight:700;">${price}</div>
                        <div class="${isPos ? 'positive' : 'negative'}">${change}</div>
                    </div>
                    <div style="display:flex; gap:6px; flex-shrink:0;">
                        <a href="analysis.html?cat=${sym.includes('USDT') ? 'crypto' : 'stocks'}&symbol=${sym}" class="btn btn--secondary" style="font-size:11px; padding:4px 8px; text-decoration:none;">Analyze</a>
                        <a href="predictions.html?symbol=${sym}" class="btn btn--secondary" style="font-size:11px; padding:4px 8px; text-decoration:none;">Predict</a>
                        <button class="btn btn--secondary" data-watchlist-remove="${sym}" style="font-size:11px; padding:4px 8px; color:var(--c-negative);">✕</button>
                    </div>
                </div>
                `;
            }).join('');
        }

        const addBtn = document.getElementById('addWatchlistBtn');
        const addInput = document.getElementById('addWatchlistInput');
        const status = document.getElementById('watchlistStatus');

        async function handleAdd() {
            if (!addInput) return;
            const raw = addInput.value.trim();
            if (!raw) {
                if (status) status.textContent = 'Enter a ticker symbol first.';
                return;
            }
            if (addBtn) addBtn.disabled = true;
            if (status) status.textContent = 'Verifying instrument…';
            const result = await window.Watchlist.addVerified(raw);
            if (result.ok) addInput.value = '';
            if (status) status.textContent = result.message;
            if (addBtn) addBtn.disabled = false;
            renderWatchlist();
        }

        if (addBtn) addBtn.addEventListener('click', handleAdd);
        if (addInput) {
            addInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    handleAdd();
                }
            });
        }

        window.Watchlist.onChange(renderWatchlist);
        window.Watchlist.onQuotes(renderWatchlist);
        renderWatchlist();
        window.Watchlist.refreshQuotes();
    }

    // 3. Notifications Popover
    if (!document.getElementById('notifPopover')) {
        const notifHTML = `
        <div class="notif-popover" id="notifPopover">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px; border-bottom:1px solid var(--c-border); padding-bottom:8px;">
                <span style="font-size:13px; font-weight:700;">Recent Market Alerts</span>
                <span style="font-size:11px; color:var(--c-accent); font-weight:600;">3 New</span>
            </div>
            <div class="notif-item">
                <span class="notif-item__dot" style="background:var(--c-accent);"></span>
                <div>
                    <div style="font-weight:600;">Binance Live Spot Active</div>
                    <div style="color:var(--c-text-secondary); margin-top:2px;">Sub-50ms quotes for BTC & ETH verified.</div>
                </div>
            </div>
            <div class="notif-item">
                <span class="notif-item__dot" style="background:var(--c-blue);"></span>
                <div>
                    <div style="font-weight:600;">RELIANCE 7D LSTM Forecast</div>
                    <div style="color:var(--c-text-secondary); margin-top:2px;">Bullish projection with 88% model confidence.</div>
                </div>
            </div>
            <div class="notif-item">
                <span class="notif-item__dot" style="background:var(--c-orange);"></span>
                <div>
                    <div style="font-weight:600;">Zerodha Kite Ready</div>
                    <div style="color:var(--c-text-secondary); margin-top:2px;">One-click login session token exchange available.</div>
                </div>
            </div>
        </div>
        `;
        document.body.insertAdjacentHTML('beforeend', notifHTML);

        const notifBtn = document.querySelector('.topbar__icon-btn');
        const notifPopover = document.getElementById('notifPopover');
        if (notifBtn && notifPopover) {
            notifBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                notifPopover.classList.toggle('open');
            });
            document.addEventListener('click', (e) => {
                if (!notifPopover.contains(e.target) && e.target !== notifBtn) {
                    notifPopover.classList.remove('open');
                }
            });
        }
    }

    // Wire sidebar links for Watchlist and SIP Calculator
    document.querySelectorAll('.sidebar__link').forEach(link => {
        const txt = link.textContent.trim();
        if (txt.includes('Watchlist')) {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const ol = document.getElementById('watchlistModalOverlay');
                if (ol) ol.classList.add('open');
            });
        } else if (txt.includes('SIP Calculator')) {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const ol = document.getElementById('sipModalOverlay');
                if (ol) ol.classList.add('open');
            });
        }
    });
}

// ===== USER SESSION & PROFILE =====
function initUserSession() {
    const userEl = document.querySelector('.sidebar__user');
    if (!userEl) return;

    const user = window.apiClient?.getAuthUser();
    if (user) {
        const avatar = userEl.querySelector('.sidebar__avatar');
        const name = userEl.querySelector('.sidebar__user-name');
        const plan = userEl.querySelector('.sidebar__user-plan');
        if (avatar) avatar.textContent = user.avatar || user.name.slice(0, 2).toUpperCase();
        if (name) name.textContent = user.name;
        if (plan) plan.textContent = user.plan || 'Pro Trader';

        userEl.title = 'Click to log out or manage account';
        userEl.style.cursor = 'pointer';
        userEl.addEventListener('click', () => {
            if (confirm(`Logged in as ${user.name} (${user.email || 'active session'}).\n\nWould you like to log out?`)) {
                window.apiClient.logout();
                window.location.reload();
            }
        });
    } else {
        userEl.title = 'Click to Sign In';
        userEl.style.cursor = 'pointer';
        userEl.addEventListener('click', () => {
            window.location.href = 'login.html?redirect=' + encodeURIComponent(window.location.pathname.split('/').pop() || 'markets.html');
        });
    }
}

// ===== COMMON INIT =====
document.addEventListener('DOMContentLoaded', () => {
    initSidebar();
    initDashSearch();
    initGlobalSearch();
    initApiIntegrationsModal();
    initQuickTools();
    initUserSession();
});



