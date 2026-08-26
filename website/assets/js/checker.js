const GITHUB_REPO = 'YoannDev90/oxyd.space';
const LANDING_ZONE = 'oxyd.space';
const MAX_LABELS = 4;
const LABEL_RE = /^(?!-)[a-z0-9-]{1,63}(?<!-)$/;

let reservedSet = new Set();
fetch('https://raw.githubusercontent.com/' + GITHUB_REPO + '/main/config/reserved_names.txt')
  .then(function(r) { return r.ok ? r.text() : ''; })
  .then(function(txt) {
    if (!txt) return;
    txt.split('\n').forEach(function(l) {
      var name = l.trim().toLowerCase();
      if (name && !name.startsWith('#')) reservedSet.add(name);
    });
  }).catch(function() {});

let takenCache = null;

async function loadTaken() {
  if (takenCache && Date.now() - takenCache.ts < 300000) return takenCache.names;
  var r = await fetch('https://api.github.com/repos/' + GITHUB_REPO + '/contents/domains/' + LANDING_ZONE);
  if (!r.ok) throw new Error('api');
  var j = await r.json();
  var names = (Array.isArray(j) ? j : [])
    .filter(function(f) { return f.name.endsWith('.json'); })
    .map(function(f) { return f.name.slice(0, -5); });
  takenCache = { names: new Set(names), ts: Date.now() };
  return takenCache.names;
}

function isValidName(raw) {
  var labels = raw.split('.');
  if (labels.length < 1 || labels.length > MAX_LABELS) return false;
  return labels.every(function(l) { return LABEL_RE.test(l) && !l.startsWith('xn--'); });
}

(async function () {
  var i18n = await initI18n('checker');

  var input = document.getElementById('domainInput');
  var go = document.getElementById('go');
  var resultEl = document.getElementById('result');

  function setResult(html) {
    resultEl.innerHTML = html;
  }

  function linkFor(name) {
    var base = 'https://github.com/' + GITHUB_REPO + '/issues/new?template=register.yml';
    var q = '&title=' + encodeURIComponent('Subdomain registration') +
            '&request-type=' + encodeURIComponent('Register a new subdomain') +
            '&subdomain=' + encodeURIComponent(name);
    return '<a href="' + base + q + '" target="_blank" rel="noopener">' +
           i18n.fmt(i18n.t('register'), { d: name + '.oxyd.space' }) + '</a>';
  }

  async function check() {
    var raw = input.value.trim().toLowerCase()
      .replace(/\.oxyd\.space$/, '')
      .replace(/^https?:\/\//, '');
    if (!raw) {
      setResult('<span class="info">' + i18n.t('idle') + '</span>');
      return;
    }
    if (!isValidName(raw)) {
      setResult('<span class="bad">' + i18n.t('invalid') + '</span>');
      return;
    }
    var labels = raw.split('.');
    var lastLabel = labels[labels.length - 1];
    if (reservedSet.has(lastLabel)) {
      setResult('<span class="bad">' + i18n.fmt(i18n.t('reserved'), { d: lastLabel + '.' }) + '</span>');
      return;
    }
    go.disabled = true;
    setResult('<span class="info">' + i18n.t('checking') + '</span>');
    try {
      var names = await loadTaken();
      if (names.has(raw)) {
        setResult('<span class="bad">' + i18n.fmt(i18n.t('taken'), { d: raw + '.oxyd.space' }) + '</span>');
      } else {
        setResult('<span class="ok">' + i18n.fmt(i18n.t('available'), { d: raw + '.oxyd.space' }) + '</span>' + linkFor(raw));
      }
    } catch(e) {
      setResult('<span class="bad">' + i18n.t('error') + '</span>');
    } finally {
      go.disabled = false;
    }
  }

  go.addEventListener('click', check);
  input.addEventListener('keydown', function(e) { if (e.key === 'Enter') check(); });
  input.focus();
})();
