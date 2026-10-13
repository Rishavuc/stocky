/**
 * ========================================================
 * INVESTOR'S EYE — Global Theme Switcher (Default: Day White / Dark #181a20)
 * ========================================================
 */

// Immediate execution to prevent flash of wrong theme before page render
(function() {
    const savedTheme = localStorage.getItem('investors_eye_theme') || 'light';
    document.documentElement.setAttribute('data-theme', savedTheme);
})();

function updateThemeToggleUI() {
    const current = document.documentElement.getAttribute('data-theme') || 'light';
    document.querySelectorAll('.theme-toggle-label').forEach(label => {
        label.textContent = current === 'dark' ? 'Dark' : 'Day';
    });
    document.querySelectorAll('.theme-toggle-btn').forEach(btn => {
        btn.setAttribute('data-current', current);
        btn.setAttribute('title', current === 'dark' ? 'Switch to Day Theme (White)' : 'Switch to Dark Theme (#181a20)');
    });
}

function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme') || 'light';
    const next = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('investors_eye_theme', next);
    updateThemeToggleUI();

    // Broadcast custom event for charts or components that may want to refresh colors
    window.dispatchEvent(new CustomEvent('themeChanged', { detail: { theme: next } }));
}

function initThemeSwitcher() {
    document.querySelectorAll('.theme-toggle-btn').forEach(btn => {
        btn.removeEventListener('click', toggleTheme);
        btn.addEventListener('click', toggleTheme);
    });
    updateThemeToggleUI();
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initThemeSwitcher);
} else {
    initThemeSwitcher();
}
