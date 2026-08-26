const GITHUB_REPO = 'YoannDev90/oxyd.space';
const LANDING_ZONE = 'oxyd.space';
const RESERVED_FALLBACK = ['www','root','apex','ns','ns1','ns2','mx','smtp','mail','api','app','admin','dashboard','db','vpn','dns','register','login','auth','cdn','static','status','git','docs','help','support','contact'];
const MAX_LABELS = 3;
const LABEL_RE = /^(?!-)[a-z0-9-]{1,63}(?<!-)$/;
const TEMPLATE = { owner:{ github:'your-github-username', github_id:12345678 }, records:[ { type:'CNAME', value:'your-github-username.github.io' } ], www:false };
let reservedSet = new Set(RESERVED_FALLBACK);
fetch(`https://raw.githubusercontent.com/${GITHUB_REPO}/main/config/reserved_names.txt`)
  .then(r=>r.ok?r.text():'')
  .then(txt=>{
    if(!txt)return;
    txt.split('\n').forEach(l=>{
      const name=l.trim().toLowerCase();
      if(name&&!name.startsWith('#'))reservedSet.add(name);
    });
  }).catch(()=>{});

const I18N = {
  en:{
    'nav.how':'How it works','nav.faq':'FAQ',
    'hero.badge':'free forever · open source · no ads',
    'hero.title':'Claim your corner of',
    'hero.subtitle':'Get a free subdomain for your personal site, portfolio or project. One issue form, zero dollars, live in minutes.',
    'checker.label':'Check availability','checker.placeholder':'yourname','checker.cta':'Check',
    'checker.idle':"Type a name to see if it's free.",
    'checker.available':'{d} is available!','checker.taken':'{d} is already taken.',
    'checker.invalid':'Invalid name. Use a-z, 0-9 and hyphens (up to 3 levels, e.g. sub.site).',
    'checker.reserved':'{d} cannot end a hostname (reserved). Put it first instead, e.g. {d}yourname','checker.checking':'Checking…','checker.error':'Could not check right now. Try again later.',
    'checker.register':'Register {d}',
    'stats.claimed':'subdomains claimed','stats.price':'price / year','stats.time':'to go live',
    'steps.title':'How it works','steps.sub':'Fully automated. No accounts, no waiting lists.',
    'step1.t':'Fill in the issue form','step1.d':'Open a pre-filled issue on GitHub: pick a name, a record type and its target. Takes one minute.',
    'step2.t':'The bot takes over','step2.d':'Your GitHub identity is verified (user ID), rules enforced, config committed automatically.',
    'step3.t':'Registered & live','step3.d':'DNS records are published right away — usually resolving worldwide within five minutes.',
    'snippet.copy':'Copy','snippet.copied':'Copied!', 'snippet.file':'domains/your.name.json · generated from your issue',
    'rec.cname':'websites & hosting','rec.a':'servers & IPv6','rec.txt':'verifications',
    'faq.title':'FAQ',
    'faq':[
      ['Is it really free?','Yes. The domain costs a coffee per year to maintain and the whole stack runs on free tiers (GitHub Pages + deSEC). No ads, no tracking, MIT licensed.'],
      ['What can I use it for?','Personal sites, portfolios, open-source docs, homelab… anything lawful. Subdomains used for phishing, malware or abuse are removed without notice.'],
      ['Which DNS records are supported?','Up to 4 levels (e.g. s1.service.yourname.oxyd.space) with CNAME, A, AAAA and TXT records, plus an optional automatic www. prefix. MX and NS delegation are not available yet.'],
      ['How fast does it go live?','Validation takes seconds. After merge, DNS is published automatically and usually resolves worldwide within ~5 minutes.'],
      ['Does it work with GitHub Pages, Vercel, Netlify…?','Yes. Point a CNAME record at your host target. A full GitHub Pages guide is in the README.'],
      ['Can I update or delete my subdomain later?','Yes — open a new issue and choose “Update my records” or “Delete my subdomain”. Ownership is tied to your GitHub account.'],
      ['What happens when the domain expires?','<code>oxyd.space</code> is registered one year at a time. A month before expiry, the project moves to a cheaper successor domain: all existing subdomains are migrated automatically and the old names become permanent redirects. Your links keep working — no action needed.']
    ],
    'cta.title':'Ready to claim yours?','cta.sub':'It takes about five minutes and costs nothing. Forever.',
    'cta.btn':'Register now on GitHub',
    'cta.note':'Heads-up: <code>oxyd.space</code> is registered for <strong>one year</strong>. One month before it expires, the project moves to a cheaper domain — every subdomain will be migrated automatically, and old names will permanently redirect to their new address.',
    'footer.oss':'Open source under MIT. Built by the community, for the community.',
    'footer.repo':'Repository','footer.browse':'Taken domains'
  },
  fr:{
    'nav.how':'Comment ça marche','nav.faq':'FAQ',
    'hero.badge':'gratuit à vie · open source · sans pub',
    'hero.title':'Réservez votre coin de',
    'hero.subtitle':"Obtenez un sous-domaine gratuit pour votre site perso, portfolio ou projet. Un formulaire d’issue, zéro euro, en ligne en quelques minutes.",
    'checker.label':'Vérifier la disponibilité','checker.placeholder':'votre-nom','checker.cta':'Vérifier',
    'checker.idle':"Tapez un nom pour voir s'il est libre.",
    'checker.available':'{d} est disponible !','checker.taken':'{d} est déjà pris.',
    'checker.invalid':'Nom invalide. Utilisez a-z, 0-9 et des tirets (jusqu\u2019à 3 niveaux, ex. sous.site).',
    'checker.reserved':'{d} ne peut pas terminer un nom (réservé). Mettez-le en premier, ex. {d}votrenom','checker.checking':'Vérification…','checker.error':'Impossible de vérifier pour le moment. Réessayez plus tard.',
    'checker.register':'Réserver {d}',
    'stats.claimed':'sous-domaines réservés','stats.price':'prix / an','stats.time':'pour être en ligne',
    'steps.title':'Comment ça marche','steps.sub':'Entièrement automatisé. Sans compte, sans liste d\u2019attente.',
    'step1.t':'Remplissez le formulaire','step1.d':'Ouvrez une issue pré-remplie sur GitHub : nom, type d’enregistrement et cible. Une minute suffit.',
    'step2.t':'Le bot s’occupe de tout','step2.d':'Votre identité GitHub est vérifiée (ID utilisateur), les règles appliquées, la config commitée automatiquement.',
    'step3.t':'Enregistré & en ligne','step3.d':'Vos enregistrements DNS sont publiés aussitôt — résolution mondiale généralement sous cinq minutes.',
    'snippet.copy':'Copier','snippet.copied':'Copié !', 'snippet.file':'domains/votre.nom.json · généré depuis votre issue',
    'rec.cname':'sites & hébergement','rec.a':'serveurs & IPv6','rec.txt':'vérifications',
    'faq.title':'FAQ',
    'faq':[
      ['C\u2019est vraiment gratuit ?','Oui. Le domaine coûte le prix d\u2019un café par an et toute la stack tourne sur des offres gratuites (GitHub Pages + deSEC). Sans pub, sans tracking, licence MIT.'],
      ['Pour quoi puis-je l\u2019utiliser ?','Sites persos, portfolios, docs de projets open source, homelab… tout ce qui est légal. Le phishing, le malware et les abus sont supprimés sans préavis.'],
      ['Quels types d\u2019enregistrements ?','Jusqu\u2019à 4 niveaux (ex. s1.service.votrenom.oxyd.space) avec CNAME, A, AAAA et TXT, plus un préfixe www. automatique en option. MX et délégation NS ne sont pas disponibles pour l\u2019instant.'],
      ['En combien de temps c\u2019est en ligne ?','La validation prend quelques secondes. Après fusion, le DNS est publié automatiquement et résout généralement partout en ~5 minutes.'],
      ['Compatible GitHub Pages, Vercel, Netlify… ?','Oui. Pointez un CNAME vers votre hébergeur. Un guide complet GitHub Pages est dans le README.'],
      ['Je peux modifier ou supprimer mon sous-domaine plus tard ?','Oui — ouvrez une nouvelle issue et choisissez « Update my records » ou « Delete my subdomain ». La propriété est liée à votre compte GitHub.'],
      ['Que se passe-t-il à l\u2019expiration du domaine ?','<code>oxyd.space</code> est enregistré un an à la fois. Un mois avant l\u2019échéance, le projet passera sur un domaine successeur moins cher : tous les sous-domaines existants seront migrés automatiquement et les anciens noms deviendront des redirections permanentes. Vos liens continueront de fonctionner — rien à faire de votre côté.']
    ],
    'cta.title':'Prêt à réserver le vôtre ?','cta.sub':'Cinq minutes environ, et aucun coût. Pour toujours.',
    'cta.btn':'Réserver sur GitHub',
    'cta.note':"À savoir : <code>oxyd.space</code> est enregistré pour <strong>un an</strong>. Un mois avant l\u2019échéance, le projet passera sur un domaine moins cher — tous les sous-domaines seront migrés automatiquement et les anciens noms redirigeront en permanence vers leur nouvelle adresse.",
    'footer.oss':'Open source sous licence MIT. Fait par la communauté, pour la communauté.',
    'footer.repo':'Dépôt','footer.browse':'Domaines pris'
  }
};

