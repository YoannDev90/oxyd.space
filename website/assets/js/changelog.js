/**
 * Dynamic changelog loader for oxyd.space
 * Fetches markdown entries from /docs/changelogs/ and renders them into a timeline.
 */
document.addEventListener('DOMContentLoaded', function () {
  var timeline = document.getElementById('changelog-timeline');
  var loading = document.getElementById('changelog-loading');
  var CHANGELOG_DIR = '/docs/changelogs';

  // Category → CSS class mapping
  var CATEGORY_CLASSES = {
    'Added': 'added',
    'Changed': 'changed',
    'Fixed': 'fixed',
    'Removed': 'removed',
    'Improved': 'changed',
    'Documentation': 'changed',
    'CI/CD': 'changed',
    'Maintenance': 'changed',
    'Tests': 'changed',
    'Build': 'changed',
    'Style': 'changed'
  };

  /**
   * Parse YAML front-matter from a markdown string.
   * Returns { meta: {version, date}, body: string }
   */
  function parseFrontMatter(text) {
    var match = text.match(/^---\n([\s\S]*?)\n---\n([\s\S]*)$/);
    if (!match) return { meta: {}, body: text };

    var meta = {};
    var lines = match[1].split('\n');
    for (var i = 0; i < lines.length; i++) {
      var kv = lines[i].split(':');
      if (kv.length >= 2) {
        var key = kv[0].trim();
        var value = kv.slice(1).join(':').trim();
        meta[key] = value;
      }
    }
    return { meta: meta, body: match[2] };
  }

  /**
   * Parse rendered HTML from marked.js into structured category blocks.
   * Takes HTML like "<h2>Added</h2>\n<ul><li>...</li></ul>" and wraps each
   * category in a .change-category div with the appropriate class.
   */
  function wrapCategories(html) {
    var tmp = document.createElement('div');
    tmp.innerHTML = html;

    var result = '';
    var currentCategory = null;
    var currentItems = [];

    var nodes = Array.prototype.slice.call(tmp.childNodes);

    function flushCategory() {
      if (currentCategory) {
        var cls = CATEGORY_CLASSES[currentCategory] || 'changed';
        var itemsHtml = currentItems.join('');
        result += '<div class="change-category ' + cls + '">';
        result += '<h3>' + escapeHtml(currentCategory) + '</h3>';
        result += '<ul>' + itemsHtml + '</ul>';
        result += '</div>';
        currentItems = [];
      }
      currentCategory = null;
    }

    for (var i = 0; i < nodes.length; i++) {
      var node = nodes[i];
      if (node.tagName === 'H2') {
        flushCategory();
        currentCategory = node.textContent.trim();
      } else if (node.tagName === 'UL') {
        var lis = node.querySelectorAll('li');
        for (var j = 0; j < lis.length; j++) {
          currentItems.push('<li>' + lis[j].innerHTML + '</li>');
        }
      }
    }
    flushCategory();
    return result;
  }

  function escapeHtml(str) {
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  /**
   * Build a single changelog entry HTML string.
   */
  function buildEntry(meta, renderedBody) {
    var version = escapeHtml(meta.version || 'unknown');
    var date = escapeHtml(meta.date || '');

    return '<article class="changelog-entry">' +
      '<div class="entry-header">' +
        '<span class="badge">' + version + '</span>' +
        (date ? '<time class="date">' + date + '</time>' : '') +
      '</div>' +
      '<div class="entry-body">' + renderedBody + '</div>' +
    '</article>';
  }

  /**
   * Sort entries by semver (newest first).
   */
  function sortByVersion(entries) {
    return entries.sort(function (a, b) {
      var va = a.meta.version || '';
      var vb = b.meta.version || '';
      // Strip leading 'v' and compare numeric parts
      var pa = va.replace(/^v/, '').split('.').map(Number);
      var pb = vb.replace(/^v/, '').split('.').map(Number);
      for (var i = 0; i < Math.max(pa.length, pb.length); i++) {
        var na = pa[i] || 0;
        var nb = pb[i] || 0;
        if (nb !== na) return nb - na;
      }
      return 0;
    });
  }

  /**
   * Render all entries into the timeline.
   */
  function renderEntries(entries) {
    // Remove loading indicator
    if (loading) loading.remove();

    if (entries.length === 0) {
      var empty = document.createElement('p');
      empty.className = 'changelog-empty';
      empty.textContent = 'No changelog entries found.';
      timeline.appendChild(empty);
      return;
    }

    var sorted = sortByVersion(entries);
    var fragment = document.createDocumentFragment();

    for (var i = 0; i < sorted.length; i++) {
      var entry = sorted[i];
      var wrapper = document.createElement('div');
      wrapper.innerHTML = buildEntry(entry.meta, entry.rendered);
      fragment.appendChild(wrapper.firstChild);
    }

    timeline.appendChild(fragment);
  }

  /**
   * Show an error state in the timeline.
   */
  function showError(message) {
    if (loading) loading.remove();
    var errorDiv = document.createElement('div');
    errorDiv.className = 'changelog-error';
    errorDiv.innerHTML = '<p>' + escapeHtml(message) + '</p>';
    timeline.appendChild(errorDiv);
  }

  /**
   * Fetch and parse all changelog entries.
   */
  async function loadChangelog() {
    // Check if marked.js loaded
    if (typeof marked === 'undefined') {
      showError('Markdown parser failed to load. Please refresh the page.');
      return;
    }

    try {
      var indexUrl = CHANGELOG_DIR + '/index.json';
      var resp = await fetch(indexUrl);
      if (!resp.ok) {
        throw new Error('Failed to fetch changelog index (HTTP ' + resp.status + ')');
      }
      var index = await resp.json();

      var entries = [];

      // Fetch all markdown files concurrently
      var fetches = index.map(function (entry) {
        return fetch(CHANGELOG_DIR + '/' + entry.file)
          .then(function (r) {
            if (!r.ok) throw new Error('Failed to fetch ' + entry.file);
            return r.text();
          });
      });

      var results = await Promise.allSettled(fetches);

      for (var i = 0; i < results.length; i++) {
        if (results[i].status === 'rejected') {
          console.warn('Failed to fetch', index[i].file, results[i].reason);
          continue;
        }
        var body = results[i].value;
        // Support optional YAML front-matter (for local generation)
        var parsed = parseFrontMatter(body);
        var meta = Object.assign({ version: index[i].version, date: index[i].date }, parsed.meta);
        var rawHtml = marked.parse(parsed.body);
        var rendered = wrapCategories(rawHtml);
        entries.push({ meta: meta, body: parsed.body, rendered: rendered });
      }

      renderEntries(entries);

      // Re-apply i18n to dynamically generated content
      if (typeof initI18n === 'function') {
        initI18n('changelog');
      }

    } catch (err) {
      console.error('Changelog load error:', err);
      showError('Failed to load changelog entries. Please try again later.');
    }
  }

  loadChangelog();
});
