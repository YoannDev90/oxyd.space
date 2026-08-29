# deSEC API

Free DNS hosting, used for oxyd.space subdomains.

**Base URL:** `https://desec.io/api/v1`

## Authentication

```
Authorization: Token <token>
```

Each zone has its own token, stored encrypted in `config/secrets.enc.json` (SOPS/AGE).

## Endpoints

### List all RRsets

```
GET /domains/{zone}/rrsets/
```

Returns a paginated list. Use `Link` header for pagination.

Filter by type/subname:

```
GET /domains/{zone}/rrsets/?type=CNAME&subname=rickroll
```

### Create / Update RRsets (batch)

```
PATCH /domains/{zone}/rrsets/
Content-Type: application/json

[
  {
    "subname": "rickroll",
    "type": "CNAME",
    "ttl": 900,
    "records": ["target.example.com."],
    "comment": "oxyd-auto: redirect"
  }
]
```

- Body **must be a list** (not a dict)
- Creates if not exists, updates if exists
- Returns `200` with updated RRsets

### Delete RRset

Set `records` to empty list via PATCH:

```
PATCH /domains/{zone}/rrsets/

[
  {
    "subname": "rickroll",
    "type": "CNAME",
    "ttl": 60,
    "records": [],
    "comment": ""
  }
]
```

## TXT records

TXT record values **must be wrapped in double quotes**:

```json
{
  "subname": "_discord",
  "type": "TXT",
  "ttl": 3600,
  "records": ["\"dh=ff122cbb5dd189a1132f329b17e190c8e5c34a28\""],
  "comment": "oxyd-auto: discord verification"
}
```

Without quotes, deSEC returns `400: Data for TXT records must be given using quotation marks.`

## Common errors

| HTTP | Meaning | Fix |
|------|---------|-----|
| 400 `non_field_errors: Another RRset exists` | Used POST instead of PATCH, or body is dict instead of list | Use `PATCH /rrsets/` with a list |
| 400 `non_field_errors: Expected a list` | Body is a dict | Wrap in `[{...}]` |
| 404 `No RRset matches` | Individual RRset endpoint (`/rrsets/CNAME/name/`) does not exist in v2 | Use batch PATCH on `/rrsets/` |
| 404 `Domain not found` | Zone doesn't exist in account | Create it on desec.io first |
| 429 | Rate limited | Retry with exponential backoff |

## Key points

- **No individual RRset endpoints** — `PATCH /rrsets/CNAME/name/` returns 404 in API v2
- **Batch only** — all create/update/delete operations go through `PATCH /rrsets/` with a list
- **POST also takes a list** — `POST /rrsets/` expects `[ {...}, {...} ]`
- TTLs: initial redirect = 900s, upgraded after 4h = 3600s
