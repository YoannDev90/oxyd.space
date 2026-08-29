# Security Policy

## Reporting vulnerabilities

If you discover a security vulnerability, **do NOT open a public issue**. Instead:

1. Email **security@oxyd.space** (or open a [private security advisory](https://github.com/YoannDev90/oxyd.space/security/advisories/new))
2. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

You should receive a response within **48 hours**.

## Scope

### In scope

- oxyd.space website and all subdomains
- Subdomain registration bot (GitHub issue processing)
- DNS propagation edge functions (Supabase)
- Supabase authentication and database
- GitHub Actions workflows
- Python scripts in `scripts/`

### Out of scope

- Third-party services (deSEC, BetterStack, Supabase infrastructure)
- Social engineering attacks
- Denial of service

## Supported versions

| Version | Supported |
|---------|-----------|
| v1.1.0  | Yes       |
| < v1.0  | No        |

## Security measures

- GitHub OAuth with minimal scopes
- Supabase RLS (Row Level Security) on all tables
- `verify_jwt: true` on authenticated edge functions
- Pre-commit hooks prevent secrets from being committed
- DNS health checks auto-evict unresponsive resolvers
- Rate limiting on issue processing (10 subdomains/account)

## Secrets

- Never commit `config/secrets.enc.json` or real API keys
- Use `config/secrets.example.json` as a template
- Environment variables preferred for CI/CD secrets
