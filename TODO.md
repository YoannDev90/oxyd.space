# TODO — oxyd.space

> Free subdomain service (like is-a.dev) — GitHub Pages + GitHub Actions + deSEC.io DNS

---

## Completed

- [x] Fix JS syntax error (apostrophes in FR strings) — 🔴 HIGH
- [x] Update `.gitignore` with all cache/build dirs — 🔴 HIGH
- [x] Move `og-image.png` → `assets/` + update refs — 🟡 MEDIUM
- [x] Commit and push all changes — 🟡 MEDIUM
- [x] Landing page (i18n EN/FR, dark theme, SVG logo, OG/Twitter meta, JSON-LD)
- [x] Availability Checker page (`/checker`)
- [x] DNS Propagation Checker page (`/propagation`, 32 DNS servers, D3.js map)
- [x] CSS/JS extracted to `assets/css` + `assets/js`
- [x] Section "Tools" on landing page
- [x] Jekyll setup (front matter permalinks, `_config.yml`)
- [x] Pre-commit hooks (ruff linting)
- [x] CI lint workflow (ruff==0.8.0)
- [x] Issue template registration (clear descriptions, no GitHub ID)
- [x] `process_issue.py` (auto GitHub user ID via API)
- [x] AI documentation (`docs/registration.md`)
- [x] 9 utility scripts (dns_health_check, ssl_checker, subdomain_explorer, orphan_detector, health_monitor, audit_log, local_dev_server, test_integration, validate)

---

## To Do

- [x] Changelog page (`/changelog`) — 🟡 MEDIUM
- [ ] Redirect Manager (via GitHub issue, option 1: mini-repo redirect) — 🟡 MEDIUM
- [ ] GitHub OAuth Device Flow (personal dashboard) — 🟡 MEDIUM
- [ ] Rate limiting on DNS API — 🟡 MEDIUM
- [ ] Monitoring uptime (UptimeRobot / BetterStack) — 🟢 LOW

---

## Blocked / Waiting on User

- [ ] CNAME `www` in deSEC UI — 🔴 HIGH (manual step)
- [ ] Add secret `SOPS_AGE_KEY` on GitHub — 🔴 HIGH (manual step)
