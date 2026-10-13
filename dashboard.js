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
            <div class="api-modal" style="max-width: 620px;">
                <div class="api-modal__header">
                    <div class="api-modal__title">
                        <span>⭐</span> My Tracked Watchlist
                    </div>
                    <button class="api-modal__close" id="watchlistModalClose">✕</button>
                </div>
                <div>
                    <div style="display:flex; gap:10px; margin-bottom:16px;">
                        <input type="text" class="api-token-input" id="addWatchlistInput" placeholder="Add ticker symbol (e.g. TCS, INFY, SOLUSDT)..." style="font-family:var(--ff-primary);">
                        <button class="btn btn--primary" id="addWatchlistBtn" style="padding:8px 16px; font-size:13px;">+ Add</button>
                    </div>
                    <div id="watchlistItemsList" style="display:flex; flex-direction:column; gap:8px; max-height:360px; overflow-y:auto;">
                        <!-- Rendered by JS -->
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

        let watchlist = JSON.parse(localStorage.getItem('ie_watchlist') || '["RELIANCE", "TCS", "INFY", "BTCUSDT", "ETHUSDT"]');

        function renderWatchlist() {
            const list = document.getElementById('watchlistItemsList');
            if (!list) return;
            list.innerHTML = watchlist.map(sym => `
                <div style="display:flex; justify-content:space-between; align-items:center; padding:10px 14px; background:rgba(255,255,255,0.03); border:1px solid var(--c-border); border-radius:var(--r-sm);">
                    <div style="font-weight:700; font-family:var(--ff-mono);">${sym}</div>
                    <div style="display:flex; gap:8px;">
                        <a href="analysis.html?cat=${sym.includes('USDT') ? 'crypto' : 'stocks'}" class="btn btn--secondary" style="font-size:11px; padding:4px 10px; text-decoration:none;">Analyze</a>
                        <a href="predictions.html?symbol=${sym}" class="btn btn--secondary" style="font-size:11px; padding:4px 10px; text-decoration:none;">Predict</a>
                        <button class="btn btn--secondary" onclick="removeWatchlist('${sym}')" style="font-size:11px; padding:4px 8px; color:var(--c-negative);">✕</button>
                    </div>
                </div>
            `).join('');
        }

        window.removeWatchlist = function(sym) {
            watchlist = watchlist.filter(s => s !== sym);
            localStorage.setItem('ie_watchlist', JSON.stringify(watchlist));
            renderWatchlist();
        };

        const addBtn = document.getElementById('addWatchlistBtn');
        const addInput = document.getElementById('addWatchlistInput');
        if (addBtn && addInput) {
            addBtn.addEventListener('click', () => {
                const s = addInput.value.trim().toUpperCase();
                if (s && !watchlist.includes(s)) {
                    watchlist.push(s);
                    localStorage.setItem('ie_watchlist', JSON.stringify(watchlist));
                    addInput.value = '';
                    renderWatchlist();
                }
            });
        }

        renderWatchlist();
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
    initApiIntegrationsModal();
    initQuickTools();
    initUserSession();
});



