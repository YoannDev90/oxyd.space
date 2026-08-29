# redirect.center

DNS-based redirect service. Redirects are configured entirely via CNAME records — no server to manage.

**How it works:** The subdomain CNAME points to `redirect.center` with encoded instructions in the hostname labels. The redirect.center server reads the CNAME, decodes the instructions, and issues an HTTP redirect.

## CNAME format

```
<host>.<path-opts>.<query-opts>.<scheme-opts>.<status-opts>.<port-opts>.redirect.center.
```

All parts are joined with `.` and terminated with a trailing `.`.

## Options

| Option | Description | Example |
|--------|-------------|---------|
| `opts-https` | Force HTTPS redirect | `example.com.opts-https.redirect.center.` |
| `opts-uri` | Preserve original path + query string | `example.com.opts-uri.redirect.center.` |
| `opts-slash.{path}` | Append path segment | `example.com.opts-slash.blog.redirect.center.` |
| `opts-path-{base32}` | Base32-encoded path (for special chars) | `example.com.opts-path-mfrgg.redirect.center.` |
| `opts-query-{base32}` | Base32-encoded query string | `example.com.opts-query-nfxgg.redirect.center.` |
| `opts-statuscode-{code}` | HTTP status: 301, 302, 307, 308 | `example.com.opts-statuscode-302.redirect.center.` |
| `opts-port-{port}` | Redirect to specific port | `example.com.opts-port-8080.redirect.center.` |

## Base32 encoding

Query strings and paths with special characters must be **Base32-encoded** (RFC 4648):

1. URL-encode the query: `v=dQw4w9WgXcQ`
2. Base32 encode: `OY6WIULXGR3TSV3HLBRVC`
3. Lowercase + strip padding: `oy6wiulxgr3tsv3hlbrvc`
4. Prepend `opts-query-`: `opts-query-oy6wiulxgr3tsv3hlbrvc`

```python
import base64, urllib.parse

def encode_query_b32(query_string: str) -> str:
    """Base32-encode a query string for redirect.center."""
    b32 = base64.b32encode(query_string.encode()).decode()
    return b32.rstrip("=").lower()

# "v=dQw4w9WgXcQ" → "oy6wiulxgr3tsv3hlbrvc"
# "?v=dQw4w9WgXcQ" → "opts-query-oy6wiulxgr3tsv3hlbrvc"
```

Same for paths: use `opts-path-{base32}` with the path (without leading `/`).

## Examples

### Simple redirect

```bash
# https://example.com → https://new-site.com
example.com.opts-https.redirect.center.
```

### Redirect with path

```bash
# https://example.com → https://new-site.com/blog
example.com.opts-slash.blog.opts-https.redirect.center.
```

### Redirect with query string

```bash
# https://youtube.com/watch?v=dQw4w9WgXcQ
youtube.com.opts-slash.watch.opts-query-oy6wiulxgr3tsv3hlbrvc.opts-https.redirect.center.
```

### 302 temporary redirect

```bash
example.com.opts-https.opts-statuscode-302.redirect.center.
```

### Redirect with port

```bash
example.com.opts-port-8080.opts-https.redirect.center.
```

## DNS propagation

redirect.center respects the CNAME record's TTL. After updating the CNAME on deSEC (TTL 900s), propagation takes ~15 minutes.

## Build function (oxyd.space)

```python
def build_redirect_cname(destination: str, status_code: str = "301") -> str:
    """Build a redirect.center CNAME from a destination URL."""
    import base64 as b64
    parsed = urllib.parse.urlparse(destination)
    host = parsed.hostname or ""
    port = parsed.port
    path = parsed.path or "/"
    scheme = parsed.scheme or "https"
    query = urllib.parse.parse_qs(parsed.query)

    parts = [host]
    if path and path != "/":
        for segment in path.strip("/").split("/"):
            if segment:
                parts.append("opts-slash")
                parts.append(segment)
        parts.append("opts-slash")
    if query:
        query_str = urllib.parse.urlencode(query, doseq=True)
        b32 = b64.b32encode(query_str.encode()).decode().rstrip("=").lower()
        parts.append(f"opts-query-{b32}")
    if scheme == "https":
        parts.append("opts-https")
    if status_code in ("302", "307", "308"):
        parts.append(f"opts-statuscode-{status_code}")
    if port and port not in (80, 443):
        parts.append(f"opts-port-{port}")
    parts.append("redirect.center")
    return ".".join(parts) + "."
```
