#!/usr/bin/env python3
import base64
import json
import os
import re
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import update_dns as udn
import validate as v

GITHUB_API = "https://api.github.com"
TITLE_PREFIX_REG = "Subdomain registration"
TITLE_PREFIX_REDIRECT = "Subdomain redirect"

LABEL_REQUEST = "What do you want to do?"
LABEL_BASE = "Base domain"
LABEL_SUBDOMAIN = "Subdomain name"
LABEL_RTYPE = "Record type"
LABEL_RVALUE = "Record value"
LABEL_EXTRA = "Additional DNS records (optional)"
LABEL_WWW = "Enable www prefix"
LABEL_TERMS = "Terms"

REDIRECT_DESTINATION = "Destination URL"
REDIRECT_TYPE = "Redirect type"

REQ_REGISTER = "Register a new subdomain"
REQ_UPDATE = "Update my records"
REQ_DELETE = "Delete my subdomain"

REDIRECT_CENTER = "redirect.center"
REDIRECT_TTL_INITIAL = 900
REDIRECT_TTL_FINAL = 3600


def parse_form(body):
    sections, current, buf = {}, None, []
    for line in body.splitlines():
        if line.startswith("### "):
            if current is not None:
                sections[current] = "\n".join(buf).strip()
            current, buf = line[4:].strip(), []
        elif current is not None:
            buf.append(line)
    if current is not None:
        sections[current] = "\n".join(buf).strip()
    return sections


def clean(value):
    return str(value or "").strip().strip("`").strip()


def checkbox_checked(block):
    return bool(re.search(r"- \[[xX]\]", block or ""))


def resolve_base_domain(raw):
    value = clean(raw).lower().rstrip(".")
    for zone in v.ZONES:
        if value == zone:
            return zone
    return None


def normalize_subdomain(raw, domain):
    value = clean(raw).lower().replace(" ", "")
    value = re.sub(r"^https?://", "", value)
    value = value.split("/")[0]
    if value.endswith(f".{domain}"):
        value = value[: -len(domain) - 1]
    return value.rstrip(".")


def parse_extra_records(block):
    records, errors = [], []
    for lineno, line in enumerate((block or "").splitlines(), 1):
        line = line.strip()
        if not line or line == "_No response_":
            continue
        tokens = line.split()
        if len(tokens) < 2:
            errors.append(
                f"additional record line {lineno}: expected 'TYPE VALUE', got '{line}'"
            )
            continue
        rtype = tokens[0].upper()
        if rtype not in v.ALLOWED_TYPES:
            errors.append(
                f"additional record line {lineno}: unknown type '{tokens[0]}'"
            )
            continue
        rec = {"type": rtype, "value": tokens[1]}
        for flag in tokens[2:]:
            if flag.startswith("ttl="):
                try:
                    rec["ttl"] = int(flag[4:])
                except ValueError:
                    errors.append(f"additional record line {lineno}: bad ttl '{flag}'")
            else:
                errors.append(
                    f"additional record line {lineno}: unknown option '{flag}'"
                )
        records.append(rec)
    return records, errors


def fetch_remote_file(repo, path, token):
    status, data = v.api_request(
        f"{GITHUB_API}/repos/{repo}/contents/{path}", token=token
    )
    if status == 200 and isinstance(data, dict) and data.get("sha"):
        content = ""
        try:
            content = base64.b64decode(data.get("content") or "").decode()
        except Exception:
            pass
        return {"sha": data["sha"], "content": content}
    return None


def post_comment(repo, number, body, token):
    status, _ = v.api_request(
        f"{GITHUB_API}/repos/{repo}/issues/{number}/comments",
        token=token,
        method="POST",
        body={"body": body},
    )
    if status not in (200, 201):
        raise RuntimeError(f"comment failed: HTTP {status}")


def finish_issue(repo, number, ok, body, label, token):
    status, existing = v.api_request(
        f"{GITHUB_API}/repos/{repo}/issues/{number}/comments?per_page=100", token=token
    )
    prev = next(
        (
            c
            for c in (existing or [])
            if "<!-- oxyd-issue-bot -->" in (c.get("body") or "")
        ),
        None,
    )
    url = prev["url"] if prev else f"{GITHUB_API}/repos/{repo}/issues/{number}/comments"
    v.api_request(
        url, token=token, method="PATCH" if prev else "POST", body={"body": body}
    )
    v.api_request(
        f"{GITHUB_API}/repos/{repo}/issues/{number}",
        token=token,
        method="PATCH",
        body={"state": "closed", "state_reason": "completed" if ok else "not_planned"},
    )
    v.api_request(
        f"{GITHUB_API}/repos/{repo}/issues/{number}/labels",
        token=token,
        method="POST",
        body={"labels": [label]},
    )


