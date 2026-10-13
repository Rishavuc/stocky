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
    }

    async _fetch(endpoint, options = {}) {
        try {
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
        } catch (error) {
            console.warn(`[API Offline Fallback] ${endpoint}:`, error.message);
            return null;
        }
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

    async getTrending() {
        return await this._fetch('/markets/trending');
    }

    async getCandles(symbol, timeframe = '1d', limit = 30) {
        return await this._fetch(`/candles/${symbol}?timeframe=${timeframe}&limit=${limit}`);
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

    // --- LSTM Predictions ---
    async getPrediction(symbol, horizon = 7) {
        return await this._fetch(`/predictions/${symbol}?horizon=${horizon}`);
    }

    async getBacktest(symbol) {
        return await this._fetch(`/predictions/${symbol}/backtest`);
    }

    // --- Mock / Paper Trading ---
    async getPaperPortfolio() {
        return await this._fetch('/paper/portfolio');
    }

    async placePaperOrder(order) {
        return await this._fetch('/paper/orders', {
            method: 'POST',
            body: JSON.stringify(order)
        });
    }

    async squareOffPaper(symbol, product = 'CNC') {
        return await this._fetch(`/paper/square-off?symbol=${symbol}&product=${product}`, {
            method: 'POST'
        });
    }

    async resetPaperPortfolio() {
        return await this._fetch('/paper/reset', {
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

    // --- Real-time WebSocket ---
    onTick(callback) {
        this.tickListeners.push(callback);
    }

    connectWebSocket() {
        try {
            this.ws = new WebSocket(this.wsUrl);
            this.ws.onopen = () => {
                console.log('⚡ Connected to Investor\'s EYE Live WebSocket');
            };
            this.ws.onmessage = (event) => {
                try {
                    const msg = JSON.parse(event.data);
                    if (msg.type === 'TICK' && Array.isArray(msg.data)) {
                        this.tickListeners.forEach(cb => cb(msg.data));
                    }
                } catch (e) {
                    console.error('WS Parse error', e);
                }
            };
            this.ws.onerror = (e) => {
                console.warn('WS error (will retry or use fallback ticks):', e);
            };
            this.ws.onclose = () => {
                setTimeout(() => this.connectWebSocket(), 5000);
            };
        } catch (e) {
            console.warn('WebSocket unavailable in current context:', e);
        }
    }
}

// Global singleton instance
window.apiClient = new ApiClient();
