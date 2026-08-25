# oxyd.space

Free subdomains for everyone, powered by open source. Point your project at `yourname.oxyd.space` — one issue form, zero dollars, live in minutes.

**Landing page:** [https://oxyd.space](https://oxyd.space)

## How it works

```mermaid
flowchart LR
    A[Contributor] -->|opens issue| B["GitHub Actions<br/>Process registration"]
    B --> C{Checks pass?}
    C -->|no| D["Issue closed<br/>with reasons"]
    C -->|yes| E["Commit<br/>domains/x.json"]
    E --> F["Sync rrsets<br/>deSEC API"]
    F --> G[("deSEC zone<br/>oxyd.space")]
    G --> H["x.oxyd.space<br/>resolves worldwide"]
```

1. Open an issue using the **Subdomain registration** template (register, update or delete).
2. The bot verifies your identity (`github_id` checked against the GitHub API), applies the rules and commits `domains/<name>.json`.
3. DNS records are pushed to **deSEC** immediately — usually resolving worldwide within minutes.

No pull requests, no forks: everything happens through a controlled issue form.

## Registering a subdomain

Fill in the [registration template](https://github.com/YoannDev90/oxyd.space/issues/new?template=register.yml):

| Field                | Description                                                        |
|----------------------|--------------------------------------------------------------------|
| Request type         | Register / Update / Delete                                          |
| Base domain          | The zone your subdomain lives under (see below)                     |
| Subdomain            | Up to 4 levels — `myname`, `service.myname`, `s1.service.myname`    |
| Record type + value  | CNAME (websites), A/AAAA (servers), TXT (verifications)             |
| Additional records   | Optional, one per line: `TYPE VALUE [ttl=3600]`                     |
| Enable www prefix    | Also publishes `www.<subdomain>` with the same records              |

**Note:** Your GitHub user ID is automatically verified via the GitHub API.

The bot generates the config file for you (stored under `domains/<base-domain>/`):

```json
{
  "owner": {
    "github": "your-github-username",
    "github_id": 12345678
  },
  "records": [
    { "type": "CNAME", "value": "your-github-username.github.io" }
  ],
  "www": false
}
```

### Owner fields

| Field       | Required | Description                                         |
|-------------|----------|-----------------------------------------------------|
| `github`    | yes      | Set automatically to the issue author               |
| `github_id` | yes      | Numeric ID, verified against the GitHub API         |
| `www`       | no       | `true` mirrors all records onto `www.<subdomain>`   |
| `records[].ttl` | no   | Integer between 60 and 86400 (default 3600)         |

### Naming rules

- Up to **4 levels**: `s1.service.yourname.oxyd.space`.
- Labels: `a-z`, `0-9`, hyphens; 1–63 chars each.
- Reserved names ([`config/reserved_names.txt`](config/reserved_names.txt)) **cannot end a name**:

| Request                       | Result |
|-------------------------------|--------|
| `nextcloud.oxyd.space`        | ❌ reserved top-level name |
| `yoann.nextcloud.oxyd.space`  | ❌ cannot end with a reserved word |
| `nextcloud.yoann.oxyd.space`  | ✅ personal instance of Nextcloud |
| `s1.nextcloud.yoann.oxyd.space` | ✅ deeper nesting is fine |

- Max **10 subdomains per GitHub account**, ownership is tied to the issue author account.
- Updates/deletes are only accepted from the current owner. Transfers are not automated.

### Self-hosting examples

| You run…      | Issue form values                                   |
|---------------|------------------------------------------------------|
| Personal site | CNAME → `you.github.io`, www prefix ✅                |
| Nextcloud     | `nextcloud.you` → A/AAAA of your server              |
| Second node   | `s2.nextcloud.you` → A/AAAA of the other server      |

### More base domains

`oxyd.space` is the flagship, but other domain owners can plug **their own domains** into this same bot (same rules, same automation — see [MAINTAINER.md](MAINTAINER.md) → *Onboard another domain*). Available zones are listed in the issue form's **Base domain** dropdown and in [`config/domains.json`](config/domains.json).

### AI-friendly documentation

For automated registration using `gh` CLI or AI assistants, see [docs/registration.md](docs/registration.md). It includes:
- Step-by-step guides for common use cases
- Ready-to-use `gh issue create` commands
- Naming rules and troubleshooting
- AI assistant instructions for helping users

### Domain lifetime

`oxyd.space` is registered **one year at a time**. One month before it expires, the project will move to a cheaper successor domain: every registered subdomain is migrated to the new zone automatically, and the old names are kept as permanent redirects — your links keep working, no action required on your side.

---

## For maintainers

Setup, moderation and operations are documented in [MAINTAINER.md](MAINTAINER.md).
