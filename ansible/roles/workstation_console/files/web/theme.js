'use strict';

// Runs before the stylesheet to avoid flashing the wrong saved theme.
(() => {
  const preferenceKey = 'workstation-theme';
  const systemTheme = window.matchMedia('(prefers-color-scheme: dark)');
  function preference() {
    try {
      const saved = localStorage.getItem(preferenceKey);
      return saved === 'dark' || saved === 'light' ? saved : null;
    } catch { return null; }
  }
  function apply(theme) {
    document.documentElement.dataset.theme = theme;
    const toggle = document.getElementById('theme-toggle');
    if (!toggle) return;
    const next = theme === 'dark' ? 'light' : 'dark';
    const label = next === 'dark' ? 'Dark mode' : 'Light mode';
    document.getElementById('theme-label').textContent = label;
    document.getElementById('theme-icon').setAttribute('href', '#i-' + (next === 'dark' ? 'moon' : 'sun'));
    toggle.setAttribute('aria-label', 'Switch to ' + next + ' mode');
    toggle.title = 'Switch to ' + next + ' mode';
  }
  apply(preference() || (systemTheme.matches ? 'dark' : 'light'));
  document.addEventListener('DOMContentLoaded', () => apply(document.documentElement.dataset.theme));
  document.addEventListener('click', event => {
    if (!event.target.closest('#theme-toggle')) return;
    const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
    try { localStorage.setItem(preferenceKey, next); } catch { /* Still usable without storage. */ }
    apply(next);
  });
  systemTheme.addEventListener('change', event => {
    if (!preference()) apply(event.matches ? 'dark' : 'light');
  });
  window.addEventListener('storage', event => {
    if (event.key === preferenceKey) apply(preference() || (systemTheme.matches ? 'dark' : 'light'));
  });
})();
