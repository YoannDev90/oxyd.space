#!/usr/bin/env python3
import ipaddress
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

DOMAINS_DIR = "domains"
CONFIG_FILE = os.path.join("config", "domains.json")
RESERVED_FILE = os.path.join("config", "reserved_names.txt")
DEFAULT_ZONE = "oxyd.space"
MAX_LABELS = 4
MAX_DOMAINS_PER_USER = 10
MAX_RECORDS = 10
ALLOWED_TYPES = {"CNAME", "A", "AAAA", "TXT"}
TTL_MIN, TTL_MAX = 60, 86400
TIMEOUT = 10
MARKER = "<!-- oxyd-validator-report -->"

LABEL_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$")
USERNAME_RE = re.compile(r"^[a-zA-Z\d](?:[a-zA-Z\d]|-(?=[a-zA-Z\d])){0,38}$")
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
HOSTNAME_LABEL_RE = re.compile(r"^[a-z0-9]([a-z0-9_-]{0,61}[a-z0-9])?$")


def load_reserved():
    names = set()
    try:
        with open(RESERVED_FILE, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip().lower()
                if line and not line.startswith("#"):
                    names.add(line)
    except FileNotFoundError:
        print(f"warning: {RESERVED_FILE} not found, no reserved names loaded")
    return names


RESERVED = load_reserved()


def load_zones():
    try:
        with open(CONFIG_FILE, encoding="utf-8") as fh:
            data = json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        print(f"warning: {CONFIG_FILE} missing or invalid, falling back to '{DEFAULT_ZONE}'")
        return [DEFAULT_ZONE]
    zones = [
        entry["domain"].lower()
        for entry in (data.get("zones") or [])
        if isinstance(entry, dict) and isinstance(entry.get("domain"), str)
    ]
    if not zones:
        print(f"warning: no zones listed in {CONFIG_FILE}, falling back to '{DEFAULT_ZONE}'")
        return [DEFAULT_ZONE]
    return zones


ZONES = load_zones()


def iter_config_paths():
    """Yield (zone, stem, path) for every subdomain config file."""
    if not os.path.isdir(DOMAINS_DIR):
        return
    for zdir in sorted(os.listdir(DOMAINS_DIR)):
        zpath = os.path.join(DOMAINS_DIR, zdir)
        if not os.path.isdir(zpath) or zdir.startswith(("_", ".")):
            continue
        for fname in sorted(os.listdir(zpath)):
            if fname.endswith(".json") and not fname.startswith(("_", ".")):
                yield zdir.lower(), fname[:-5], os.path.join(zpath, fname)


def config_relpath(zone, stem):
    """Repo-relative path used both on disk and against the GitHub API."""
    return f"{DOMAINS_DIR}/{zone}/{stem}.json"


def count_owner_domains(owner):
    owner = (owner or "").lower()
    total = 0
    for _, _, path in iter_config_paths():
        with open(path, encoding="utf-8") as fh:
            if (parse_owner(fh.read()) or "").lower() == owner:
                total += 1
    return total


def is_valid_label(label):
    return bool(LABEL_RE.match(label)) and not label.startswith("xn--")


def is_valid_hostname(value):
    if not isinstance(value, str) or not (0 < len(value.rstrip(".")) <= 253):
        return False
    labels = value.rstrip(".").lower().split(".")
    if len(labels) < 2:
        return False
    if not all(HOSTNAME_LABEL_RE.match(l) for l in labels):
        return False
    return bool(re.fullmatch(r"[a-z]{2,63}", labels[-1]))


def git(*args):
    proc = subprocess.run(["git", *args], capture_output=True, text=True)
    return proc.stdout if proc.returncode == 0 else None


def base_domain_paths(base_sha):
    out = git("ls-tree", "-r", "--name-only", base_sha, DOMAINS_DIR + "/")
    return [l for l in out.splitlines() if l.strip()] if out else []


def base_file_content(base_sha, path):
    return git("show", f"{base_sha}:{path}")


def parse_owner(content):
    try:
        owner = json.loads(content).get("owner")
        if isinstance(owner, dict) and isinstance(owner.get("github"), str):
            return owner["github"]
    except (json.JSONDecodeError, AttributeError):
        pass
    return None


def api_request(url, token=None, method="GET", body=None):
    data = None
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as res:
            raw = res.read().decode()
            return res.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, None


def gh_paginate(path, token):
    items, page = [], 1
    while True:
        status, batch = api_request(f"https://api.github.com/{path}?per_page=100&page={page}", token=token)
        if status != 200 or not isinstance(batch, list):
            raise RuntimeError(f"GitHub API {path} failed: HTTP {status}")
        items.extend(batch)
        if len(batch) < 100:
            return items
        page += 1


class UserIdentityCache:
    def __init__(self, token=None):
        self.token = token
        self.cache = {}

    def get_id(self, login):
        key = login.lower()
        if key not in self.cache:
            status, data = api_request(f"https://api.github.com/users/{login}", token=self.token)
            if status == 404:
                self.cache[key] = ("error", f"'{login}' is not a valid GitHub username")
            elif status != 200 or not isinstance(data, dict):
                self.cache[key] = ("unavailable", f"HTTP {status}")
            else:
                self.cache[key] = ("ok", data["id"])
        return self.cache[key]


def validate_config(name_labels, raw_json, *, expected_owner=None, users=None):
    errors, warnings = [], []
    try:
        cfg = json.loads(raw_json)
    except json.JSONDecodeError as e:
        return [f"invalid JSON: {e}"], warnings
    if not isinstance(cfg, dict):
        return ["root must be a JSON object"], warnings

    for key in cfg:
        if key not in ("owner", "records", "www"):
            errors.append(f'unknown top-level key "{key}"')

    owner = cfg.get("owner")
    if not isinstance(owner, dict):
        errors.append('"owner" object is required')
        owner = {}
    for key in owner:
        if key not in ("github", "github_id", "name", "email", "url"):
            errors.append(f'unknown owner field "{key}"')
    github = owner.get("github")
    github_id = owner.get("github_id")
    if not isinstance(github, str) or not USERNAME_RE.match(github):
        errors.append('"owner.github" must be a valid GitHub username')
    if isinstance(github_id, bool) or not isinstance(github_id, int) or github_id < 1:
        errors.append('"owner.github_id" must be your numeric GitHub user ID (integer > 0)')
    if "name" in owner and (not isinstance(owner["name"], str) or not (1 <= len(owner["name"]) <= 100)):
        errors.append('"owner.name" must be a string of 1-100 characters')
    if "email" in owner:
        email = owner["email"]
        if not isinstance(email, str) or not EMAIL_RE.match(email or ""):
            errors.append('"owner.email" must be a valid email address')
    if "url" in owner:
        url = owner["url"]
        if not isinstance(url, str) or not url.startswith("https://") or len(url) > 200:
            errors.append('"owner.url" must be an https:// URL (max 200 chars)')
    if "www" in cfg and not isinstance(cfg["www"], bool):
        errors.append('"www" must be true or false')

    if expected_owner and isinstance(github, str) and github.lower() != expected_owner.lower():
        errors.append(f'"owner.github" must be your own account ({expected_owner})')

    if users and isinstance(github, str) and USERNAME_RE.match(github) and isinstance(github_id, int) and not isinstance(github_id, bool):
        state, value = users.get_id(github)
        if state == "error":
            errors.append(f"identity check failed: {value}")
        elif state == "unavailable":
            warnings.append(f"could not verify github_id ({value}), continuing anyway")
        elif value != github_id:
            errors.append(f"github_id mismatch: {github}'s real ID is {value}, file says {github_id}")

    records = cfg.get("records")
    if not isinstance(records, list) or len(records) == 0:
        errors.append('"records" must be a non-empty array')
        records = []
    elif len(records) > MAX_RECORDS:
        errors.append(f"too many records (max {MAX_RECORDS})")
    for i, rec in enumerate(records):
        ref = f"records[{i}]"
        if not isinstance(rec, dict):
            errors.append(f"{ref} must be an object")
            continue
        for key in rec:
            if key not in ("type", "value", "ttl"):
                errors.append(f'{ref}: unknown field "{key}"')
        rtype = rec.get("type")
        value = rec.get("value")
        if rtype not in ALLOWED_TYPES:
            errors.append(f"{ref}: type must be one of {sorted(ALLOWED_TYPES)}")
            continue
        if isinstance(value, str):
            value = value.strip()
        if rtype == "CNAME":
            normalized = value.rstrip(".") if isinstance(value, str) else value
            if not is_valid_hostname(normalized):
                errors.append(f"{ref}: invalid CNAME target hostname")
        elif rtype == "A":
            try:
                if ipaddress.ip_address(value).version != 4:
                    raise ValueError
            except (ValueError, TypeError):
                errors.append(f"{ref}: value must be a valid IPv4 address")
        elif rtype == "AAAA":
            try:
                if ipaddress.ip_address(value).version != 6:
                    raise ValueError
            except (ValueError, TypeError):
                errors.append(f"{ref}: value must be a valid IPv6 address")
        elif rtype == "TXT":
            if not isinstance(value, str) or not (1 <= len(value) <= 255):
                errors.append(f"{ref}: TXT value must be a string of 1-255 characters")
        if "ttl" in rec:
            ttl = rec["ttl"]
            if isinstance(ttl, bool) or not isinstance(ttl, int) or not (TTL_MIN <= ttl <= TTL_MAX):
                errors.append(f"{ref}: ttl must be an integer between {TTL_MIN} and {TTL_MAX}")

    if records and not any(isinstance(r, dict) and r.get("type") == "CNAME" for r in records):
        warnings.append("no CNAME record: make sure you know how to use A/AAAA/TXT records")
    return errors, warnings


def validate_name(stem):
    errors = []
    labels = stem.split(".")
    if len(labels) > MAX_LABELS:
        errors.append(f"'{stem}' has too many levels (max {MAX_LABELS}, e.g. s1.service.yourname)")
    for label in labels:
        if not is_valid_label(label):
            errors.append(f"'{label}' is not a valid label (a-z, 0-9, hyphens; no leading/trailing hyphen)")
    if labels and labels[-1].lower() in RESERVED:
        errors.append(
            f"'{labels[-1]}' is reserved and cannot end a name; put your own namespace last instead, "
            f"e.g. {'.'.join(labels[:-1] + ['yourname'])}.{DEFAULT_ZONE}"
        )
    return errors


def check_reachability(targets):
    results = []
    for target in targets[:10]:
        req = urllib.request.Request(f"https://{target}/", method="HEAD")
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as res:
                results.append((target, True))
        except urllib.error.HTTPError:
            results.append((target, True))
        except Exception:
            results.append((target, False))
    return results


def build_report(rows, problems_count):
    lines = [MARKER, "## 🧪 Validation report", ""]
    if rows:
        lines += ["| File | Status | Details |", "|---|---|---|"]
        for path, ok, details in rows:
            icon = "✅" if ok else "❌"
            lines.append(f"| `{path}` | {icon} | {details or 'looks good'} |")
    else:
        lines.append("No subdomain registration found.")
    lines.append("")
    if problems_count:
        lines.append(f"**{problems_count} blocking issue(s).**")
    else:
        lines.append("**All checks passed.** ✅")
    return "\n".join(lines)


def run_local_mode():
    files = list(iter_config_paths())
    if not files:
        print(f"No subdomain files under {DOMAINS_DIR}/<zone>/, nothing to validate.")
        return 0
    problems = []
    for zone, stem, path in files:
        if zone not in ZONES:
            problems.append(f"{path}: unknown zone '{zone}' (not listed in {CONFIG_FILE})")
        errs = validate_name(stem)
        with open(path, encoding="utf-8") as fh:
            cfg_errs, _ = validate_config(stem, fh.read())
        errs.extend(cfg_errs)
        problems.extend(f"{path}: {e}" for e in errs)
    for p in problems:
        print(f"❌ {p}")
    if problems:
        print(f"\nValidation FAILED with {len(problems)} problem(s).")
        return 1
    zones_touched = sorted({z for z, _, _ in files})
    print(f"All {len(files)} domain file(s) across {len(zones_touched)} zone(s) are valid. ✅")
    return 0


def main():
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path or not os.path.exists(event_path):
        sys.exit(run_local_mode())
    print("PR-based registration is retired; registrations are handled through issues.")
    return 0


if __name__ == "__main__":
    main()
