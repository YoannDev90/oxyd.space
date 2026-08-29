(function () {
  var svg = d3.select('#map');
  var W = 960, H = 500;
  var proj = d3.geoNaturalEarth1().scale(153).translate([W / 2, H / 2]);
  var path = d3.geoPath(proj);

  var defs = svg.append('defs');
  var glow = defs.append('filter').attr('id', 'glow').attr('x', '-50%').attr('y', '-50%').attr('width', '200%').attr('height', '200%');
  glow.append('feGaussianBlur').attr('stdDeviation', '2').attr('result', 'blur');
  glow.append('feMerge').selectAll('feMergeNode').data(['blur', 'SourceGraphic']).join('feMergeNode').attr('in', function (d) { return d; });

  var gMain = svg.append('g');

  var zoom = d3.zoom().scaleExtent([1, 12]).on('zoom', function (e) {
    gMain.attr('transform', e.transform);
    gMain.selectAll('.srv-dot').attr('r', 3 / e.transform.k);
  });
  svg.call(zoom);

  gMain.append('path').datum({ type: 'Sphere' }).attr('class', 'sphere').attr('d', path);
  gMain.append('path').datum(d3.geoGraticule().step([30, 30])()).attr('class', 'graticule').attr('d', path);

  var dotByIp = {};

  function drawDots(servers) {
    var dotsG = gMain.append('g');
    var dotData = dotsG.selectAll('g').data(servers).join('g').attr('transform', function (d) {
      var p = proj([d.lng, d.lat]);
      return 'translate(' + p[0] + ',' + p[1] + ')';
    });
    dotData.append('circle')
      .attr('class', 'srv-dot')
      .attr('r', 3)
      .attr('fill', '#2a3a50')
      .attr('opacity', 0.5)
      .attr('filter', 'url(#glow)')
      .append('title').text(function (d) { return d.label + ' (' + d.city + ', ' + d.country + ')'; });
    dotData.each(function (d) { dotByIp[d.ip] = this.querySelector('circle'); });
  }

  function setDot(ip, status) {
    var c = dotByIp[ip];
    if (!c) return;
    if (status === 'success') { c.setAttribute('fill', '#34d399'); c.setAttribute('opacity', 1); }
    else { c.setAttribute('fill', '#f87171'); c.setAttribute('opacity', 1); }
  }

  function resetDots() {
    Object.keys(dotByIp).forEach(function (ip) {
      var c = dotByIp[ip];
      c.setAttribute('fill', '#2a3a50');
      c.setAttribute('opacity', 0.5);
    });
  }

  var domainEl, rtypeEl, goBtn, out, grid, doneEl, okEl, failEl, progressFill, totalEl, elapsedEl;
  var servers = [];

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  function insertRow(node) {
    var rows = grid.children;
    var ms = node._ms == null ? Infinity : node._ms;
    var pos = rows.length;
    for (var k = 0; k < rows.length; k++) {
      var rms = rows[k]._ms == null ? Infinity : rows[k]._ms;
      if (ms < rms) { pos = k; break; }
    }
    if (pos < rows.length) grid.insertBefore(node, rows[pos]);
    else grid.appendChild(node);
  }

  function renderSummary(done, total, t0) {
    var ok = 0;
    for (var i = 0; i < done.length; i++) if (done[i].ok) ok++;
    doneEl.textContent = done.length;
    totalEl.textContent = total;
    okEl.textContent = ok;
    failEl.textContent = total - ok;
    progressFill.style.width = Math.round(done.length / total * 100) + '%';
    if (done.length === total) elapsedEl.textContent = Math.round(performance.now() - t0) + 'ms total';
  }

  function buildCard(j) {
    var card = el('div', 'srv-card ' + (j.ok ? 'ok' : 'err'));
    card.append(el('span', 'dot ' + (j.ok ? 'ok' : 'err')));
    var info = el('div', 'info');
    info.append(el('span', 'name', j.flag + ' ' + j.label));
    info.append(el('span', 'region', j.city + ', ' + j.country + ' · ' + j.ip));
    card.appendChild(info);
    var res = el('div', 'result');
    res.append(el('span', 'ips', j.ips || '—'));
    var msEl = el('span', 'ms' + (j.ms != null && j.ms < 100 ? ' fast' : (j.ms != null && j.ms > 500 ? ' slow' : '')), j.ms != null ? j.ms + 'ms' : 'timeout');
    res.appendChild(msEl);
    card.appendChild(res);
    card._ms = j.ms == null ? null : j.ms;
    return card;
  }

  async function query(d, s) {
    var controller = new AbortController();
    var timer = setTimeout(function () { controller.abort(); }, 8000);
    try {
      var r = await fetch('https://dnsrobot.net/api/dns-query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        signal: controller.signal,
        body: JSON.stringify({ domain: d, recordType: rtypeEl.value, dnsServer: s.ip, timeout: 5000 })
      });
      var j = await r.json();
      var ok = j.status === 'success';
      var ips = Array.isArray(j.resolvedIPs) ? j.resolvedIPs.join(', ') : (j.resolvedData || '—');
      return { ok: ok, ips: ips, ms: j.responseTime != null ? Math.round(j.responseTime) : null };
    } catch (e) {
      return { ok: false, ips: '—', ms: null };
    } finally {
      clearTimeout(timer);
    }
  }

  async function runPool(items, worker, limit) {
    var i = 0;
    async function one() {
      while (i < items.length) {
        var idx = i++;
        await worker(items[idx], idx);
      }
    }
    var workers = [];
    for (var k = 0; k < Math.min(limit, items.length); k++) workers.push(one());
    await Promise.all(workers);
  }

  async function check() {
    var d = domainEl.value.trim().toLowerCase().replace(/^https?:\/\//, '').split('/')[0];
    if (!d) return;
    goBtn.disabled = true;
    goBtn.textContent = 'Checking…';
    resetDots();
    out.querySelector('.results-header').style.display = 'flex';
    grid.innerHTML = '';
    progressFill.style.width = '0%';
    elapsedEl.textContent = '';
    doneEl.textContent = '0';
    okEl.textContent = '0';
    failEl.textContent = '0';

    var t0 = performance.now();
    var done = [];
    await runPool(servers, async function (s) {
      var r = await query(d, s);
      var entry = { ok: r.ok, ip: s.ip, label: s.label, country: s.country, city: s.city, flag: s.flag, ips: r.ips, ms: r.ms };
      done.push(entry);
      setDot(s.ip, r.ok ? 'success' : 'error');
      var card = buildCard(entry);
      insertRow(card);
      renderSummary(done, servers.length, t0);
    }, 64);

    elapsedEl.textContent = Math.round(performance.now() - t0) + 'ms total';
    goBtn.disabled = false;
    goBtn.textContent = 'Check';
  }

  function boot() {
    domainEl = document.getElementById('domain');
    rtypeEl = document.getElementById('rtype');
    goBtn = document.getElementById('go');
    out = document.getElementById('resultsArea');
    grid = document.getElementById('resultsGrid');
    doneEl = document.getElementById('doneCount');
    okEl = document.getElementById('okCount');
    failEl = document.getElementById('failCount');
    progressFill = document.getElementById('progressFill');
    totalEl = document.getElementById('totalCount');
    elapsedEl = document.getElementById('elapsed');

    goBtn.addEventListener('click', check);
    domainEl.addEventListener('keydown', function (e) { if (e.key === 'Enter') check(); });

    Promise.all([
      fetch('/assets/dns.json').then(function (r) { return r.json(); }),
      d3.json('https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json')
    ]).then(function (pair) {
      servers = pair[0];
      var world = pair[1];
      gMain.append('g')
        .selectAll('path').data(topojson.feature(world, world.objects.countries).features).join('path')
        .attr('class', 'land').attr('d', path);
      gMain.append('path')
        .datum(topojson.mesh(world, world.objects.countries, function (a, b) { return a !== b; }))
        .attr('class', 'border').attr('d', path);
      document.getElementById('srvCount').textContent = servers.length;
      drawDots(servers);
    }).catch(function (e) {
      document.getElementById('srvCount').textContent = '–';
    });
  }

  boot();
})();