let lang = localStorage.getItem('oxyd-lang') || (navigator.language||'en').slice(0,2);
if (!I18N[lang]) lang = 'en';

function t(key){
  return I18N[lang][key] ?? I18N.en[key] ?? key;
}
function fmt(str, vars){
  return str.replace(/\{(\w+)\}/g, (_,k)=>vars[k]??'');
}
function applyLang(){
  document.documentElement.lang = lang;
  document.getElementById('langBtn').textContent = lang==='en'?'FR':'EN';
  document.querySelectorAll('[data-i18n]').forEach(el=>{ el.textContent = t(el.dataset.i18n); });
  document.querySelectorAll('[data-i18n-html]').forEach(el=>{ el.innerHTML = t(el.dataset.i18nHtml); });
  document.querySelectorAll('[data-i18n-placeholder]').forEach(el=>{ el.placeholder = t(el.dataset.i18nPlaceholder); });
  const faqList = document.getElementById('faqList');
  faqList.innerHTML='';
  I18N[lang].faq.forEach(([q,a])=>{
    const d=document.createElement('details');d.className='faq-item';
    const s=document.createElement('summary');s.textContent=q;
    const p=document.createElement('p');p.innerHTML=a;
    d.append(s,p);faqList.append(d);
  });
  renderSnippet();
}
document.getElementById('langBtn').addEventListener('click',()=>{
  lang = lang==='en'?'fr':'en';
  localStorage.setItem('oxyd-lang',lang);
  applyLang();
});

