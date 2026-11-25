/**
 * ========================================================
 * INVESTOR'S EYE — Unified Frontend API & WebSocket Client
 * ========================================================
 */

const API_CONFIG = {
    // Automatically detect host or default to port 8000
    BASE_URL: (window.location.port === '8000' || window.location.port === '3000') 
        ? `http://${window.location.hostname}:8000/v1` 
        : '/v1',
    WS_URL: (window.location.port === '8000' || window.location.port === '3000') 
        ? `ws://${window.location.hostname}:8000/ws/stream` 
        : `ws://${window.location.host}/ws/stream`
};

class ApiClient {
    constructor() {
        this.baseUrl = API_CONFIG.BASE_URL;
        this.wsUrl = API_CONFIG.WS_URL;
        this.ws = null;
        this.tickListeners = [];
        this._tickState = new Map();
        this._simTimer = null;
        this._seedPromise = null;
        this._startSimulation();
        window.addEventListener('beforeunload', () => {
            if (this._simTimer) clearInterval(this._simTimer);
        });
    }

    async _fetch(endpoint, options = {}) {
        try {
            return await this._fetchStrict(endpoint, options);
        } catch (error) {
            console.warn(`[API Offline Fallback] ${endpoint}:`, error.message);
            return null;
        }
    }

    async _fetchStrict(endpoint, options = {}) {
        const res = await fetch(`${this.baseUrl}${endpoint}`, {
            headers: {
                'Content-Type': 'application/json',
                ...(options.headers || {})
            },
            ...options
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: res.statusText }));
            throw new Error(err.detail || 'API request failed');
        }
        return await res.json();
    }

    // --- Market & Quotes ---
    async getQuotes() {
        return await this._fetch('/quotes');
    }

    async getQuote(symbol) {
        return await this._fetch(`/quotes/${symbol}`);
    }

    async getIndices() {
        return await this._fetch('/markets/indices');
    }

    async getGlobalIndices() {
        return await this._fetch('/markets/global-indices');
    }

    async searchInstruments(query) {
        return await this._fetchStrict(`/instruments/search?q=${encodeURIComponent(query)}`);
    }

    async getTrending() {
        return await this._fetch('/markets/trending');
    }

    async getCandles(symbol, timeframe = '1d', limit = 30) {
        return await this._fetch(`/candles/${symbol}?timeframe=${timeframe}&limit=${limit}`);
    }

    async getCandlesStrict(symbol, timeframe = '1d', limit = 30) {
        return await this._fetchStrict(`/candles/${symbol}?timeframe=${timeframe}&limit=${limit}`);
    }

    async getFundGrowth() {
        return await this._fetch('/analysis/funds/growth');
    }

    async getFundAnalysis(code) {
        return await this._fetchStrict(`/analysis/funds/${encodeURIComponent(code)}`);
    }

    async getBreadth() {
        return await this._fetch('/markets/breadth');
    }

    async getFiiDii() {
        return await this._fetch('/markets/fii-dii');
    }

    async getSectors() {
        return await this._fetch('/markets/sectors');
    }

    async getStocksCatalog() {
        return await this._fetch('/markets/stocks');
    }

    async getCryptoCatalog() {
        return await this._fetch('/markets/crypto');
    }

    async getCurrenciesCatalog() {
        return await this._fetch('/markets/currencies');
    }

    async getMutualFunds() {
        return await this._fetch('/markets/mutual-funds');
    }

    async searchMutualFunds(query) {
        return await this._fetch(`/markets/mutual-funds/search?q=${encodeURIComponent(query)}`);
    }

    // --- Analysis ---
    async getTechnicalAnalysis(symbol) {
        return await this._fetch(`/analysis/technical/${symbol}`);
    }

    async getOptionChain(underlying = 'NIFTY') {
        return await this._fetch(`/analysis/option-chain?underlying=${underlying}`);
    }

    async getFundAnalysis(code = 'PPFCF') {
        return await this._fetch(`/analysis/funds/${code}`);
    }

    async getCryptoAnalysis(symbol = 'BTCINR') {
        return await this._fetch(`/analysis/crypto/${symbol}`);
    }

    // --- Learning & Quizzes ---
    async getCourses() {
        return await this._fetch('/learn/courses');
    }

    async getQuiz() {
        return await this._fetch('/learn/quiz');
    }

    async submitQuizAnswer(questionId, selectedOption) {
        return await this._fetchStrict('/learn/quiz/answer', {
            method: 'POST',
            body: JSON.stringify({ question_id: questionId, selected_option: selectedOption })
        });
    }

    // --- LSTM Predictions ---
    async getPrediction(symbol, horizon = 7, model = 'lstm') {
        return await this._fetchStrict(`/predictions/${symbol}?horizon=${horizon}&model=${model}`);
    }

    async getBacktest(symbol, model = 'lstm') {
        return await this._fetch(`/predictions/${symbol}/backtest?model=${model}`);
    }

    // --- Mock / Paper Trading ---
    async getPaperPortfolio() {
        return await this._fetch('/paper/portfolio');
    }

    async getPaperPortfolioStrict() {
        return await this._fetchStrict('/paper/portfolio');
    }

    async placePaperOrder(order) {
        return await this._fetch('/paper/orders', {
            method: 'POST',
            body: JSON.stringify(order)
        });
    }

    async placePaperOrderStrict(order) {
        return await this._fetchStrict('/paper/orders', {
            method: 'POST',
            body: JSON.stringify(order)
        });
    }

    async squareOffPaper(symbol, product = 'CNC', clientOrderId = null, createdAt = null, price = null) {
        const params = new URLSearchParams({ symbol, product });
        if (clientOrderId) params.set('client_order_id', clientOrderId);
        if (createdAt) params.set('created_at', createdAt);
        if (price !== null && price !== undefined) params.set('price', String(price));
        return await this._fetch(`/paper/square-off?${params}`, { method: 'POST' });
    }

    async squareOffPaperStrict(symbol, product = 'CNC', clientOrderId = null, createdAt = null, price = null) {
        const params = new URLSearchParams({ symbol, product });
        if (clientOrderId) params.set('client_order_id', clientOrderId);
        if (createdAt) params.set('created_at', createdAt);
        if (price !== null && price !== undefined) params.set('price', String(price));
        return await this._fetchStrict(`/paper/square-off?${params}`, { method: 'POST' });
    }

    async resetPaperPortfolio() {
        return await this._fetch('/paper/reset', {
            method: 'POST'
        });
    }

    async resetPaperPortfolioStrict() {
        return await this._fetchStrict('/paper/reset', {
            method: 'POST'
        });
    }

    // --- Trades & Unified Book ---
    async getTrades(broker = null) {
        const query = broker ? `?broker=${broker}` : '';
        return await this._fetch(`/trades${query}`);
    }

    async getHoldings() {
        return await this._fetch('/portfolio/holdings');
    }

    async connectBroker(brokerName, clientId) {
        return await this._fetch('/brokers/connect', {
            method: 'POST',
            body: JSON.stringify({ broker_name: brokerName, client_id: clientId })
        });
    }

    // --- Alerts ---
    async getAlerts() {
        return await this._fetch('/alerts');
    }

    async createAlert(rule) {
        return await this._fetch('/alerts', {
            method: 'POST',
            body: JSON.stringify(rule)
        });
    }

    async deleteAlert(ruleId) {
        return await this._fetch(`/alerts/${ruleId}`, {
            method: 'DELETE'
        });
    }

    // --- Integrations (Kite & Binance) ---
    async getIntegrationsStatus() {
        return await this._fetch('/integrations/status');
    }

    async getKiteLoginUrl() {
        return await this._fetch('/integrations/kite/login-url');
    }

    async setKiteToken(payload) {
        return await this._fetch('/integrations/kite/token', {
            method: 'POST',
            body: JSON.stringify(payload)
        });
    }

    async getBinanceAccount() {
        return await this._fetch('/integrations/binance/account');
    }

    // --- Authentication & User Session ---
    async login(usernameOrEmail, password) {
        const res = await this._fetch('/auth/login', {
            method: 'POST',
            body: JSON.stringify({ username_or_email: usernameOrEmail, password: password })
        });
        if (res && res.success) {
            this.setAuthSession(res.access_token, res.user);
        }
        return res;
    }

    async register(name, email, password) {
        const res = await this._fetch('/auth/register', {
            method: 'POST',
            body: JSON.stringify({ name, email, password })
        });
        if (res && res.success) {
            this.setAuthSession(res.access_token, res.user);
        }
        return res;
    }

    getAuthUser() {
        try {
            const raw = localStorage.getItem('ie_auth_user');
            return raw ? JSON.parse(raw) : null;
        } catch (e) {
            return null;
        }
    }

    setAuthSession(token, user) {
        try {
            localStorage.setItem('ie_auth_token', token);
            localStorage.setItem('ie_auth_user', JSON.stringify(user));
        } catch (e) {
            console.warn('Storage error', e);
        }
    }

    logout() {
        try {
            localStorage.removeItem('ie_auth_token');
            localStorage.removeItem('ie_auth_user');
        } catch (e) {}
    }

    // --- Real-time WebSocket + 1-second live tick engine ---
    onTick(callback) {
        this.tickListeners.push(callback);
        this._startSimulation();
        return () => {
            this.tickListeners = this.tickListeners.filter(cb => cb !== callback);
        };
    }

    _startSimulation() {
        if (this._simTimer) return;
        this._simTimer = setInterval(() => {
            if (!this._tickState.size) this._seedTickStateFromApi();
            this._emitSimulatedTicks();
        }, 1000);
    }

    _volatilityFor(symbol) {
        const s = String(symbol || '').toUpperCase();
        if (s.endsWith('USDT') || ['BTC', 'ETH', 'SOL', 'DOGE', 'ADA', 'AVAX', 'XRP'].includes(s)) return 0.00055;
        if (s.includes('NIFTY') || s.includes('SENSEX')) return 0.00018;
        return 0.00032;
    }

    _normaliseQuote(q) {
        if (!q || !q.symbol || !Number.isFinite(Number(q.price)) || Number(q.price) <= 0) return null;
        const symbol = String(q.symbol).toUpperCase().trim();
        const price = Number(q.price);
        const change = Number.isFinite(Number(q.change)) ? Number(q.change) : 0;
        const previousClose = Math.max(0.01, price - change);
        return {
            symbol,
            name: q.name || symbol,
            source: q.source || 'verified feed',
            price,
            change,
            change_pct: Number.isFinite(Number(q.change_pct))
                ? Number(q.change_pct)
                : (previousClose ? (change / previousClose) * 100 : 0),
            high_24h: Number.isFinite(Number(q.high_24h)) ? Number(q.high_24h) : price,
            low_24h: Number.isFinite(Number(q.low_24h)) ? Number(q.low_24h) : price,
            volume: q.volume,
            previousClose
        };
    }

    _ingestRealQuotes(quotes, type = 'TICK', dispatch = true) {
        const now = Date.now();
        const clean = (Array.isArray(quotes) ? quotes : [])
            .map(q => this._normaliseQuote(q))
            .filter(Boolean);

        const dispatchable = [];
        clean.forEach(q => {
            const existing = this._tickState.get(q.symbol);
            const unchanged = existing && Math.abs(existing.anchor - q.price) < 0.005 && type !== 'INITIAL_SNAPSHOT';
            this._tickState.set(q.symbol, {
                ...q,
                current: unchanged ? existing.current : q.price,
                anchor: q.price,
                volatility: existing?.volatility || this._volatilityFor(q.symbol),
                updatedAt: now
            });
            if (!unchanged) dispatchable.push(q);
        });

        if (dispatch && dispatchable.length) {
            const batch = dispatchable.map(q => ({
                symbol: q.symbol,
                name: q.name,
                price: q.price,
                change: q.change,
                change_pct: q.change_pct,
                high_24h: q.high_24h,
                low_24h: q.low_24h,
                volume: q.volume,
                source: q.source,
                verified_source: q.source,
                tick_source: 'verified_snapshot',
                is_simulated: false,
                simulated: false
            }));
            this._dispatchTicks(batch, type);
        }
    }

    async _seedTickStateFromApi() {
        if (this._tickState.size) return;
        if (this._seedPromise) return this._seedPromise;
        this._seedPromise = Promise.all([
            this.getStocksCatalog(),
            this.getCryptoCatalog(),
            this.getIndices(),
            this.getCurrenciesCatalog(),
            this.getGlobalIndices()
        ]).then(([stocks, crypto, indices, currencies, globalIndices]) => {
            const quotes = [];
            (Array.isArray(stocks) ? stocks : []).forEach(s => quotes.push({
                symbol: s.symbol,
                name: s.name,
                price: s.price,
                change: s.change,
                change_pct: s.change_pct,
                high_24h: s.high_24h,
                low_24h: s.low_24h,
                volume: s.volume,
                source: s.api_source || 'verified feed'
            }));
            (Array.isArray(crypto) ? crypto : []).forEach(s => quotes.push({
                symbol: s.symbol,
                name: s.name,
                price: s.price,
                change: s.change,
                change_pct: s.change_pct,
                high_24h: s.high_24h,
                low_24h: s.low_24h,
                volume: s.volume,
                source: s.api_source || 'Binance Spot API'
            }));
            (Array.isArray(indices) ? indices : []).forEach(s => quotes.push({
                symbol: s.name,
                name: s.name,
                price: s.value,
                change: s.change,
                change_pct: s.change_pct,
                source: 'Verified index feed'
            }));
            (Array.isArray(currencies) ? currencies : []).forEach(s => quotes.push({
                symbol: s.symbol,
                name: s.name,
                price: s.price,
                change: s.change,
                change_pct: s.change_pct,
                source: s.api_source || 'Verified FX feed'
            }));
            (Array.isArray(globalIndices) ? globalIndices : []).forEach(s => quotes.push({
                symbol: s.name,
                name: s.name,
                price: s.value,
                change: s.change,
                change_pct: s.change_pct,
                source: 'Verified global index feed'
            }));
            this._ingestRealQuotes(quotes, 'INITIAL_SNAPSHOT', true);
        }).catch(e => {
            console.warn('Tick seed from REST catalogues failed:', e.message);
        }).finally(() => {
            this._seedPromise = null;
        });
        return this._seedPromise;
    }

    getLiveQuote(symbol) {
        const s = this._tickState.get(String(symbol || '').toUpperCase().trim());
        if (!s) return null;
        const change = Math.round((s.current - s.previousClose) * 100) / 100;
        return {
            symbol: s.symbol,
            name: s.name,
            price: s.current,
            change,
            change_pct: s.previousClose ? Math.round((change / s.previousClose) * 10000) / 100 : 0,
            high_24h: Math.max(s.high_24h || s.current, s.current),
            low_24h: Math.min(s.low_24h || s.current, s.current),
            volume: s.volume,
            source: `Simulated live (${s.source})`,
            verified_source: s.source,
            tick_source: 'simulated_live',
            is_simulated: true,
            simulated: true
        };
    }

    _dispatchTicks(batch, type) {
        this.tickListeners.forEach(cb => {
            try {
                cb(batch, type);
            } catch (e) {
                console.error('Tick listener error', e);
            }
        });
    }

    _emitSimulatedTicks() {
        if (!this._tickState.size) return;
        const now = Date.now();
        const batch = [];

        this._tickState.forEach((s, symbol) => {
            const anchor = s.anchor || s.price;
            const pull = ((anchor - s.current) / anchor) * 0.06;
            const noise = (Math.random() - 0.5) * 2 * s.volatility;
            let delta = s.current * (pull + noise);
            const minTick = anchor >= 1000 ? 0.05 : 0.01;
            if (Math.abs(delta) < minTick) delta = (delta >= 0 ? 1 : -1) * minTick;

            let next = s.current + delta;
            next = Math.min(anchor * 1.015, Math.max(anchor * 0.985, next));
            next = Math.round(next * 100) / 100;
            s.current = next;
            s.updatedAt = now;

            const change = Math.round((next - s.previousClose) * 100) / 100;
            const changePct = s.previousClose
                ? Math.round((change / s.previousClose) * 10000) / 100
                : 0;

            batch.push({
                symbol,
                name: s.name,
                price: next,
                change,
                change_pct: changePct,
                high_24h: Math.max(s.high_24h || next, next),
                low_24h: Math.min(s.low_24h || next, next),
                volume: s.volume,
                source: `Simulated live (${s.source})`,
                verified_source: s.source,
                anchor_price: anchor,
                tick_source: 'simulated_live',
                is_simulated: true,
                simulated: true,
                timestamp: now
            });
        });

        if (batch.length) this._dispatchTicks(batch, 'SIMULATED_TICK');
    }

    connectWebSocket() {
        this._startSimulation();
        try {
            if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
                return;
            }
            this.ws = new WebSocket(this.wsUrl);
            this.ws.onopen = () => {
                console.log('⚡ Connected to Investor\'s EYE Live WebSocket');
                this._seedTickStateFromApi();
            };
            this.ws.onmessage = (event) => {
                try {
                    const msg = JSON.parse(event.data);
                    if ((msg.type === 'TICK' || msg.type === 'INITIAL_SNAPSHOT') && Array.isArray(msg.data)) {
                        this._ingestRealQuotes(msg.data, msg.type, true);
                    }
                } catch (e) {
                    console.error('WS Parse error', e);
                }
            };
            this.ws.onerror = (e) => {
                console.warn('WS error (simulated ticks will continue):', e);
            };
            this.ws.onclose = () => {
                setTimeout(() => this.connectWebSocket(), 5000);
            };
        } catch (e) {
            console.warn('WebSocket unavailable; simulated ticks will continue:', e);
            this._seedTickStateFromApi();
        }
    }
}

// Global singleton instance
window.apiClient = new ApiClient();
