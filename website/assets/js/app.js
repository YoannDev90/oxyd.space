const GITHUB_REPO = 'YoannDev90/oxyd.space';
const LANDING_ZONE = 'oxyd.space';
const TEMPLATE = { owner:{ github:'your-github-username', github_id:12345678 }, records:[ { type:'CNAME', value:'your-github-username.github.io' } ], www:false };

let reservedSet = new Set();
fetch('https://raw.githubusercontent.com/' + GITHUB_REPO + '/main/config/reserved_names.txt')
  .then(function(r){ return r.ok ? r.text() : ''; })
  .then(function(txt){
    if(!txt)return;
    txt.split('\n').forEach(function(l){
      var name=l.trim().toLowerCase();
      if(name&&!name.startsWith('#'))reservedSet.add(name);
    });
  }).catch(function(){});

(function () {
  function esc(s){return s.replace(/&/g,'&amp;').replace(/</g,'&lt;');}
  function highlight(json){
    return esc(json)
      .replace(/&quot;/g,'"')
      .replace(/"([^"]+)":/g,'<span class="tk-key">"$1"</span>:')
      .replace(/: "([^"]*)"/g,': <span class="tk-str">"$1"</span>');
  }
  function renderSnippet(){
    var json=JSON.stringify(TEMPLATE,null,2);
    document.getElementById('snippetCode').innerHTML=highlight(json);
  }

  async function boot() {
    var i18n = await initI18n('index');

    // FAQ rendering
    var faqList = document.getElementById('faqList');
    if (faqList && i18n.dict.faq) {
      faqList.innerHTML = '';
      i18n.dict.faq.forEach(function(pair) {
        var q = pair[0], a = pair[1];
        var d = document.createElement('details');
        d.className = 'faq-item';
        var s = document.createElement('summary');
        s.textContent = q;
        var p = document.createElement('p');
        p.innerHTML = a;
        d.append(s, p);
        faqList.append(d);
      });
    }

    // Snippet rendering
    renderSnippet();

    var copyBtn = document.getElementById('copyBtn');
    if (copyBtn) {
      copyBtn.addEventListener('click', function() {
        navigator.clipboard.writeText(JSON.stringify(TEMPLATE, null, 2)).then(function() {
          copyBtn.textContent = i18n.t('snippet.copied');
          setTimeout(function() { copyBtn.textContent = i18n.t('snippet.copy'); }, 1600);
        }).catch(function(){});
      });
    }

    // Fetch claimed count
    try {
      var r = await fetch('https://api.github.com/repos/' + GITHUB_REPO + '/contents/domains/' + LANDING_ZONE);
      if (!r.ok) throw new Error('api');
      var j = await r.json();
      var names = (Array.isArray(j) ? j : []).filter(function(f){ return f.name.endsWith('.json'); }).map(function(f){ return f.name.slice(0, -5); });
      document.getElementById('statClaimed').textContent = names.length;
    } catch(e) {
      document.getElementById('statClaimed').textContent = '\u2014';
    }
  }

  boot();
})();
