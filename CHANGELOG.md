# Changelog

## [1.1.0] - 2026-08-29

### Added
- **DNS Propagation Checker** — rebuilt from scratch with Astro + Supabase edge functions
  - Queries 394+ global DNS servers via `Deno.resolveDns` on Supabase Edge Runtime
  - Parallel chunked queries (25 servers/chunk, `Promise.all`) — full check in ~10s
  - Interactive SVG map (d3 geoNaturalEarth1) with pan/zoom, server dots colored by status
  - Expandable map overlay (fullscreen toggle)
  - Group servers by country (`Intl.DisplayNames`, zero dependencies)
  - 2-column responsive card layout
  - Summary bar (ok/empty/failed + elapsed) at top of results
- **Weekly DNS health check** — GitHub Actions workflow (`dns-health.yml`)
  - Probes 10 seed domains per server via raw UDP sockets (stdlib, zero pip)
  - 30s budget per server, deactivates non-responders
  - Auto-reactivation when servers come back online
  - Safety guard: aborts if >50% of fleet looks dead
  - Commits changes to `dns.json` and dispatches site rebuild
- `active` field on all 599 DNS servers in `dns.json`
- `lastChecked` timestamps from health probes

### Changed
- Migrated site from Jekyll to Astro (static output, zero JS overhead)
- DNS propagation checker now queries servers directly (no dnsrobot.net)
- Client rewritten: vanilla JS pan/zoom, no d3 at runtime
- Deploy workflow: Astro build → force-push `dist/` to `live` branch

### Fixed
- Deploy workflow `cd dist` path (outputs to repo root, not `website/dist`)
- CSS deploy race conditions (stale builds from uncommitted edits)
- Country grid showing 4 columns instead of stacking vertically
- Summary bar too close to results grid
- Form button missing right padding

## [1.0.0] - 2026-08-26

### Added
- **oxyd.space** — personal tools hub on GitHub Pages
  - Landing page with tools registry
  - Availability checker page
  - Changelog page (dynamic markdown rendering)
- **Personal dashboard** with GitHub OAuth via Supabase
  - Notification preferences with Supabase DB
- i18n translations extracted to JSON
- Unified navbar across all pages
- Jekyll-based site with clean URLs
- CI/CD: GitHub Actions deploy workflow (Jekyll → `live` branch)
- DNS server list: 600+ global resolvers with geolocation (lat/lng)