def build_redirect_cname(destination, status_code="301"):
    """Build a redirect.center CNAME value from a destination URL."""
    parsed = urllib.parse.urlparse(destination)
    host = parsed.hostname or ""
    port = parsed.port
    path = parsed.path or "/"
    scheme = parsed.scheme or "https"

    parts = [host]
    if path and path != "/":
        for segment in path.strip("/").split("/"):
            if segment:
                parts.append("opts-slash")
                parts.append(segment)
        parts.append("opts-slash")
    if scheme == "https":
        parts.append("opts-https")
    if status_code in ("302", "307", "308"):
        parts.append(f"opts-statuscode-{status_code}")
    if port and port not in (80, 443):
        parts.append(f"opts-port-{port}")
    parts.append(REDIRECT_CENTER)
    return ".".join(parts) + "."


def process_redirect_issue(issue, token, repo):
    """Handle a redirect issue: create a CNAME via redirect.center."""
    number = issue["number"]
    author = (issue.get("user") or {}).get("login", "")
    body = issue.get("body") or ""

    sections = parse_form(body)

    missing = [
        line
        for line in (
            LABEL_BASE,
            LABEL_SUBDOMAIN,
            REDIRECT_DESTINATION,
            REDIRECT_TYPE,
            LABEL_TERMS,
        )
        if not sections.get(line)
    ]
    if missing:
        fail_redirect(
            repo,
            number,
            [
                "this issue does not use the redirect template. "
                "Please open a new one via the 'Subdomain redirect' template."
            ],
            token,
        )
        return

    domain = resolve_base_domain(sections[LABEL_BASE])
    stem = normalize_subdomain(sections[LABEL_SUBDOMAIN], domain)
    destination = clean(sections[REDIRECT_DESTINATION])
    redirect_type_raw = clean(sections[REDIRECT_TYPE])
    terms_ok = checkbox_checked(sections[LABEL_TERMS])

    status_code = "301" if "301" in redirect_type_raw else "302"

    errors = []

    if domain is None:
        errors.append(
            f"'{clean(sections[LABEL_BASE])}' is not a base domain managed here; "
            f"pick one from the dropdown: {', '.join(v.ZONES)}"
        )
    if not stem:
        errors.append("subdomain is empty")
    if not terms_ok:
        errors.append("you must accept the terms to create a redirect")

    if destination:
        parsed = urllib.parse.urlparse(destination)
        if not parsed.scheme or not parsed.hostname:
            errors.append("destination must be a full URL (e.g. https://example.com)")
        elif parsed.scheme not in ("http", "https"):
            errors.append("destination must use http:// or https://")

    name_errors = v.validate_name(stem) if stem else ["subdomain is empty"]
    errors.extend(name_errors)

    user_status, user_data = v.api_request(f"{GITHUB_API}/users/{author}", token=token)
    ghid = user_data.get("id", 0) if user_status == 200 and user_data else 0
    if not ghid:
        errors.append("could not verify your GitHub account; try again later")

    path = f"{v.DOMAINS_DIR}/{domain}/{stem}.json" if stem and domain else None
    remote = None
    if stem and domain:
        remote = fetch_remote_file(repo, path, token)
        if remote:
            errors.append(
                f"{stem}.{domain} already exists — delete it first or choose another name"
            )
        previous_owner = None
        if remote:
            previous_owner = v.parse_owner(remote["content"])
            if previous_owner and previous_owner.lower() != author.lower():
                errors.append(f"you do not own {stem}.{domain}")

    if errors:
        fail_redirect(repo, number, errors, token)
        return

    cfg = {
        "owner": {
            "github": author,
            "github_id": ghid,
        },
        "redirect_to": destination,
        "redirect_status": status_code,
    }

    fqdn = f"{stem}.{domain}"
    pretty = json.dumps(cfg, indent=2, ensure_ascii=False) + "\n"
    encoded = base64.b64encode(pretty.encode()).decode()

    status, _ = v.api_request(
        f"{GITHUB_API}/repos/{repo}/contents/{path}",
        token=token,
        method="PUT",
        body={
            "message": f"redirect({author}): {stem}.{domain} → {destination}",
            "content": encoded,
        },
    )
    if status not in (200, 201):
        fail_redirect(
            repo,
            number,
            [f"could not write the configuration (HTTP {status}); try again."],
            token,
        )
        return

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(pretty)

    success_text = (
        "<!-- oxyd-issue-bot -->\n"
        f"## ✅ Redirect created\n\n"
        f"Hey @{author}, your redirect is configured:\n\n"
        f"- 🌐 **{fqdn}** → `{destination}`\n"
        f"- 📋 Type: {status_code} {'(permanent)' if status_code == '301' else '(temporary)'}\n\n"
        f"DNS changes will propagate within ~15 minutes. "
        f"This issue is now closed — open a new 'Subdomain redirect' issue to modify it later."
    )
    finish_issue(repo, number, True, success_text, "redirect-created", token)
    print(success_text.replace("**", ""))
    print(f"\nIssue #{number} processed: redirect {fqdn} → {destination}")

    print("\nSyncing DNS…")
    try:
        udn.main(zone_filter=domain)
    except SystemExit as e:
        print(f"warning: DNS sync exited with code {e}", file=sys.stderr)
    except Exception as e:
        print(f"warning: DNS sync failed: {e}", file=sys.stderr)
        post_comment(
            repo,
            number,
            "⚠️ The configuration was committed but the DNS sync failed. "
            "A maintainer can re-run the **Update DNS** workflow.",
            token,
        )


