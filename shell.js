/**
 * STOCKY — small top-bar additions (no layout changes)
 * 1. Date chip: today's date in IST + whether NSE regular hours are running.
 * 2. Profile avatar in the top-right that reuses the sidebar user's click behaviour.
 */
(function () {
    const IST = 'Asia/Kolkata';

    // ---- date chip ----
    function istParts(now) {
        const parts = new Intl.DateTimeFormat('en-GB', {
            timeZone: IST, weekday: 'short', hour: '2-digit', minute: '2-digit', hour12: false,
        }).formatToParts(now);
        const get = (t) => parts.find((p) => p.type === t)?.value;
        return { weekday: get('weekday'), minutes: Number(get('hour')) * 60 + Number(get('minute')) };
    }

    // NSE regular session 09:15–15:30 IST, Mon–Fri. Exchange holidays are not known here,
    // so the label says "session hours", not "market open".
    function sessionLabel(now) {
        const { weekday, minutes } = istParts(now);
        const weekend = weekday === 'Sat' || weekday === 'Sun';
        if (!weekend && minutes >= 555 && minutes < 930) return { text: 'Session hours', open: true };
        if (!weekend && minutes >= 540 && minutes < 555) return { text: 'Pre-open', open: false };
        return { text: 'After hours', open: false };
    }

    function buildDateChip() {
        const chip = document.createElement('div');
        chip.className = 'stk-date-chip';
        chip.title = 'NSE regular session 09:15–15:30 IST, Mon–Fri (exchange holidays not checked)';
        chip.innerHTML =
            '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" aria-hidden="true">' +
            '<rect x="3.5" y="5" width="17" height="15.5" rx="4"/><path d="M3.5 10h17M8 3v4M16 3v4"/></svg>' +
            '<span class="stk-date-chip__date"></span><span class="stk-date-chip__state"></span>';

        const render = () => {
            const now = new Date();
            chip.querySelector('.stk-date-chip__date').textContent = new Intl.DateTimeFormat('en-IN', {
                timeZone: IST, day: 'numeric', month: 'short', year: 'numeric',
            }).format(now);
            const s = sessionLabel(now);
            const state = chip.querySelector('.stk-date-chip__state');
            state.textContent = s.text;
            state.classList.toggle('is-open', s.open);
        };
        render();
        setInterval(render, 60 * 1000);
        return chip;
    }

    // ---- avatar ----
    function buildAvatar() {
        const sidebarUser = document.querySelector('.sidebar__user');
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'stk-avatar';

        const sync = () => {
            const src = document.querySelector('.sidebar__avatar');
            const name = document.querySelector('.sidebar__user-name');
            btn.textContent = (src && src.textContent.trim()) || 'G';
            btn.setAttribute('aria-label', (name && name.textContent.trim()) || 'Account');
            btn.title = sidebarUser ? sidebarUser.title || 'Account' : 'Account';
        };
        sync();
        // dashboard.js fills the sidebar user after load; mirror it.
        setTimeout(sync, 0);
        window.addEventListener('load', sync);

        btn.addEventListener('click', () => {
            if (sidebarUser) sidebarUser.click();
            else window.location.href = 'login.html';
        });
        return btn;
    }

    // ---- market status badges ----
    // Replaces badges that used to say "Markets are Open" no matter the time.
    // Markup opts in with [data-market-status]; the text goes in [data-market-status-text].
    const HOLIDAY_NOTE = 'NSE regular session 09:15–15:30 IST, Mon–Fri (exchange holidays not checked)';

    function renderMarketStatus() {
        const s = sessionLabel(new Date());
        document.querySelectorAll('[data-market-status]').forEach((el) => {
            const text = el.querySelector('[data-market-status-text]') || el;
            text.textContent = 'NSE ' + s.text.toLowerCase();
            el.title = HOLIDAY_NOTE;
            el.classList.toggle('market-status--open', s.open);
            el.classList.toggle('market-status--closed', !s.open);
            el.classList.toggle('is-closed', !s.open);
        });
        // mock trading order ticket label
        const ticket = document.getElementById('dispMarketStatus');
        if (ticket) {
            ticket.textContent = s.text.toUpperCase();
            ticket.title = HOLIDAY_NOTE;
        }
    }

    function init() {
        renderMarketStatus();
        setInterval(renderMarketStatus, 60 * 1000);

        const right = document.querySelector('.topbar__right');
        if (!right || right.querySelector('.stk-date-chip')) return;
        const search = right.querySelector('.topbar__search');
        right.insertBefore(buildDateChip(), search ? search.nextSibling : right.firstChild);
        right.appendChild(buildAvatar());
    }

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
})();
