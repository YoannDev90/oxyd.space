# Contributing to oxyd.space

Thanks for your interest in contributing! Here's how to get started.

## Development setup

```bash
git clone https://github.com/YoannDev90/oxyd.space.git
cd oxyd.space
```

### Local site

```bash
cd website
npm install
npm run dev
```

Site at `http://localhost:4321`.

### Scripts

Scripts are in `scripts/`. Run directly:

```bash
python3 scripts/validate.py
python3 scripts/process_issue.py
```

## Project structure

```
oxyd.space/
├── website/              # Astro site
│   ├── src/pages/        # Pages (propagation, dashboard, checker, etc.)
│   ├── public/assets/    # Static assets (dns.json, countries-110m.json)
│   └── astro.config.mjs
├── scripts/              # Python scripts (bot, health checks, validation)
├── config/               # Domain config, reserved names
├── domains/              # Registered subdomain configs
├── supabase/             # Edge functions (dns-propagate)
├── docs/                 # Documentation
└── .github/workflows/    # CI/CD (deploy, dns-health)
```

## Code style

- **Python:** ruff (rules in `ruff.toml`), pre-commit hooks enforce formatting
- **JS/TS:** vanilla, no framework overhead in client scripts
- **CSS:** CSS variables from `global.css`, no Tailwind/Bootstrap
- **Astro:** `<style is:global>` for shared styles, inline `<script>` for page logic

## Submitting changes

1. Fork the repo
2. Create a branch (`git checkout -b feat/my-feature`)
3. Commit with clear messages (`feat:`, `fix:`, `chore:`, etc.)
4. Open a PR against `main`

Pre-commit hooks run automatically on commit (ruff, end-of-file-fixer, check-yaml).

## Reporting issues

- **Bugs:** Open an issue with steps to reproduce
- **Security:** See [SECURITY.md](SECURITY.md) — do NOT open public issues for vulnerabilities
- **Feature requests:** Open an issue describing the use case