def fail_redirect(repo, number, messages, token):
    listing = "\n".join(f"- ❌ {m}" for m in messages)
    text = (
        "<!-- oxyd-issue-bot -->\n## ❌ Redirect rejected\n\n"
        f"{listing}\n\nFix the issues above and open a new request."
    )
    finish_issue(repo, number, False, text, "invalid", token)
    print(text.replace("<br>", "\n"))
    print("\nIssue closed as invalid.")


def main():
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")

    if not event_path or not os.path.exists(event_path):
        print("No GitHub event: nothing to do (local run).")
        return

    with open(event_path, encoding="utf-8") as fh:
        event = json.load(fh)
    issue = event.get("issue") or {}
    if issue.get("pull_request") or event.get("action") not in ("opened", "reopened"):
        print("Not a fresh issue, skipping.")
        return
    number = issue["number"]
    author = (issue.get("user") or {}).get("login", "")
    title = issue.get("title", "")
    body = issue.get("body") or ""

    if not repo or not token:
        raise RuntimeError("GITHUB_TOKEN / GITHUB_REPOSITORY are required")

    if title.startswith(TITLE_PREFIX_REDIRECT):
        process_redirect_issue(issue, token, repo)
        return

    if not title.startswith(TITLE_PREFIX_REG):
        print(
            f"Issue title does not start with '{TITLE_PREFIX_REG}' or '{TITLE_PREFIX_REDIRECT}', skipping."
        )
        return

    def fail(messages):
        listing = "\n".join(f"- ❌ {m}" for m in messages)
        text = (
            "<!-- oxyd-issue-bot -->\n## ❌ Registration rejected\n\n"
            f"{listing}\n\nFix the issues above and open a new request."
        )
        finish_issue(repo, number, False, text, "invalid", token)
        print(text.replace("<br>", "\n"))
        print("\nIssue closed as invalid.")

    sections = parse_form(body)

    missing = [
        line
        for line in (
            LABEL_REQUEST,
            LABEL_BASE,
            LABEL_SUBDOMAIN,
            LABEL_RTYPE,
            LABEL_RVALUE,
            LABEL_TERMS,
        )
        if not sections.get(line)
    ]
    if missing:
        fail(
            [
                "this issue does not use the registration template. "
                "Please open a new one via the 'Subdomain registration' template."
            ]
        )
        return

    request = clean(sections[LABEL_REQUEST])
    domain = resolve_base_domain(sections[LABEL_BASE])
    stem = normalize_subdomain(sections[LABEL_SUBDOMAIN], domain)
    rtype = clean(sections[LABEL_RTYPE]).upper()
    rvalue = clean(sections[LABEL_RVALUE])
    terms_ok = checkbox_checked(sections[LABEL_TERMS])
    want_www = checkbox_checked(sections[LABEL_WWW])

    # Fetch GitHub user ID from API
    user_status, user_data = v.api_request(f"{GITHUB_API}/users/{author}", token=token)
    ghid = user_data.get("id", 0) if user_status == 200 and user_data else 0
    if not ghid:
        errors = ["could not verify your GitHub account; try again later"]
        fail(errors)
        return

    extra_records, extra_errors = parse_extra_records(sections.get(LABEL_EXTRA))
    errors = list(extra_errors)

    if request not in (REQ_REGISTER, REQ_UPDATE, REQ_DELETE):
        errors.append(f"unknown request type '{request}'")
    if domain is None:
        errors.append(
            f"'{clean(sections[LABEL_BASE])}' is not a base domain managed here; "
            f"pick one from the dropdown: {', '.join(v.ZONES)}"
        )
    if not stem:
        errors.append("subdomain is empty")
    if not terms_ok:
        errors.append("you must accept the terms to get a subdomain")

    records = []
    if rtype not in v.ALLOWED_TYPES:
        errors.append(f"record type must be one of {sorted(v.ALLOWED_TYPES)}")
    elif rvalue:
        records.append({"type": rtype, "value": rvalue})
    records.extend(extra_records)

    seen = set()
    for rec in records:
        key_norm = (
            rec["type"],
            str(rec["value"]).lower() if rec["type"] != "TXT" else rec["value"],
        )
        if key_norm in seen:
            errors.append(f"duplicate record {rec['type']} {rec['value']}")
        seen.add(key_norm)

    cfg = {
        "owner": {
            "github": author,
            "github_id": ghid,
        },
        "records": records,
    }
    if want_www:
        cfg["www"] = True

    name_errors = v.validate_name(stem) if stem else ["subdomain is empty"]
    errors.extend(name_errors)

    path = f"{v.DOMAINS_DIR}/{domain}/{stem}.json" if stem and domain else None
    local_exists = path and os.path.exists(path)
    remote = None
    if stem and domain and request in (REQ_UPDATE, REQ_DELETE):
        remote = fetch_remote_file(repo, path, token)
        if remote is None:
            errors.append(
                f"{stem}.{domain} does not exist — nothing to update or delete"
            )
        else:
            previous_owner = v.parse_owner(remote["content"])
            if previous_owner is None or previous_owner.lower() != author.lower():
                errors.append(
                    f"you do not own {stem}.{domain}; transfers are not allowed"
                )
    elif (
        stem
        and domain
        and request == REQ_REGISTER
        and (local_exists or fetch_remote_file(repo, path, token))
    ):
        errors.append(f"{stem}.{domain} is already taken")

    holdings = v.count_owner_domains(author)
    if request == REQ_REGISTER and holdings + 1 > v.MAX_DOMAINS_PER_USER:
        errors.append(
            f"@{author} already owns {holdings} subdomains (max {v.MAX_DOMAINS_PER_USER})"
        )

    if request != REQ_DELETE:
        config_errors, _ = v.validate_config(
            stem,
            json.dumps(cfg),
            expected_owner=author,
            users=v.UserIdentityCache(token),
        )
        errors.extend(config_errors)

    if errors:
        fail(errors)
        return

    fqdn = f"{stem}.{domain}"

    pretty = json.dumps(cfg, indent=2, ensure_ascii=False) + "\n"

    if request == REQ_DELETE:
        status, _ = v.api_request(
            f"{GITHUB_API}/repos/{repo}/contents/{path}",
            token=token,
            method="DELETE",
            body={"message": f"delete({author}): {fqdn}", "sha": remote["sha"]},
        )
        if status not in (200, 204):
            fail(
                [
                    f"could not delete the file (HTTP {status}); maybe a concurrent change? Try again."
                ]
            )
            return
        if local_exists:
            os.remove(path)
        verb = "deleted"
    else:
        encoded = base64.b64encode(pretty.encode()).decode()
        put_body = {
            "message": f"{'update' if request == REQ_UPDATE else 'register'}({author}): {stem}.{domain}",
            "content": encoded,
        }
        if request == REQ_UPDATE:
            put_body["sha"] = remote["sha"]
        status, data = v.api_request(
            f"{GITHUB_API}/repos/{repo}/contents/{path}",
            token=token,
            method="PUT",
            body=put_body,
        )
        if status not in (200, 201):
            fail(
                [
                    f"could not write the configuration (HTTP {status}); the name may have just been taken. Try again."
                ]
            )
            return
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(pretty)
        verb = "updated" if request == REQ_UPDATE else "registered"

    fqdns = [f"**{fqdn}**"]
    if want_www and request != REQ_DELETE:
        fqdns.append(f"**www.{fqdn}**")

    rows = (
        "\n".join(f"| `{r['type']}` | `{r['value']}` |" for r in records)
        if request != REQ_DELETE
        else "_all records removed_"
    )

    success_text = (
        "<!-- oxyd-issue-bot -->\n"
        f"## ✅ Subdomain {verb}\n\n"
        f"Hey @{author}, here is your configuration:\n\n"
        + "\n".join(f"- 🌐 {f}" for f in fqdns)
        + "\n\n"
        + (
            "| Type | Value |\n|---|---|\n" + rows + "\n"
            if request != REQ_DELETE
            else ""
        )
        + "\nDNS changes propagate within minutes (deSEC TTLs allow fast updates). "
        "This issue is now closed — open a new 'Subdomain registration' issue to modify it later."
    )
    finish_issue(repo, number, True, success_text, verb, token)
    print(success_text.replace("**", ""))
    print(f"\nIssue #{number} processed: {verb} {fqdn}")

    print("\nSyncing DNS…")
    try:
        udn.main(zone_filter=domain)
    except SystemExit as e:
        print(f"warning: DNS sync exited with code {e}", file=sys.stderr)
    except Exception as e:
        print(f"warning: DNS sync failed: {e}", file=sys.stderr)
        post_comment(
            repo,
            number,
            "⚠️ The configuration was committed but the DNS sync failed. "
            "A maintainer can re-run the **Update DNS** workflow.",
            token,
        )


if __name__ == "__main__":
    main()
