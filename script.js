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
        if (window.apiClient) {
            Promise.all([
                window.apiClient.getCandles('NIFTY 50', '1d', 30),
                window.apiClient.getCandles('SENSEX', '1d', 30),
                window.apiClient.getCandles('BANK NIFTY', '1d', 30),
                window.apiClient.getIndices()
            ]).then(([niftyCandles, sensexCandles, bankCandles, indices]) => {
                // Update Index Values and Changes
                if (indices && indices.length > 0) {
                    const n = indices.find(x => x.name.includes('NIFTY 50'));
                    if (n) {
                        const valEl = document.getElementById('heroNiftyVal');
                        const chgEl = document.getElementById('heroNiftyChange');
                        if (valEl) valEl.textContent = n.value.toLocaleString('en-IN');
                        if (chgEl) {
                            chgEl.textContent = (n.change_pct > 0 ? '+' : '') + n.change_pct + '%';
                            chgEl.className = 'hero__mini-chart-change ' + (n.positive ? 'positive' : 'negative');
                        }
                    }
                    const s = indices.find(x => x.name.includes('SENSEX'));
                    if (s) {
                        const valEl = document.getElementById('heroSensexVal');
                        const chgEl = document.getElementById('heroSensexChange');
                        if (valEl) valEl.textContent = s.value.toLocaleString('en-IN');
                        if (chgEl) {
                            chgEl.textContent = (s.change_pct > 0 ? '+' : '') + s.change_pct + '%';
                            chgEl.className = 'hero__mini-chart-change ' + (s.positive ? 'positive' : 'negative');
                        }
                    }
                    const b = indices.find(x => x.name.includes('BANK NIFTY'));
                    if (b) {
                        const valEl = document.getElementById('heroBankNiftyVal');
                        const chgEl = document.getElementById('heroBankNiftyChange');
                        if (valEl) valEl.textContent = b.value.toLocaleString('en-IN');
                        if (chgEl) {
                            chgEl.textContent = (b.change_pct > 0 ? '+' : '') + b.change_pct + '%';
                            chgEl.className = 'hero__mini-chart-change ' + (b.positive ? 'positive' : 'negative');
                        }
                    }
                }

                // Draw Real Historical Candlestick Sparklines
                const nData = niftyCandles && niftyCandles.length > 0 ? niftyCandles.map(c => c.close) : generateChartData(22300, 50, 30, 'up');
                const sData = sensexCandles && sensexCandles.length > 0 ? sensexCandles.map(c => c.close) : generateChartData(73500, 150, 30, 'up');
                const bData = bankCandles && bankCandles.length > 0 ? bankCandles.map(c => c.close) : generateChartData(47400, 80, 30, 'down');

                const nPos = nData[nData.length - 1] >= nData[0];
                const sPos = sData[sData.length - 1] >= sData[0];
                const bPos = bData[bData.length - 1] >= bData[0];

                drawSparkline('heroChartNifty', nData, nPos ? '#00d09c' : '#ff5252', nPos ? 'rgba(0, 208, 156, 0.1)' : 'rgba(255, 82, 82, 0.1)');
                drawSparkline('heroChartSensex', sData, sPos ? '#00d09c' : '#ff5252', sPos ? 'rgba(0, 208, 156, 0.1)' : 'rgba(255, 82, 82, 0.1)');
                drawSparkline('heroChartBankNifty', bData, bPos ? '#00d09c' : '#ff5252', bPos ? 'rgba(0, 208, 156, 0.1)' : 'rgba(255, 82, 82, 0.1)');
            }).catch(() => {
                drawSparkline('heroChartNifty', generateChartData(22300, 50, 40, 'up'), '#00d09c', 'rgba(0, 208, 156, 0.1)');
                drawSparkline('heroChartSensex', generateChartData(73500, 150, 40, 'up'), '#00d09c', 'rgba(0, 208, 156, 0.1)');
                drawSparkline('heroChartBankNifty', generateChartData(47400, 80, 40, 'down'), '#ff5252', 'rgba(255, 82, 82, 0.1)');
            });
        }
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
        if (!grid) return;
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
        if (!tabContainer) return;
        tabContainer.addEventListener('click', (e) => {
            if (!e.target.classList.contains('tab')) return;
            tabContainer.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            e.target.classList.add('active');
            renderIndices(e.target.dataset.tab);
        });

        renderIndices('indian');
    }

    // ===== TRENDING STOCKS TABLE =====
    let cachedTrending = null;

    function renderStocksTable(tab) {
        const tbody = document.getElementById('stocksTableBody');
        if (!tbody) return;

        function displayRows(list) {
            tbody.innerHTML = list.map((stock, i) => {
                const canvasId = `sparkline_${tab}_${i}`;
                const sym = stock.symbol;
                const comp = stock.name || stock.company || sym;
                const ltp = stock.price || stock.ltp || 0;
                const chg = stock.change || 0;
                const pct = stock.change_pct !== undefined ? stock.change_pct : (stock.pct || 0);
                const isPos = chg >= 0;
                const vol = typeof stock.volume === 'number' ? stock.volume.toLocaleString('en-IN') : (stock.volume || '14.2M');
                const curr = sym.includes('USDT') ? '$' : '₹';

                return `
                    <tr onclick="location.href='predictions.html?symbol=${sym}'" style="cursor:pointer;" title="Click to view AI Forecast for ${sym}">
                        <td>
                            <div class="stock-name">
                                <span class="stock-name__symbol">${sym}</span>
                                <span class="stock-name__company">${comp}</span>
                            </div>
                        </td>
                        <td><span class="stock-ltp">${curr}${ltp.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span></td>
                        <td><span class="stock-change ${isPos ? 'positive' : 'negative'}">${isPos ? '+' : ''}${typeof chg === 'number' ? chg.toFixed(2) : chg}</span></td>
                        <td><span class="stock-change ${isPos ? 'positive' : 'negative'}">${isPos ? '+' : ''}${typeof pct === 'number' ? pct.toFixed(2) : pct}%</span></td>
                        <td><span class="stock-volume">${vol}</span></td>
                        <td><canvas class="stock-sparkline" id="${canvasId}"></canvas></td>
                        <td><button class="stock-analyze-btn" onclick="event.stopPropagation(); location.href='analysis.html?cat=${sym}'">Analyze</button></td>
                    </tr>
                `;
            }).join('');

            requestAnimationFrame(() => {
                list.forEach((stock, i) => {
                    const canvasId = `sparkline_${tab}_${i}`;
                    const isPos = (stock.change >= 0) || (stock.change_pct >= 0);
                    const chartData = generateChartData(100, 6, 20, isPos ? 'up' : 'down');
                    const color = isPos ? '#00d09c' : '#ff5252';
                    drawSparkline(canvasId, chartData, color, 'transparent');
                });
            });
        }

        if (window.apiClient) {
            if (cachedTrending) {
                const mapTab = { gainers: 'gainers', losers: 'losers', active: 'most_active' };
                const list = cachedTrending[mapTab[tab] || 'gainers'];
                if (list && list.length > 0) {
                    displayRows(list);
                    return;
                }
            }
            window.apiClient.getTrending().then(data => {
                if (data) {
                    cachedTrending = data;
                    const mapTab = { gainers: 'gainers', losers: 'losers', active: 'most_active' };
                    const list = data[mapTab[tab] || 'gainers'];
                    if (list && list.length > 0) {
                        displayRows(list);
                    }
                }
            }).catch(() => {});
        }
    }

    function initTrendingTabs() {
        const tabContainer = document.getElementById('trendingTabs');
        if (!tabContainer) return;
        tabContainer.addEventListener('click', (e) => {
            if (!e.target.classList.contains('tab')) return;
            tabContainer.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            e.target.classList.add('active');
            renderStocksTable(e.target.dataset.tab);
        });

        renderStocksTable('gainers');
    }

    // ===== LSTM PREDICTION DEMO CHART (Real Candle Data) =====
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

        const sym = 'RELIANCE';

        function renderChartLines(actualData, predictedData) {
            ctx.clearRect(0, 0, w, h);
            const allData = [...actualData, ...predictedData.slice(1)];
            const min = Math.min(...allData) * 0.99;
            const max = Math.max(...allData) * 1.01;
            const range = max - min || 1;

            function getX(i, total) { return pad + (i / (total - 1)) * (w - pad * 2); }
            function getY(val) { return h - pad - ((val - min) / range) * (h - pad * 2); }

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

            // Divider
            const divX = getX(actualData.length - 1, allData.length);
            ctx.beginPath();
            ctx.moveTo(divX, pad);
            ctx.lineTo(divX, h - pad);
            ctx.strokeStyle = 'rgba(255, 255, 255, 0.15)';
            ctx.lineWidth = 1;
            ctx.setLineDash([3, 3]);
            ctx.stroke();
            ctx.setLineDash([]);

            // Endpoint dots
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

            ctx.beginPath();
            ctx.arc(predX, getY(lastPred), 8, 0, Math.PI * 2);
            ctx.fillStyle = 'rgba(0, 208, 156, 0.2)';
            ctx.fill();
        }

        if (window.apiClient) {
            Promise.all([
                window.apiClient.getCandles(sym, '1d', 20),
                window.apiClient.getPrediction(sym, 7)
            ]).then(([candles, pred]) => {
                if (candles && candles.length > 0) {
                    const actualData = candles.map(c => c.close);
                    let predictedData = [actualData[actualData.length - 1]];
                    const pts = pred && (pred.forecast_points || pred.predictions);
                    if (pts && pts.length > 0) {
                        predictedData = [actualData[actualData.length - 1], ...pts.map(p => p.predicted)];
                    } else {
                        let v = actualData[actualData.length - 1];
                        for (let i = 0; i < 7; i++) { v += (v * 0.005); predictedData.push(v); }
                    }
                    renderChartLines(actualData, predictedData);
                }
            }).catch(() => {});
        }
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

    // ===== LIVE REAL MARKET DATA TICKS & HYDRATION =====
    function initLivePriceUpdates() {
        if (window.apiClient) {
            window.apiClient.connectWebSocket();
            window.apiClient.onTick((ticks) => {
                ticks.forEach(t => {
                    if (t.symbol === 'NIFTY 50') {
                        const valEl = document.getElementById('heroNiftyVal');
                        const chgEl = document.getElementById('heroNiftyChange');
                        if (valEl) valEl.textContent = t.price.toLocaleString('en-IN');
                        if (chgEl) {
                            chgEl.textContent = (t.change_pct > 0 ? '+' : '') + t.change_pct + '%';
                            chgEl.className = 'hero__mini-chart-change ' + (t.change >= 0 ? 'positive' : 'negative');
                        }
                    } else if (t.symbol === 'SENSEX') {
                        const valEl = document.getElementById('heroSensexVal');
                        const chgEl = document.getElementById('heroSensexChange');
                        if (valEl) valEl.textContent = t.price.toLocaleString('en-IN');
                        if (chgEl) {
                            chgEl.textContent = (t.change_pct > 0 ? '+' : '') + t.change_pct + '%';
                            chgEl.className = 'hero__mini-chart-change ' + (t.change >= 0 ? 'positive' : 'negative');
                        }
                    } else if (t.symbol === 'BANK NIFTY') {
                        const valEl = document.getElementById('heroBankNiftyVal');
                        const chgEl = document.getElementById('heroBankNiftyChange');
                        if (valEl) valEl.textContent = t.price.toLocaleString('en-IN');
                        if (chgEl) {
                            chgEl.textContent = (t.change_pct > 0 ? '+' : '') + t.change_pct + '%';
                            chgEl.className = 'hero__mini-chart-change ' + (t.change >= 0 ? 'positive' : 'negative');
                        }
                    }
                });
            });

            // Hydrate category cards with real live market data
            Promise.all([
                window.apiClient.getQuote('BTCUSDT'),
                window.apiClient.getQuote('ETHUSDT'),
                window.apiClient.getBreadth()
            ]).then(([btc, eth, breadth]) => {
                const catCrypto = document.getElementById('catCrypto');
                if (catCrypto && btc && eth) {
                    const stats = catCrypto.querySelectorAll('.category-card__stat');
                    if (stats.length >= 2) {
                        stats[0].innerHTML = `BTC: <span class="${btc.change >= 0 ? 'positive' : 'negative'}">$${btc.price.toLocaleString('en-IN')}</span>`;
                        stats[1].innerHTML = `ETH: <span class="${eth.change >= 0 ? 'positive' : 'negative'}">$${eth.price.toLocaleString('en-IN')}</span>`;
                    }
                }
                const catStocks = document.getElementById('catStocks');
                if (catStocks && breadth) {
                    const stats = catStocks.querySelectorAll('.category-card__stat');
                    if (stats.length >= 2) {
                        stats[0].innerHTML = `<span class="positive">▲ ${breadth.advances.toLocaleString('en-IN')}</span> advancing`;
                        stats[1].innerHTML = `<span class="negative">▼ ${breadth.declines.toLocaleString('en-IN')}</span> declining`;
                    }
                }
            }).catch(() => {});
        }
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
