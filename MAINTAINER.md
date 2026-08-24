# Maintainer guide

Stack: **GitHub Pages** (landing), **GitHub Actions** (bot), **deSEC** (DNS) — 100% free tiers. This guide is for the repository owner only; contributors only ever touch the issue template.

## 1. Secrets: sops + age (one GitHub secret only)

All DNS tokens live in `config/secrets.enc.json`, encrypted with [sops](https://github.com/getsops/sops) using an **age** key. GitHub stores exactly one secret: `SOPS_AGE_KEY`.

1. Install the tools: `mise use sops age` (pinned by `mise.toml`) or grab binaries from their releases.
2. Generate a keypair if needed and keep `key.txt` safe (password manager):

   ```bash
   age-keygen -o key.txt        # prints the public key, stores the private one
   ```

3. Put the public key into [.sops.yaml](.sops.yaml).
4. Create and fill the vault:

   ```bash
   cp config/secrets.example.json config/secrets.enc.json
   sops -e -i config/secrets.enc.json         # encrypt in place (uses .sops.yaml)
   EDITOR=nano sops config/secrets.enc.json   # edit tokens; saving re-encrypts
   ```

5. Install the private key once for local CLI use (scripts + editing) — no env vars needed afterwards:

   ```bash
   mkdir -p ~/.config/sops/age && cp key.txt ~/.config/sops/age/keys.txt
   ```

6. Commit `config/secrets.enc.json` — it is ciphertext, that's the point. Never commit `key.txt`.
7. On GitHub: *Settings → Secrets and variables → Actions* → new secret **`SOPS_AGE_KEY`** = full contents of `key.txt`. That is the only secret needed.
8. Losing `key.txt` means re-encrypting with a new keypair and rotating every token.

## 2. Your first zone (oxyd.space)

1. Sign up at [desec.io](https://desec.io) (free), add the domain `oxyd.space`.
2. Namecheap → Domain List → Manage → **Nameservers** → Custom DNS → deSEC's (`ns1.desec.io`, `ns2.desec.org`).
3. Put the zone API token in the vault under its `token_key` (see [`config/domains.json`](config/domains.json)).
4. Recreate the landing page records (deSEC UI or API):

```bash
DESEC_TOKEN=xxx ZONE=oxyd.space
curl -X POST https://desec.io/api/v1/domains/$ZONE/rrsets/ \
  -H "Authorization: Token $DESEC_TOKEN" -H "Content-Type: application/json" \
  -d '{"subname":"","type":"A","ttl":3600,"records":["185.199.108.153.","185.199.109.153.","185.199.110.153.","185.199.111.153."],"comment":"apex"}'
curl -X POST https://desec.io/api/v1/domains/$ZONE/rrsets/ \
  -H "Authorization: Token $DESEC_TOKEN" -H "Content-Type: application/json" \
  -d '{"subname":"www","type":"CNAME","ttl":3600,"records":["YoannDev90.github.io."],"comment":"apex"}'
```

> Why not Cloudflare? Free zones created after Sept 2024 are capped at **200 DNS records** — fatal for a public registry. deSEC has none.

## 3. Onboard another domain

Anyone can offer their own domain through your bot:

1. They create a free deSEC account, add their domain, point their registrar NS at deSEC, hand you an API token scoped to that domain.
2. Add the token: `sops config/secrets.enc.json` → new key, e.g. `"desec_token_sondomaine_fr": "…"`.
3. Register the zone in [`config/domains.json`](config/domains.json):

   ```json
   { "domain": "sondomaine.fr", "token_key": "desec_token_sondomaine_fr", "public": true }
   ```

4. Subdomain files then live under `domains/sondomaine.fr/<name>.json`; quotas, reserved names and identity checks apply globally.
5. Add the domain to the **Base domain** dropdown in `.github/ISSUE_TEMPLATE/register.yml` (keep it in sync).

## 4. Publish the landing page

*Settings → Pages → Source: Deploy from a branch → `main` / `(root)`*, custom domain `oxyd.space` (the `CNAME` file handles it), enable *Enforce HTTPS* once the certificate is issued.

## 5. Moderation

- The bot only auto-processes issues titled `Subdomain registration`; everything else lands as a normal issue.
- Levers against abuse: edit [`config/reserved_names.txt`](config/reserved_names.txt), close+lock issues, temporarily disable issues, or delete a `domains/<zone>/*.json` file (next sync removes the records).
- A partner domain misbehaving? Remove its entry from `config/domains.json` and delete its directory — nothing else gets touched.
- Commits by the bot do not trigger the push-based DNS sync (GitHub recursion guard); the bot runs the sync itself right after committing.

## Testing locally

```bash
python3 scripts/validate.py                        # validate every domains/<zone>/*.json
OXYD_DRY_RUN=true python3 scripts/update_dns.py    # plan without any secret
OXYD_ZONE=oxyd.space python3 scripts/update_dns.py # real sync, one zone (needs local age key)
```

All Python scripts are stdlib-only — no `pip install`.

## Security notes

- Tokens never appear in plaintext on GitHub; CI decrypts in memory via `SOPS_AGE_KEY`.
- Only rrsets tagged `oxyd-auto` are managed by the sync — apex/www records of every zone are safe.
- Identity is anchored on the numeric GitHub ID (stable across renames); ownership transfers require manual action — the bot rejects them.
