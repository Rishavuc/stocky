/* =============================================
   INVESTOR'S EYE — Interactive JavaScript
   ============================================= */

document.addEventListener('DOMContentLoaded', () => {

    // ===== TICKER DATA =====
    const tickerData = [
        { name: 'NIFTY 50', value: '22,456.80', change: '+1.24%', positive: true },
        { name: 'SENSEX', value: '73,890.45', change: '+0.98%', positive: true },
        { name: 'BANK NIFTY', value: '47,234.15', change: '-0.42%', positive: false },
        { name: 'NIFTY IT', value: '34,567.20', change: '+2.15%', positive: true },
        { name: 'NIFTY FIN', value: '20,890.30', change: '+0.76%', positive: true },
        { name: 'MIDCAP 50', value: '13,456.90', change: '-0.31%', positive: false },
        { name: 'GOLD', value: '₹62,450', change: '+0.85%', positive: true },
        { name: 'USD/INR', value: '83.24', change: '-0.12%', positive: false },
        { name: 'CRUDE OIL', value: '$78.90', change: '-1.45%', positive: false },
        { name: 'BTC/USD', value: '$67,240', change: '+3.21%', positive: true },
        { name: 'ETH/USD', value: '$3,180', change: '-0.85%', positive: false },
        { name: 'NIFTY PHARMA', value: '17,892.45', change: '+1.56%', positive: true },
    ];

    function initTicker() {
        const track = document.getElementById('tickerTrack');
        if (!track) return;

        const renderTrack = () => {
            const itemsHTML = tickerData.map(item => `
                <div class="ticker-item">
                    <span class="ticker-item__name">${item.name}</span>
                    <span>${item.value}</span>
                    <span class="ticker-item__change ${item.positive ? 'positive' : 'negative'}">${item.change}</span>
                </div>
            `).join('');
            track.innerHTML = itemsHTML + itemsHTML;
        };

        renderTrack();

        // Hydrate ticker with real live Binance & NSE data
        if (window.apiClient) {
            Promise.all([
                window.apiClient.getIndices(),
                window.apiClient.getQuote('BTCUSDT'),
                window.apiClient.getQuote('ETHUSDT')
            ]).then(([indices, btc, eth]) => {
                if (indices && indices.length > 0) {
                    indices.forEach(idx => {
                        const target = tickerData.find(t => t.name === idx.name);
                        if (target) {
                            target.value = idx.value.toLocaleString('en-IN');
                            target.change = (idx.change_pct > 0 ? '+' : '') + idx.change_pct + '%';
                            target.positive = idx.positive;
                        }
                    });
                }
                if (btc) {
                    const btcTarget = tickerData.find(t => t.name.includes('BTC'));
                    if (btcTarget) {
                        btcTarget.value = '$' + btc.price.toLocaleString('en-IN');
                        btcTarget.change = (btc.change_pct > 0 ? '+' : '') + btc.change_pct + '%';
                        btcTarget.positive = btc.change >= 0;
                    }
                }
                if (eth) {
                    const ethTarget = tickerData.find(t => t.name.includes('ETH'));
                    if (ethTarget) {
                        ethTarget.value = '$' + eth.price.toLocaleString('en-IN');
                        ethTarget.change = (eth.change_pct > 0 ? '+' : '') + eth.change_pct + '%';
                        ethTarget.positive = eth.change >= 0;
                    }
                }
                renderTrack();
            }).catch(() => {});
        }
    }

    // ===== NAVBAR SCROLL EFFECT =====
    function initNavbarScroll() {
        const navbar = document.getElementById('navbar');
        let lastScroll = 0;

        window.addEventListener('scroll', () => {
            const currentScroll = window.scrollY;
            navbar.classList.toggle('scrolled', currentScroll > 50);
            lastScroll = currentScroll;
        });
    }

    // ===== MOBILE NAV =====
    function initMobileNav() {
        const hamburger = document.getElementById('navHamburger');
        const navMenu = document.getElementById('navMenu');

        hamburger.addEventListener('click', () => {
            navMenu.classList.toggle('open');
            hamburger.classList.toggle('active');
        });

        // Close on link click
        navMenu.querySelectorAll('.navbar__link').forEach(link => {
            link.addEventListener('click', () => {
                navMenu.classList.remove('open');
                hamburger.classList.remove('active');
            });
        });
    }

    // ===== MINI CHARTS (Canvas sparklines) =====
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

        // Fill gradient
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
        // Close path for fill
        ctx.lineTo(w - padding, h);
        ctx.lineTo(padding, h);
        ctx.closePath();
        ctx.fillStyle = grad;
        ctx.fill();

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

    function initHeroCharts() {
        const niftyData = generateChartData(22300, 50, 40, 'up');
        const sensexData = generateChartData(73500, 150, 40, 'up');
        const bankNiftyData = generateChartData(47400, 80, 40, 'down');

        drawSparkline('heroChartNifty', niftyData, '#00d09c', 'rgba(0, 208, 156, 0.1)');
        drawSparkline('heroChartSensex', sensexData, '#00d09c', 'rgba(0, 208, 156, 0.1)');
        drawSparkline('heroChartBankNifty', bankNiftyData, '#ff5252', 'rgba(255, 82, 82, 0.1)');
    }

    // ===== MARKET INDICES =====
    const indicesData = {
        indian: [
            { name: 'NIFTY 50', value: '22,456.80', change: '+278.45', pct: '+1.24%', positive: true, trend: 'up' },
            { name: 'SENSEX', value: '73,890.45', change: '+718.32', pct: '+0.98%', positive: true, trend: 'up' },
            { name: 'BANK NIFTY', value: '47,234.15', change: '-198.70', pct: '-0.42%', positive: false, trend: 'down' },
            { name: 'NIFTY IT', value: '34,567.20', change: '+728.15', pct: '+2.15%', positive: true, trend: 'up' },
            { name: 'NIFTY FIN SVC', value: '20,890.30', change: '+157.40', pct: '+0.76%', positive: true, trend: 'up' },
            { name: 'NIFTY MIDCAP', value: '48,123.60', change: '-152.30', pct: '-0.31%', positive: false, trend: 'down' },
            { name: 'NIFTY PHARMA', value: '17,892.45', change: '+274.80', pct: '+1.56%', positive: true, trend: 'up' },
            { name: 'INDIA VIX', value: '12.45', change: '-0.89', pct: '-6.68%', positive: true, trend: 'down' },
        ],
        global: [
            { name: 'S&P 500', value: '5,234.18', change: '+42.15', pct: '+0.81%', positive: true, trend: 'up' },
            { name: 'NASDAQ', value: '16,456.20', change: '+198.30', pct: '+1.22%', positive: true, trend: 'up' },
            { name: 'DOW JONES', value: '39,127.80', change: '-89.45', pct: '-0.23%', positive: false, trend: 'down' },
            { name: 'FTSE 100', value: '8,124.90', change: '+34.20', pct: '+0.42%', positive: true, trend: 'up' },
            { name: 'DAX', value: '18,456.70', change: '+156.30', pct: '+0.85%', positive: true, trend: 'up' },
            { name: 'NIKKEI 225', value: '39,890.20', change: '-234.10', pct: '-0.58%', positive: false, trend: 'down' },
            { name: 'HANG SENG', value: '17,234.80', change: '+187.40', pct: '+1.10%', positive: true, trend: 'up' },
            { name: 'SHANGHAI', value: '3,089.45', change: '+12.30', pct: '+0.40%', positive: true, trend: 'up' },
        ],
        crypto: [
            { name: 'BITCOIN', value: '$67,240.50', change: '+$2,089', pct: '+3.21%', positive: true, trend: 'up' },
            { name: 'ETHEREUM', value: '$3,180.20', change: '-$27.40', pct: '-0.85%', positive: false, trend: 'down' },
            { name: 'SOLANA', value: '$178.90', change: '+$12.30', pct: '+7.38%', positive: true, trend: 'up' },
            { name: 'BNB', value: '$598.40', change: '+$8.90', pct: '+1.51%', positive: true, trend: 'up' },
            { name: 'XRP', value: '$0.5824', change: '+$0.018', pct: '+3.19%', positive: true, trend: 'up' },
            { name: 'CARDANO', value: '$0.4521', change: '-$0.012', pct: '-2.58%', positive: false, trend: 'down' },
            { name: 'DOGECOIN', value: '$0.1234', change: '+$0.008', pct: '+6.93%', positive: true, trend: 'up' },
            { name: 'POLYGON', value: '$0.7823', change: '+$0.032', pct: '+4.26%', positive: true, trend: 'up' },
        ]
    };

    function renderIndices(tab) {
        const grid = document.getElementById('indicesGrid');
        const data = indicesData[tab] || indicesData.indian;

        grid.innerHTML = data.map((item, i) => {
            const canvasId = `indexChart_${tab}_${i}`;
            return `
                <div class="index-card reveal" style="transition-delay: ${i * 50}ms">
                    <div class="index-card__header">
                        <span class="index-card__name">${item.name}</span>
                        <span class="index-card__badge ${item.positive ? 'positive' : 'negative'}">${item.pct}</span>
                    </div>
                    <div class="index-card__value">${item.value}</div>
                    <div class="index-card__change ${item.positive ? 'positive' : 'negative'}">${item.change} (${item.pct})</div>
                    <canvas class="index-card__chart" id="${canvasId}"></canvas>
                </div>
            `;
        }).join('');

        // Draw charts after DOM update
        requestAnimationFrame(() => {
            data.forEach((item, i) => {
                const canvasId = `indexChart_${tab}_${i}`;
                const chartData = generateChartData(1000, 20, 30, item.trend);
                const color = item.positive ? '#00d09c' : '#ff5252';
                const fill = item.positive ? 'rgba(0, 208, 156, 0.08)' : 'rgba(255, 82, 82, 0.08)';
                drawSparkline(canvasId, chartData, color, fill);
            });

            // Trigger reveal
            setTimeout(() => {
                grid.querySelectorAll('.reveal').forEach(el => el.classList.add('visible'));
            }, 50);
        });
    }

    function initMarketTabs() {
        const tabContainer = document.getElementById('marketTabs');
        tabContainer.addEventListener('click', (e) => {
            if (!e.target.classList.contains('tab')) return;
            tabContainer.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            e.target.classList.add('active');
            renderIndices(e.target.dataset.tab);
        });

        renderIndices('indian');
    }

    // ===== TRENDING STOCKS TABLE =====
    const stocksData = {
        gainers: [
            { symbol: 'TATAMOTORS', company: 'Tata Motors Ltd', ltp: 987.45, change: 68.90, pct: 7.50, volume: '42.3M', positive: true },
            { symbol: 'INFY', company: 'Infosys Ltd', ltp: 1678.30, change: 89.15, pct: 5.61, volume: '28.7M', positive: true },
            { symbol: 'ADANIENT', company: 'Adani Enterprises', ltp: 2890.60, change: 134.20, pct: 4.87, volume: '15.2M', positive: true },
            { symbol: 'TCS', company: 'Tata Consultancy', ltp: 4123.80, change: 178.45, pct: 4.52, volume: '12.8M', positive: true },
            { symbol: 'WIPRO', company: 'Wipro Ltd', ltp: 478.90, change: 18.35, pct: 3.98, volume: '31.5M', positive: true },
            { symbol: 'HDFCBANK', company: 'HDFC Bank Ltd', ltp: 1567.20, change: 52.40, pct: 3.46, volume: '22.1M', positive: true },
            { symbol: 'RELIANCE', company: 'Reliance Industries', ltp: 2456.70, change: 78.90, pct: 3.32, volume: '18.9M', positive: true },
            { symbol: 'BAJFINANCE', company: 'Bajaj Finance', ltp: 6789.30, change: 198.60, pct: 3.01, volume: '8.4M', positive: true },
        ],
        losers: [
            { symbol: 'COALINDIA', company: 'Coal India Ltd', ltp: 432.10, change: -28.90, pct: -6.27, volume: '35.6M', positive: false },
            { symbol: 'ONGC', company: 'Oil & Natural Gas', ltp: 267.80, change: -14.20, pct: -5.04, volume: '29.3M', positive: false },
            { symbol: 'BPCL', company: 'Bharat Petroleum', ltp: 534.60, change: -24.30, pct: -4.35, volume: '18.7M', positive: false },
            { symbol: 'NTPC', company: 'NTPC Ltd', ltp: 356.90, change: -14.80, pct: -3.98, volume: '24.1M', positive: false },
            { symbol: 'POWERGRID', company: 'Power Grid Corp', ltp: 278.40, change: -10.20, pct: -3.53, volume: '15.8M', positive: false },
            { symbol: 'SUNPHARMA', company: 'Sun Pharma', ltp: 1234.50, change: -38.70, pct: -3.04, volume: '11.2M', positive: false },
            { symbol: 'DRREDDY', company: "Dr Reddy's Labs", ltp: 5678.90, change: -156.30, pct: -2.68, volume: '5.4M', positive: false },
            { symbol: 'CIPLA', company: 'Cipla Ltd', ltp: 1345.20, change: -32.80, pct: -2.38, volume: '9.7M', positive: false },
        ],
        active: [
            { symbol: 'TATASTEEL', company: 'Tata Steel Ltd', ltp: 145.60, change: 4.80, pct: 3.41, volume: '98.5M', positive: true },
            { symbol: 'SBIN', company: 'State Bank of India', ltp: 789.30, change: -8.90, pct: -1.11, volume: '78.2M', positive: false },
            { symbol: 'ITC', company: 'ITC Ltd', ltp: 456.70, change: 12.30, pct: 2.77, volume: '65.4M', positive: true },
            { symbol: 'TATAMOTORS', company: 'Tata Motors Ltd', ltp: 987.45, change: 68.90, pct: 7.50, volume: '42.3M', positive: true },
            { symbol: 'VEDL', company: 'Vedanta Ltd', ltp: 312.80, change: -5.60, pct: -1.76, volume: '56.7M', positive: false },
            { symbol: 'HINDALCO', company: 'Hindalco Inds', ltp: 567.20, change: 18.90, pct: 3.45, volume: '41.2M', positive: true },
            { symbol: 'JSWSTEEL', company: 'JSW Steel Ltd', ltp: 834.90, change: -12.40, pct: -1.46, volume: '38.9M', positive: false },
            { symbol: 'COALINDIA', company: 'Coal India Ltd', ltp: 432.10, change: -28.90, pct: -6.27, volume: '35.6M', positive: false },
        ]
    };

    function renderStocksTable(tab) {
        const tbody = document.getElementById('stocksTableBody');
        const data = stocksData[tab] || stocksData.gainers;

        tbody.innerHTML = data.map((stock, i) => {
            const canvasId = `sparkline_${tab}_${i}`;
            return `
                <tr>
                    <td>
                        <div class="stock-name">
                            <span class="stock-name__symbol">${stock.symbol}</span>
                            <span class="stock-name__company">${stock.company}</span>
                        </div>
                    </td>
                    <td><span class="stock-ltp">₹${stock.ltp.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span></td>
                    <td><span class="stock-change ${stock.positive ? 'positive' : 'negative'}">${stock.positive ? '+' : ''}${stock.change.toFixed(2)}</span></td>
                    <td><span class="stock-change ${stock.positive ? 'positive' : 'negative'}">${stock.positive ? '+' : ''}${stock.pct.toFixed(2)}%</span></td>
                    <td><span class="stock-volume">${stock.volume}</span></td>
                    <td><canvas class="stock-sparkline" id="${canvasId}"></canvas></td>
                    <td><button class="stock-analyze-btn">Analyze</button></td>
                </tr>
            `;
        }).join('');

        // Draw sparklines
        requestAnimationFrame(() => {
            data.forEach((stock, i) => {
                const canvasId = `sparkline_${tab}_${i}`;
                const chartData = generateChartData(100, 5, 20, stock.positive ? 'up' : 'down');
                const color = stock.positive ? '#00d09c' : '#ff5252';
                drawSparkline(canvasId, chartData, color, 'transparent');
            });
        });
    }

    function initTrendingTabs() {
        const tabContainer = document.getElementById('trendingTabs');
        tabContainer.addEventListener('click', (e) => {
            if (!e.target.classList.contains('tab')) return;
            tabContainer.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            e.target.classList.add('active');
            renderStocksTable(e.target.dataset.tab);
        });

        renderStocksTable('gainers');
    }

    // ===== LSTM PREDICTION DEMO CHART =====
    function initPredictionChart() {
        const canvas = document.getElementById('predictionCanvas');
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        const dpr = window.devicePixelRatio || 1;

        canvas.width = canvas.offsetWidth * dpr;
        canvas.height = canvas.offsetHeight * dpr;
        ctx.scale(dpr, dpr);

        const w = canvas.offsetWidth;
        const h = canvas.offsetHeight;
        const pad = 8;

        // Generate actual data (past 20 days)
        const actualData = [];
        let val = 2400;
        for (let i = 0; i < 20; i++) {
            val += (Math.random() - 0.45) * 30;
            actualData.push(val);
        }

        // Predicted data (next 7 days, continuing trend)
        const predictedData = [actualData[actualData.length - 1]];
        for (let i = 0; i < 7; i++) {
            val += (Math.random() - 0.35) * 25;
            predictedData.push(val);
        }

        const allData = [...actualData, ...predictedData.slice(1)];
        const min = Math.min(...allData) - 20;
        const max = Math.max(...allData) + 20;
        const range = max - min;

        function getX(i, total) {
            return pad + (i / (total - 1)) * (w - pad * 2);
        }

        function getY(val) {
            return h - pad - ((val - min) / range) * (h - pad * 2);
        }

        // Draw actual line
        ctx.beginPath();
        actualData.forEach((v, i) => {
            const x = getX(i, allData.length);
            const y = getY(v);
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        });
        ctx.strokeStyle = '#4a9eff';
        ctx.lineWidth = 2.5;
        ctx.lineJoin = 'round';
        ctx.lineCap = 'round';
        ctx.stroke();

        // Draw predicted line (dashed)
        ctx.beginPath();
        const startIdx = actualData.length - 1;
        predictedData.forEach((v, i) => {
            const x = getX(startIdx + i, allData.length);
            const y = getY(v);
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        });
        ctx.strokeStyle = '#00d09c';
        ctx.lineWidth = 2.5;
        ctx.setLineDash([6, 4]);
        ctx.stroke();
        ctx.setLineDash([]);

        // Draw divider line
        const divX = getX(actualData.length - 1, allData.length);
        ctx.beginPath();
        ctx.moveTo(divX, pad);
        ctx.lineTo(divX, h - pad);
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.1)';
        ctx.lineWidth = 1;
        ctx.setLineDash([3, 3]);
        ctx.stroke();
        ctx.setLineDash([]);

        // Draw dots at endpoints
        const lastActual = actualData[actualData.length - 1];
        ctx.beginPath();
        ctx.arc(divX, getY(lastActual), 4, 0, Math.PI * 2);
        ctx.fillStyle = '#4a9eff';
        ctx.fill();

        const lastPred = predictedData[predictedData.length - 1];
        const predX = getX(allData.length - 1, allData.length);
        ctx.beginPath();
        ctx.arc(predX, getY(lastPred), 4, 0, Math.PI * 2);
        ctx.fillStyle = '#00d09c';
        ctx.fill();

        // Glow around predicted endpoint
        ctx.beginPath();
        ctx.arc(predX, getY(lastPred), 8, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(0, 208, 156, 0.2)';
        ctx.fill();
    }

    // ===== COUNTER ANIMATION =====
    function animateCounters() {
        const counters = document.querySelectorAll('.hero__stat-number');
        counters.forEach(counter => {
            const target = parseInt(counter.dataset.target);
            const duration = 2000;
            const start = performance.now();

            function updateCounter(now) {
                const elapsed = now - start;
                const progress = Math.min(elapsed / duration, 1);
                const eased = 1 - Math.pow(1 - progress, 3);
                counter.textContent = Math.floor(target * eased).toLocaleString();

                if (progress < 1) {
                    requestAnimationFrame(updateCounter);
                }
            }

            requestAnimationFrame(updateCounter);
        });
    }

    // ===== SCROLL REVEAL =====
    function initScrollReveal() {
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('visible');
                }
            });
        }, { threshold: 0.1, rootMargin: '0px 0px -40px 0px' });

        document.querySelectorAll('.category-card, .feature-card, .course-card, .cta-card').forEach(el => {
            el.classList.add('reveal');
            observer.observe(el);
        });
    }

    // ===== CATEGORY CARD MOUSE GLOW =====
    function initCardGlow() {
        document.querySelectorAll('.category-card').forEach(card => {
            card.addEventListener('mousemove', (e) => {
                const rect = card.getBoundingClientRect();
                card.style.setProperty('--mouse-x', `${e.clientX - rect.left}px`);
                card.style.setProperty('--mouse-y', `${e.clientY - rect.top}px`);
            });
        });
    }

    // ===== ACTIVE NAV LINK ON SCROLL =====
    function initActiveNav() {
        const sections = document.querySelectorAll('section[id]');
        const navLinks = document.querySelectorAll('.navbar__link');

        window.addEventListener('scroll', () => {
            let current = '';
            sections.forEach(section => {
                const sectionTop = section.offsetTop - 120;
                if (window.scrollY >= sectionTop) {
                    current = section.getAttribute('id');
                }
            });

            navLinks.forEach(link => {
                link.classList.remove('active');
                if (link.dataset.section === current) {
                    link.classList.add('active');
                }
            });
        });
    }

    // ===== KEYBOARD SHORTCUT (Ctrl+K) =====
    function initSearchShortcut() {
        document.addEventListener('keydown', (e) => {
            if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
                e.preventDefault();
                const searchInput = document.getElementById('searchInput');
                if (searchInput) searchInput.focus();
            }
        });
    }

    // ===== SMOOTH SCROLL FOR NAV =====
    function initSmoothScroll() {
        document.querySelectorAll('a[href^="#"]').forEach(anchor => {
            anchor.addEventListener('click', (e) => {
                e.preventDefault();
                const target = document.querySelector(anchor.getAttribute('href'));
                if (target) {
                    target.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }
            });
        });
    }

    // ===== LIVE PRICE SIMULATION =====
    function initLivePriceUpdates() {
        const elements = [
            { valId: 'heroNiftyVal', changeId: 'heroNiftyChange', baseVal: 22456.80, basePct: 1.24 },
            { valId: 'heroSensexVal', changeId: 'heroSensexChange', baseVal: 73890.45, basePct: 0.98 },
            { valId: 'heroBankNiftyVal', changeId: 'heroBankNiftyChange', baseVal: 47234.15, basePct: -0.42 },
        ];

        setInterval(() => {
            elements.forEach(item => {
                const valEl = document.getElementById(item.valId);
                const changeEl = document.getElementById(item.changeId);
                if (!valEl || !changeEl) return;

                const delta = (Math.random() - 0.5) * 10;
                item.baseVal += delta;
                item.basePct += (Math.random() - 0.5) * 0.02;

                const isPositive = item.basePct >= 0;
                valEl.textContent = item.baseVal.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
                changeEl.textContent = `${isPositive ? '+' : ''}${item.basePct.toFixed(2)}%`;

                valEl.className = `hero__mini-chart-value ${isPositive ? 'positive' : 'negative'}`;
                changeEl.className = `hero__mini-chart-change ${isPositive ? 'positive' : 'negative'}`;

                // Brief flash effect
                valEl.style.transition = 'none';
                valEl.style.textShadow = isPositive ? '0 0 12px rgba(0,208,156,0.5)' : '0 0 12px rgba(255,82,82,0.5)';
                setTimeout(() => {
                    valEl.style.transition = 'text-shadow 1s ease';
                    valEl.style.textShadow = 'none';
                }, 100);
            });
        }, 3000);
    }

    // ===== INITIALIZE EVERYTHING =====
    initTicker();
    initNavbarScroll();
    initMobileNav();
    initHeroCharts();
    initMarketTabs();
    initTrendingTabs();
    initPredictionChart();
    animateCounters();
    initScrollReveal();
    initCardGlow();
    initActiveNav();
    initSearchShortcut();
    initSmoothScroll();
    initLivePriceUpdates();

    // Redraw charts on resize
    let resizeTimeout;
    window.addEventListener('resize', () => {
        clearTimeout(resizeTimeout);
        resizeTimeout = setTimeout(() => {
            initHeroCharts();
            initPredictionChart();
            // Re-render current tab charts
            const activeMarketTab = document.querySelector('#marketTabs .tab.active');
            if (activeMarketTab) renderIndices(activeMarketTab.dataset.tab);
            const activeTrendingTab = document.querySelector('#trendingTabs .tab.active');
            if (activeTrendingTab) renderStocksTable(activeTrendingTab.dataset.tab);
        }, 250);
    });
});
