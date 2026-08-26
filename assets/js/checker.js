const GITHUB_REPO = 'YoannDev90/oxyd.space';
const LANDING_ZONE = 'oxyd.space';
const MAX_LABELS = 4;
const LABEL_RE = /^(?!-)[a-z0-9-]{1,63}(?<!-)$/;

let reservedSet = new Set();
fetch(`https://raw.githubusercontent.com/${GITHUB_REPO}/main/config/reserved_names.txt`)
  .then(r => r.ok ? r.text() : '')
  .then(txt => {
    if (!txt) return;
    txt.split('\n').forEach(l => {
      const name = l.trim().toLowerCase();
      if (name && !name.startsWith('#')) reservedSet.add(name);
    });
  }).catch(() => {});

const I18N = {
  en: {
    'nav.home': 'Home',
    'nav.propagation': 'Propagation',
    'title': 'Availability Checker',
    'subtitle': 'Check if a subdomain is free before registering it.',
    'label': 'Subdomain name',
    'placeholder': 'yourname',
    'cta': 'Check',
    'idle': 'Type a name to see if it\'s free.',
    'available': '{d} is available!',
    'taken': '{d} is already taken.',
    'invalid': 'Invalid name. Use a-z, 0-9 and hyphens (up to 4 labels, e.g. api.mysite).',
    'reserved': '{d} cannot end a hostname (reserved). Put it first, e.g. {d}yourname',
    'checking': 'Checking…',
    'error': 'Could not check right now. Try again later.',
    'register': 'Register {d}',
    'rules.title': 'Naming rules',
    'rules.labels': '1–4 labels separated by dots (e.g. <code>api.myname</code>)',
    'rules.chars': 'Lowercase a–z, digits 0–9, hyphens (no leading/trailing hyphen)',
    'rules.max': '63 characters per label',
    'rules.reserved': 'Some names are reserved (www, root, ns, api…)',
    'records.title': 'Supported record types',
    'rec.cname': 'websites & hosting',
    'rec.a': 'servers & IPv4',
    'rec.aaaa': 'servers & IPv6',
    'rec.txt': 'verifications',
    'footer.oss': 'Open source under MIT.',
    'footer.repo': 'Repository',
  },
  fr: {
    'nav.home': 'Accueil',
    'nav.propagation': 'Propagation',
    'title': 'Vérificateur de disponibilité',
    'subtitle': 'Vérifiez si un sous-domaine est libre avant de l\'enregistrer.',
    'label': 'Nom du sous-domaine',
    'placeholder': 'votre-nom',
    'cta': 'Vérifier',
    'idle': 'Tapez un nom pour voir s\'il est libre.',
    'available': '{d} est disponible !',
    'taken': '{d} est déjà pris.',
    'invalid': 'Nom invalide. Utilisez a-z, 0-9 et des tirets (jusqu\'à 4 labels, ex. api.monsite).',
    'reserved': '{d} ne peut pas terminer un nom (réservé). Mettez-le en premier, ex. {d}votrenom',
    'checking': 'Vérification…',
    'error': 'Impossible de vérifier pour le moment. Réessayez plus tard.',
    'register': 'Réserver {d}',
    'rules.title': 'Règles de nommage',
    'rules.labels': '1–4 labels séparés par des points (ex. <code>api.monnom</code>)',
    'rules.chars': 'Minuscules a–z, chiffres 0–9, tirets (pas de tiret en début/fin)',
    'rules.max': '63 caractères par label',
    'rules.reserved': 'Certains noms sont réservés (www, root, ns, api…)',
    'records.title': 'Types d\'enregistrements supportés',
    'rec.cname': 'sites & hébergement',
    'rec.a': 'serveurs & IPv4',
    'rec.aaaa': 'serveurs & IPv6',
    'rec.txt': 'vérifications',
    'footer.oss': 'Open source sous MIT.',
    'footer.repo': 'Dépôt',
  }
};

let lang = localStorage.getItem('oxyd-lang') || (navigator.language || 'en').slice(0, 2);
if (!I18N[lang]) lang = 'en';

function t(key) {
  return I18N[lang][key] ?? I18N.en[key] ?? key;
}
function fmt(str, vars) {
  return str.replace(/\{(\w+)\}/g, (_, k) => vars[k] ?? '');
}
function applyLang() {
  document.documentElement.lang = lang;
  document.getElementById('langBtn').textContent = lang === 'en' ? 'FR' : 'EN';
  document.querySelectorAll('[data-i18n]').forEach(el => {
    el.innerHTML = t(el.dataset.i18n);
  });
  document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
    el.placeholder = t(el.dataset.i18nPlaceholder);
  });
}
document.getElementById('langBtn').addEventListener('click', () => {
  lang = lang === 'en' ? 'fr' : 'en';
  localStorage.setItem('oxyd-lang', lang);
  applyLang();
});

const input = document.getElementById('domainInput');
const go = document.getElementById('go');
const resultEl = document.getElementById('result');
let takenCache = null;

async function loadTaken() {
  if (takenCache && Date.now() - takenCache.ts < 300000) return takenCache.names;
  const r = await fetch(`https://api.github.com/repos/${GITHUB_REPO}/contents/domains/${LANDING_ZONE}`);
  if (!r.ok) throw new Error('api');
  const j = await r.json();
  const names = (Array.isArray(j) ? j : [])
    .filter(f => f.name.endsWith('.json'))
    .map(f => f.name.slice(0, -5));
  takenCache = { names: new Set(names), ts: Date.now() };
  return takenCache.names;
}

function setResult(html) {
  resultEl.innerHTML = html;
}

function linkFor(name) {
  const base = `https://github.com/${GITHUB_REPO}/issues/new?template=register.yml`;
  const q = `&title=${encodeURIComponent('Subdomain registration')}&request-type=${encodeURIComponent('Register a new subdomain')}&subdomain=${encodeURIComponent(name)}`;
  return `<a href="${base}${q}" target="_blank" rel="noopener">${fmt(t('register'), { d: name + '.oxyd.space' })}</a>`;
}

function isValidName(raw) {
  const labels = raw.split('.');
  if (labels.length < 1 || labels.length > MAX_LABELS) return false;
  return labels.every(l => LABEL_RE.test(l) && !l.startsWith('xn--'));
}

async function check() {
  const raw = input.value.trim().toLowerCase()
    .replace(/\.oxyd\.space$/, '')
    .replace(/^https?:\/\//, '');
  if (!raw) {
    setResult(`<span class="info">${t('idle')}</span>`);
    return;
  }
  if (!isValidName(raw)) {
    setResult(`<span class="bad">${t('invalid')}</span>`);
    return;
  }
  const labels = raw.split('.');
  const lastLabel = labels[labels.length - 1];
  if (reservedSet.has(lastLabel)) {
    setResult(`<span class="bad">${fmt(t('reserved'), { d: lastLabel + '.' })}</span>`);
    return;
  }
  go.disabled = true;
  setResult(`<span class="info">${t('checking')}</span>`);
  try {
    const names = await loadTaken();
    if (names.has(raw)) {
      setResult(`<span class="bad">${fmt(t('taken'), { d: raw + '.oxyd.space' })}</span>`);
    } else {
      setResult(`<span class="ok">${fmt(t('available'), { d: raw + '.oxyd.space' })}</span>${linkFor(raw)}`);
    }
  } catch {
    setResult(`<span class="bad">${t('error')}</span>`);
  } finally {
    go.disabled = false;
  }
}

go.addEventListener('click', check);
input.addEventListener('keydown', e => { if (e.key === 'Enter') check(); });
input.focus();

applyLang();