function esc(s){return s.replace(/&/g,'&amp;').replace(/</g,'&lt;');}
function highlight(json){
  return esc(json)
    .replace(/&quot;/g,'"')
    .replace(/"([^"]+)":/g,'<span class="tk-key">"$1"</span>:')
    .replace(/: "([^"]*)"/g,': <span class="tk-str">"$1"</span>');
}
function renderSnippet(){
  const json=JSON.stringify(TEMPLATE,null,2);
  document.getElementById('snippetCode').innerHTML=highlight(json);
}
const copyBtn=document.getElementById('copyBtn');
copyBtn.addEventListener('click',async()=>{
  try{
    await navigator.clipboard.writeText(JSON.stringify(TEMPLATE,null,2));
    copyBtn.textContent=t('snippet.copied');
    setTimeout(()=>{copyBtn.textContent=t('snippet.copy')},1600);
  }catch{}
});

const input=document.getElementById('domainInput');
const checkBtn=document.getElementById('checkBtn');
const resultEl=document.getElementById('checkerResult');
let takenCache=null;

async function loadTaken(){
  if(takenCache && Date.now()-takenCache.ts<300000) return takenCache.names;
  const r=await fetch(`https://api.github.com/repos/${GITHUB_REPO}/contents/domains/${LANDING_ZONE}`);
  if(!r.ok) throw new Error('api');
  const j=await r.json();
  const names=(Array.isArray(j)?j:[]).filter(f=>f.name.endsWith('.json')).map(f=>f.name.slice(0,-5));
  takenCache={names:new Set(names),ts:Date.now()};
  return takenCache.names;
}
function setResult(html){resultEl.innerHTML=html;}
function linkFor(name,labelKey){
  const base=`https://github.com/${GITHUB_REPO}/issues/new?template=register.yml`;
  const q=`&title=${encodeURIComponent('Subdomain registration')}&request-type=${encodeURIComponent('Register a new subdomain')}&subdomain=${encodeURIComponent(name)}`;
  return `<a href="${base}${q}" target="_blank" rel="noopener">${fmt(t(labelKey),{d:name+'.oxyd.space'})}</a>`;
}
function isValidName(raw){
  const labels=raw.split('.');
  if(labels.length<1||labels.length>MAX_LABELS)return false;
  return labels.every(l=>LABEL_RE.test(l)&&!l.startsWith('xn--'));
}
async function check(){
  const raw=input.value.trim().toLowerCase().replace(/\.oxyd\.space$/,'').replace(/^https?:\/\//,'');
  if(!isValidName(raw)){
    setResult(`<span class="bad">${t('checker.invalid')}</span>`);return;
  }
  const labels=raw.split('.');
  const lastHit=labels[labels.length-1];
  if(reservedSet.has(lastHit)){
    setResult(`<span class="bad">${fmt(t('checker.reserved'),{d:lastHit+'.'})}</span>`);return;
  }
  checkBtn.disabled=true;
  setResult(`<span class="info">${t('checker.checking')}</span>`);
  try{
    const names=await loadTaken();
    if(names.has(raw)){
      setResult(`<span class="bad">${fmt(t('checker.taken'),{d:raw+'.oxyd.space'})}</span>`);
    }else{
      setResult(`<span class="ok">${fmt(t('checker.available'),{d:raw+'.oxyd.space'})}</span>${linkFor(raw,'checker.register')}`);
    }
  }catch{
    setResult(`<span class="bad">${t('checker.error')}</span>`);
  }finally{
    checkBtn.disabled=false;
  }
}
checkBtn.addEventListener('click',check);
input.addEventListener('keydown',e=>{if(e.key==='Enter')check();});

(async()=>{
  try{
    const names=await loadTaken();
    document.getElementById('statClaimed').textContent=names.size;
  }catch{
    document.getElementById('statClaimed').textContent='—';
  }
})();

applyLang();
