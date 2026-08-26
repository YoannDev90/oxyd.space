/**
 * Minimal i18n loader for oxyd.space
 * Usage: in page JS, call initI18n('index') after DOM ready.
 * It loads assets/i18n/{lang}.json (shared) + assets/i18n/{page}.{lang}.json (page),
 * merges them, and applies data-i18n / data-i18n-html / data-i18n-placeholder attributes.
 */
(function () {
  const cache = {};

  function getLang() {
    return localStorage.getItem('oxyd-lang') || (navigator.language || 'en').slice(0, 2);
  }

  function setLang(l) {
    localStorage.setItem('oxyd-lang', l);
  }

  async function loadJSON(url) {
    if (cache[url]) return cache[url];
    try {
      const r = await fetch(url);
      if (!r.ok) return {};
      cache[url] = await r.json();
      return cache[url];
    } catch {
      return {};
    }
  }

  function applyToDOM(dict) {
    document.querySelectorAll('[data-i18n]').forEach(el => {
      const key = el.dataset.i18n;
      if (key in dict) el.textContent = dict[key];
    });
    document.querySelectorAll('[data-i18n-html]').forEach(el => {
      const key = el.dataset.i18nHtml;
      if (key in dict) el.innerHTML = dict[key];
    });
    document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
      const key = el.dataset.i18nPlaceholder;
      if (key in dict) el.placeholder = dict[key];
    });
  }

  /**
   * Initialize i18n for a page.
   * @param {string} page — page name (matches JSON filename, e.g. 'index', 'checker', 'tools', 'propagation')
   * @returns {{ lang: string, t: function, fmt: function, dict: object }}
   */
  window.initI18n = async function (page) {
    let lang = getLang();
    const shared = await loadJSON('/assets/i18n/' + lang + '.json');
    const pageData = await loadJSON('/assets/i18n/' + page + '.' + lang + '.json');
    const dict = Object.assign({}, shared, pageData);

    document.documentElement.lang = lang;

    // Apply text
    applyToDOM(dict);

    // Update lang button
    const btn = document.getElementById('langBtn');
    if (btn) btn.textContent = lang === 'en' ? 'FR' : 'EN';

    // t(key) — get translation, fallback to key
    function t(key) {
      return dict[key] ?? key;
    }

    // fmt(str, {var: val}) — simple {var} interpolation
    function fmt(str, vars) {
      return str.replace(/\{(\w+)\}/g, function (_, k) { return vars[k] ?? ''; });
    }

    // Switch language handler (replaceWith strips previous listeners)
    if (btn) {
      var fresh = btn.cloneNode(true);
      btn.parentNode.replaceChild(fresh, btn);
      fresh.addEventListener('click', async function () {
        lang = lang === 'en' ? 'fr' : 'en';
        setLang(lang);
        Object.keys(cache).forEach(function (k) { delete cache[k]; });
        await window.initI18n(page);
      });
    }

    return { lang: lang, t: t, fmt: fmt, dict: dict };
  };
})();
