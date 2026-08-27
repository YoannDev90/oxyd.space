/**
 * Dashboard for oxyd.space — manage subdomains via GitHub OAuth Device Flow.
 * All logic is client-side. Creates GitHub Issues that the existing bot processes.
 */
(async function () {
  var i18n = await initI18n('dashboard');
  var t = i18n.t;
  var fmt = i18n.fmt;

  var GITHUB_REPO = GitHubOAuth.REPO;
  var GITHUB_API = 'https://api.github.com';
  var DOMAINS_DIR = 'domains';

  // DOM refs
  var loginScreen = document.getElementById('login-screen');
  var deviceScreen = document.getElementById('device-screen');
  var dashScreen = document.getElementById('dashboard-screen');
  var formOverlay = document.getElementById('formOverlay');

  var loginBtn = document.getElementById('loginBtn');
  var logoutBtn = document.getElementById('logoutBtn');
  var registerBtn = document.getElementById('registerBtn');
  var copyCodeBtn = document.getElementById('copyCode');

  var userAvatar = document.getElementById('userAvatar');
  var userName = document.getElementById('userName');
  var userEmail = document.getElementById('userEmail');
  var subdomainCount = document.getElementById('subdomainCount');
  var openIssueCount = document.getElementById('openIssueCount');
  var limitCount = document.getElementById('limitCount');
  var subdomainList = document.getElementById('subdomainList');
  var issueList = document.getElementById('issueList');
  var notifSsl = document.getElementById('notifSsl');
  var notifDomain = document.getElementById('notifDomain');
  var notifUpdates = document.getElementById('notifUpdates');
  var saveNotifBtn = document.getElementById('saveNotifBtn');

  var formTitle = document.getElementById('formTitle');
  var formSubdomain = document.getElementById('formSubdomain');
  var formDomain = document.getElementById('formDomain');
  var formRtype = document.getElementById('formRtype');
  var formRvalue = document.getElementById('formRvalue');
  var formExtra = document.getElementById('formExtra');
  var formWww = document.getElementById('formWww');
  var formSubmit = document.getElementById('formSubmit');
  var formStatus = document.getElementById('formStatus');
  var formClose = document.getElementById('formClose');

  var userCode = null;
  var authUrl = null;
  var authStatus = document.getElementById('authStatus');

  var currentUser = null;
  var mySubdomains = [];
  var myIssues = [];
  var token = null;
  var userEmailAddr = null;

  function showScreen(screen) {
    loginScreen.hidden = true;
    deviceScreen.hidden = true;
    dashScreen.hidden = true;
    screen.hidden = false;
  }

  function escapeHtml(s) {
    return s.replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function formatDate(iso) {
    var d = new Date(iso);
    return d.toLocaleDateString(document.documentElement.lang === 'fr' ? 'fr-FR' : 'en-US', {
      year: 'numeric', month: 'short', day: 'numeric'
    });
  }

  // ── API helpers ──────────────────────────────────────────────────────

  function ghFetch(path) {
    var headers = {
      'Accept': 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28'
    };
    if (token) headers['Authorization'] = 'Bearer ' + token;
    return fetch(GITHUB_API + path, { headers: headers });
  }

  function ghPost(path, body) {
    return fetch(GITHUB_API + path, {
      method: 'POST',
      headers: {
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
        'Authorization': 'Bearer ' + token,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(body)
    });
  }

  // ── Load user's subdomains ───────────────────────────────────────────

  async function loadMySubdomains() {
    var resp = await ghFetch('/repos/' + GITHUB_REPO + '/contents/' + DOMAINS_DIR);
    if (!resp.ok) return [];
    var zones = await resp.json();
    var results = [];

    for (var i = 0; i < zones.length; i++) {
      var zone = zones[i];
      if (zone.type !== 'dir' || zone.name.startsWith('_') || zone.name.startsWith('.')) continue;

      var filesResp = await ghFetch('/repos/' + GITHUB_REPO + '/contents/' + DOMAINS_DIR + '/' + zone.name);
      if (!filesResp.ok) continue;
      var files = await filesResp.json();

      for (var j = 0; j < files.length; j++) {
        var file = files[j];
        if (!file.name.endsWith('.json') || file.name.startsWith('_')) continue;

        var cfgResp = await ghFetch(file.url.replace(GITHUB_API, ''));
        if (!cfgResp.ok) continue;
        var cfgData = await cfgResp.json();
        var content = atob(cfgData.content);
        var config;
        try { config = JSON.parse(content); } catch (e) { continue; }

        if (config.owner && config.owner.github &&
            config.owner.github.toLowerCase() === currentUser.login.toLowerCase()) {
          results.push({
            zone: zone.name,
            name: file.name.replace('.json', ''),
            config: config,
            sha: cfgData.sha,
            path: DOMAINS_DIR + '/' + zone.name + '/' + file.name
          });
        }
      }
    }
    return results;
  }

  // ── Load user's registration issues ──────────────────────────────────

  async function loadMyIssues() {
    var allIssues = [];
    var page = 1;
    while (true) {
      var resp = await ghFetch(
        '/repos/' + GITHUB_REPO + '/issues?labels=registration&state=all&per_page=100&page=' + page
      );
      if (!resp.ok) break;
      var batch = await resp.json();
      if (!batch.length) break;
      allIssues = allIssues.concat(batch);
      if (batch.length < 100) break;
      page++;
    }
    return allIssues.filter(function (issue) {
      return issue.user && issue.user.login === currentUser.login;
    });
  }

  // ── Build issue body (exact format process_issue.py expects) ─────────

  function buildIssueBody(request, domain, subdomain, rtype, rvalue, extraRecords, www) {
    var lines = [];
    lines.push('### What do you want to do?');
    lines.push(request);
    lines.push('');
    lines.push('### Base domain');
    lines.push(domain);
    lines.push('');
    lines.push('### Subdomain name');
    lines.push(subdomain);
    lines.push('');
    lines.push('### Record type');
    lines.push(rtype);
    lines.push('');
    lines.push('### Record value');
    lines.push(rvalue);
    if (extraRecords && extraRecords.trim()) {
      lines.push('');
      lines.push('### Additional DNS records (optional)');
      lines.push(extraRecords.trim());
    }
    lines.push('');
    lines.push('### Enable www prefix');
    lines.push(www ? '- [x] Yes, also create www.<subdomain>' : '- [ ] Yes, also create www.<subdomain>');
    lines.push('');
    lines.push('### Terms');
    lines.push('- [x] I will not use this subdomain for phishing, malware, spam or illegal content');
    lines.push('- [x] I understand the service is provided as-is and may be discontinued');
    return lines.join('\n');
  }

  // ── Create issue ─────────────────────────────────────────────────────

  async function createIssue(requestType, domain, subdomain, rtype, rvalue, extra, www) {
    var body = buildIssueBody(requestType, domain, subdomain, rtype, rvalue, extra, www);
    var resp = await ghPost('/repos/' + GITHUB_REPO + '/issues', {
      title: 'Subdomain registration',
      body: body,
      labels: ['registration']
    });
    if (!resp.ok) {
      var err = await resp.json().catch(function () { return {}; });
      throw new Error(err.message || 'HTTP ' + resp.status);
    }
    return resp.json();
  }

  // ── Render functions ─────────────────────────────────────────────────

  function renderStats() {
    subdomainCount.textContent = mySubdomains.length;
    openIssueCount.textContent = myIssues.filter(function (i) { return i.state === 'open'; }).length;
    limitCount.textContent = mySubdomains.length + '/10';
  }

  function renderSubdomains() {
    subdomainList.innerHTML = '';
    if (mySubdomains.length === 0) {
      subdomainList.innerHTML = '<p class="empty-state" data-i18n="subdomain.empty">' +
        escapeHtml(t('subdomain.empty')) + '</p>';
      return;
    }

    for (var i = 0; i < mySubdomains.length; i++) {
      var sub = mySubdomains[i];
      var fqdn = sub.name + '.' + sub.zone;
      var records = (sub.config.records || []);
      var www = sub.config.www ? ' · www' : '';
      var owner = sub.config.owner || {};
      var ownerName = owner.github || 'unknown';
      var ownerId = owner.github_id || '—';

      var recordsHtml = records.map(function (r) {
        return '<span class="record-chip"><em>' + escapeHtml(r.type) + '</em> ' + escapeHtml(r.value) + '</span>';
      }).join('');

      var card = document.createElement('div');
      card.className = 'subdomain-card';
      card.innerHTML =
        '<div class="subdomain-card-header">' +
          '<h3 class="subdomain-name">' + escapeHtml(fqdn) + www + '</h3>' +
          '<div class="subdomain-actions">' +
            '<button class="lang-btn action-btn action-update" data-idx="' + i + '" data-i18n="subdomain.update">' + escapeHtml(t('subdomain.update')) + '</button>' +
            '<button class="lang-btn action-btn action-delete" data-idx="' + i + '" data-i18n="subdomain.delete">' + escapeHtml(t('subdomain.delete')) + '</button>' +
          '</div>' +
        '</div>' +
        '<div class="subdomain-records">' + recordsHtml + '</div>' +
        '<div class="subdomain-meta">' +
          '<span class="subdomain-meta-item">' + escapeHtml(t('subdomain.owner')) + ': @' + escapeHtml(ownerName) + ' (#' + escapeHtml(String(ownerId)) + ')</span>' +
        '</div>';
      subdomainList.appendChild(card);
    }

    subdomainList.querySelectorAll('.action-update').forEach(function (btn) {
      btn.addEventListener('click', function () {
        showUpdateForm(mySubdomains[parseInt(btn.dataset.idx)]);
      });
    });

    subdomainList.querySelectorAll('.action-delete').forEach(function (btn) {
      btn.addEventListener('click', function () {
        confirmDelete(mySubdomains[parseInt(btn.dataset.idx)]);
      });
    });
  }

  function renderIssues() {
    issueList.innerHTML = '';
    var open = myIssues.filter(function (i) { return i.state === 'open'; });
    var closed = myIssues.filter(function (i) { return i.state === 'closed'; }).slice(0, 5);

    if (open.length === 0 && closed.length === 0) {
      issueList.innerHTML = '<p class="empty-state" data-i18n="issue.empty">' +
        escapeHtml(t('issue.empty') || 'No registration requests yet.') + '</p>';
      return;
    }

    var shown = open.concat(closed);
    for (var i = 0; i < shown.length; i++) {
      var issue = shown[i];
      var isClosed = issue.state === 'closed';
      var badge = isClosed ? 'badge-closed' : 'badge-open';
      var badgeText = isClosed ? t('issue.closed') : t('issue.open');

      var card = document.createElement('div');
      card.className = 'issue-card';
      card.innerHTML =
        '<div class="issue-card-header">' +
          '<a href="' + escapeHtml(issue.html_url) + '" target="_blank" rel="noopener" class="issue-link">#' + issue.number + '</a>' +
          '<span class="status-badge ' + badge + '">' + escapeHtml(badgeText) + '</span>' +
        '</div>' +
        '<p class="issue-title">' + escapeHtml(issue.title) + '</p>' +
        '<time class="issue-date">' + formatDate(issue.created_at) + '</time>';
      issueList.appendChild(card);
    }
  }

  // ── Forms ────────────────────────────────────────────────────────────

  function showRegisterForm() {
    formTitle.textContent = t('form.title.register');
    formSubdomain.value = '';
    formSubdomain.readOnly = false;
    formDomain.value = 'oxyd.space';
    formRtype.value = 'CNAME';
    formRvalue.value = '';
    formExtra.value = '';
    formWww.checked = false;
    formStatus.textContent = '';
    formStatus.className = 'form-status';
    formSubmit.textContent = t('form.submit.register');
    formOverlay.hidden = false;
    formSubdomain.focus();
  }

  function showUpdateForm(sub) {
    formTitle.textContent = t('form.title.update');
    formSubdomain.value = sub.name;
    formSubdomain.readOnly = true;
    formDomain.value = sub.zone;
    var first = (sub.config.records || [])[0];
    if (first) {
      formRtype.value = first.type;
      formRvalue.value = first.value;
    } else {
      formRtype.value = 'CNAME';
      formRvalue.value = '';
    }
    var extras = (sub.config.records || []).slice(1).map(function (r) {
      return r.type + ' ' + r.value;
    }).join('\n');
    formExtra.value = extras;
    formWww.checked = !!sub.config.www;
    formStatus.textContent = '';
    formStatus.className = 'form-status';
    formSubmit.textContent = t('form.submit.update');
    formOverlay.hidden = false;
    formSubdomain.focus();
  }

  function closeForm() {
    formOverlay.hidden = true;
  }

  function confirmDelete(sub) {
    var fqdn = sub.name + '.' + sub.zone;
    if (!confirm(fmt(t('confirm.body'), { name: fqdn }))) return;
    submitDelete(sub);
  }

  async function submitDelete(sub) {
    formStatus.textContent = t('form.creating');
    formStatus.className = 'form-status info';
    try {
      var issue = await createIssue(
        'Delete my subdomain', sub.zone, sub.name,
        'CNAME', '-', '', false
      );
      formStatus.innerHTML = '<a href="' + escapeHtml(issue.html_url) + '" target="_blank" rel="noopener">' +
        fmt(t('form.success'), { number: issue.number }) + '</a>';
      formStatus.className = 'form-status ok';
      loadAll();
    } catch (err) {
      formStatus.textContent = t('form.error') + ' ' + err.message;
      formStatus.className = 'form-status bad';
    }
  }

  async function submitRegistration() {
    var request = formSubdomain.readOnly ? 'Update my records' : 'Register a new subdomain';
    var subdomain = formSubdomain.value.trim().toLowerCase();
    var domain = formDomain.value;
    var rtype = formRtype.value;
    var rvalue = formRvalue.value.trim();
    var extra = formExtra.value.trim();
    var www = formWww.checked;

    if (!subdomain) {
      formStatus.textContent = t('form.subdomain') + ' ?';
      formStatus.className = 'form-status bad';
      return;
    }
    if (!rvalue) {
      formStatus.textContent = t('form.rvalue') + ' ?';
      formStatus.className = 'form-status bad';
      return;
    }

    formSubmit.disabled = true;
    formStatus.textContent = t('form.creating');
    formStatus.className = 'form-status info';

    try {
      var issue = await createIssue(request, domain, subdomain, rtype, rvalue, extra, www);
      formStatus.innerHTML = '<a href="' + escapeHtml(issue.html_url) + '" target="_blank" rel="noopener">' +
        fmt(t('form.success'), { number: issue.number }) + '</a>';
      formStatus.className = 'form-status ok';
      setTimeout(function () {
        closeForm();
        loadAll();
      }, 2000);
    } catch (err) {
      formStatus.textContent = t('form.error') + ' ' + err.message;
      formStatus.className = 'form-status bad';
    } finally {
      formSubmit.disabled = false;
    }
  }

  // ── Auth flow ────────────────────────────────────────────────────────

  async function handleOAuthRedirect() {
    var handled = await GitHubOAuth.handleRedirect();
    if (!handled) return false;

    showScreen(deviceScreen);
    authStatus.textContent = t('auth.exchanging');
    authStatus.className = 'auth-status';

    try {
      token = GitHubOAuth.getToken();
      if (!token) throw new Error('No token received');
      currentUser = await GitHubOAuth.getUser(token);
      if (currentUser) {
        await loadDashboard();
        return true;
      }
      GitHubOAuth.clearToken();
      throw new Error('Could not fetch user info');
    } catch (err) {
      authStatus.textContent = t('auth.error') + ' ' + err.message;
      authStatus.className = 'form-status bad';
      setTimeout(function () { showScreen(loginScreen); }, 3000);
    }
    return true;
  }

  function startLogin() {
    GitHubOAuth.login();
  }

  // ── Dashboard init ───────────────────────────────────────────────────

  async function loadDashboard() {
    userAvatar.src = currentUser.avatar_url;
    userName.textContent = currentUser.login;
    userEmailAddr = await GitHubOAuth.getSessionEmail();
    if (userEmail) {
      userEmail.textContent = userEmailAddr || '';
      userEmail.style.display = userEmailAddr ? 'block' : 'none';
    }
    showScreen(dashScreen);
    await loadAll();
    loadNotifPreferences();
  }

  async function loadAll() {
    var results = await Promise.all([loadMySubdomains(), loadMyIssues()]);
    mySubdomains = results[0];
    myIssues = results[1];
    renderStats();
    renderSubdomains();
    renderIssues();
  }

  // ── Notification preferences (Supabase DB) ──────────────────────────

  async function loadNotifPreferences() {
    if (!userEmailAddr) {
      var notifSection = document.getElementById('notif-section');
      if (notifSection) notifSection.style.display = 'none';
      return;
    }
    try {
      var sb = GitHubOAuth.getSupabase();
      if (!sb) return;
      var { data } = await sb.from('user_profiles').select('*').eq('github_id', currentUser.id).single();
      if (data) {
        if (notifSsl) notifSsl.checked = data.notify_ssl_renewal !== false;
        if (notifDomain) notifDomain.checked = data.notify_domain_expiry !== false;
        if (notifUpdates) notifUpdates.checked = data.notify_updates !== false;
      }
    } catch (e) {}
  }

  async function saveNotifPreferences() {
    if (!notifSsl || !notifDomain || !notifUpdates) return;
    try {
      var sb = GitHubOAuth.getSupabase();
      if (!sb) throw new Error('Supabase not initialized');
      var authUser = await GitHubOAuth.getAuthUser();
      if (!authUser) throw new Error('Not authenticated');
      var { error } = await sb.from('user_profiles').upsert({
        id: authUser.id,
        github_id: currentUser.id,
        github_username: currentUser.login,
        email: userEmailAddr,
        notify_ssl_renewal: notifSsl.checked,
        notify_domain_expiry: notifDomain.checked,
        notify_updates: notifUpdates.checked,
        updated_at: new Date().toISOString(),
      }, { onConflict: 'id' });
      if (error) throw error;
      var statusEl = document.getElementById('notifStatus');
      if (statusEl) {
        statusEl.textContent = t('notif.saved');
        statusEl.className = 'form-status ok';
        setTimeout(function () { statusEl.textContent = ''; statusEl.className = 'form-status'; }, 2000);
      }
    } catch (err) {
      var statusEl = document.getElementById('notifStatus');
      if (statusEl) {
        statusEl.textContent = t('form.error') + ' ' + err.message;
        statusEl.className = 'form-status bad';
      }
    }
  }

  // ── Boot ─────────────────────────────────────────────────────────────

  // Attach event listeners FIRST (before async boot can fail/return early)
  loginBtn.addEventListener('click', startLogin);
  logoutBtn.addEventListener('click', function () {
    GitHubOAuth.logout();
    showScreen(loginScreen);
  });
  registerBtn.addEventListener('click', showRegisterForm);
  formClose.addEventListener('click', closeForm);
  formSubmit.addEventListener('click', submitRegistration);
  formOverlay.addEventListener('click', function (e) {
    if (e.target === formOverlay) closeForm();
  });
  if (saveNotifBtn) saveNotifBtn.addEventListener('click', saveNotifPreferences);

  // Then run async boot
  try {
    var handledRedirect = await handleOAuthRedirect();
    if (handledRedirect) return;

    token = GitHubOAuth.getToken();
    if (token) {
      currentUser = await GitHubOAuth.getUser(token);
      if (currentUser) {
        await loadDashboard();
      } else {
        GitHubOAuth.clearToken();
        showScreen(loginScreen);
      }
    } else {
      showScreen(loginScreen);
    }
  } catch (err) {
    console.error('Dashboard boot error:', err);
    showScreen(loginScreen);
  }
})();
