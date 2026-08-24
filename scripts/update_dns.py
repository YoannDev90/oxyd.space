#!/usr/bin/env python3
"""Sync every managed zone from config/domains.json with deSEC.

Tokens live in a sops-encrypted config/secrets.enc.json (one key per zone,
see config/secrets.example.json). GitHub only stores the single age private
key as the SOPS_AGE_KEY secret.
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

DESEC_API = "https://desec.io/api/v1"
MANAGED_TAG = "oxyd-auto"
DOMAINS_DIR = "domains"
CONFIG_FILE = os.path.join("config", "domains.json")
SECRETS_FILE = os.path.join("config", "secrets.enc.json")
DEFAULT_TTL = 3600
MAX_RETRIES = 4
TIMEOUT = 30
ALLOWED_TYPES = ("CNAME", "A", "AAAA", "TXT")


def load_zone_registry():
    try:
        with open(CONFIG_FILE, encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        raise RuntimeError(f"{CONFIG_FILE} not found")
    except json.JSONDecodeError as e:
        raise RuntimeError(f"{CONFIG_FILE} is not valid JSON: {e}")
    zones = [z for z in (data.get("zones") or []) if isinstance(z, dict) and z.get("domain")]
    if not zones:
        raise RuntimeError(f"no zones defined in {CONFIG_FILE}")
    for z in zones:
        if not isinstance(z.get("token_key"), str) or not z["token_key"]:
            raise RuntimeError(f"zone {z['domain']}: missing 'token_key' entry in {CONFIG_FILE}")
    return zones


def decrypt_secrets():
    proc = subprocess.run(["sops", "-d", SECRETS_FILE], capture_output=True, text=True)
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        hint = f" ({detail[-1]})" if detail else ""
        raise RuntimeError(f"could not decrypt {SECRETS_FILE}{hint}. Is sops installed and SOPS_AGE_KEY set?")
    return json.loads(proc.stdout)


def token_for(zone_cfg, secrets):
    key = zone_cfg["token_key"]
    token = (secrets or {}).get(key)
    if not token:
        raise RuntimeError(
            f"zone {zone_cfg['domain']}: secret '{key}' not found in {SECRETS_FILE} "
            "(add it with `sops " + SECRETS_FILE + "`)"
        )
    return token


def api(method, path, body=None, token=None):
    data = None
    headers = {"Authorization": f"Token {token}", "Content-Type": "application/json", "Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode()
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        req = urllib.request.Request(f"{DESEC_API}{path}", data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as res:
                raw = res.read().decode()
                return res.status, json.loads(raw) if raw else None
        except urllib.error.HTTPError as e:
            raw = e.read().decode()
            if e.code == 429 or e.code >= 500:
                delay = min(2 ** (attempt - 1), 8)
                print(f"deSEC API HTTP {e.code}, retrying in {delay}s…")
                time.sleep(delay)
                last_error = f"HTTP {e.code}"
                continue
            raise RuntimeError(f"deSEC API {method} {path} failed: HTTP {e.code} {raw[:200]}")
        except urllib.error.URLError as e:
            delay = min(2 ** (attempt - 1), 8)
            print(f"network error ({e.reason}), retrying in {delay}s…")
            time.sleep(delay)
            last_error = str(e.reason)
    raise RuntimeError(f"deSEC API {method} {path} failed after {MAX_RETRIES} attempts ({last_error})")


def pres_content(rtype, value):
    value = str(value).strip()
    if rtype == "CNAME":
        return value.rstrip(".").lower() + "."
    if rtype == "TXT":
        text = value.strip().strip('"')
        chunks = [text[i:i + 255] for i in range(0, len(text), 255)]
        return " ".join(f'"{c}"' for c in chunks)
    return value.lower()


def normalize_subname(value, zone):
    value = str(value).rstrip(".")
    suffix = f".{zone}"
    if value.lower().endswith(suffix.lower()):
        value = value[:-len(suffix)]
    return value.lower()


def load_configs(zone):
    zdir = os.path.join(DOMAINS_DIR, zone)
    configs = []
    if not os.path.isdir(zdir):
        return configs
    for fname in sorted(os.listdir(zdir)):
        if not fname.endswith(".json") or fname.startswith(("_", ".")):
            continue
        label = fname[:-5]
        with open(os.path.join(zdir, fname), encoding="utf-8") as fh:
            try:
                cfg = json.load(fh)
            except json.JSONDecodeError as e:
                raise RuntimeError(f"{DOMAINS_DIR}/{zone}/{fname} is not valid JSON: {e}")
        configs.append((label, cfg))
    return configs


def desired_records(configs):
    desired = {}
    for label, cfg in configs:
        owner = cfg.get("owner") or {}
        tag = MANAGED_TAG + (f" owner=@{owner['github']}" if isinstance(owner.get("github"), str) else "")
        names = [label]
        if cfg.get("www") is True:
            names.append(f"www.{label}")
        for name in names:
            subname = name.lower()
            for rec in cfg.get("records") or []:
                rtype = rec.get("type")
                if rtype not in ALLOWED_TYPES:
                    raise RuntimeError(f"{label}: unsupported record type {rtype!r}")
                content = pres_content(rtype, rec.get("value"))
                key = (subname, rtype)
                entry = desired.setdefault(key, {
                    "subname": subname,
                    "type": rtype,
                    "ttl": rec["ttl"] if isinstance(rec.get("ttl"), int) else DEFAULT_TTL,
                    "records": [],
                    "comment": tag[:255],
                })
                if content not in entry["records"]:
                    entry["records"].append(content)
    for entry in desired.values():
        entry["records"].sort()
    return desired


def fetch_all_rrsets(zone, token):
    rrsets = []
    path = f"/domains/{zone}/rrsets/"
    while path:
        status_code, batch = None, None
        req = urllib.request.Request(
            f"{DESEC_API}{path}",
            headers={"Authorization": f"Token {token}", "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as res:
                batch = json.loads(res.read().decode())
                link = res.headers.get("Link", "")
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"deSEC API GET {path} failed: HTTP {e.code}")
        rrsets.extend(batch)
        path = None
        match = re.search(r'<([^>]+)>;\s*rel="next"', link or "")
        if match:
            path = match.group(1).replace(DESEC_API, "")
    return rrsets


def diff(existing, desired, zone):
    managed = [
        r for r in existing
        if isinstance(r.get("comment"), str)
        and r["comment"].startswith(MANAGED_TAG)
        and r.get("type") in ALLOWED_TYPES
        and normalize_subname(r.get("subname", ""), zone) != ""
    ]
    existing_by_key = {
        (normalize_subname(r["subname"], zone), r["type"]): r
        for r in managed
    }
    creates, updates, deletes = [], [], []
    for key, rec in desired.items():
        current = existing_by_key.get(key)
        if current is None:
            creates.append(rec)
        elif sorted(current.get("records") or []) != rec["records"] or int(current.get("ttl", 0)) != rec["ttl"]:
            updates.append((current, rec))
    for key, current in existing_by_key.items():
        if key not in desired:
            deletes.append(current)
    return creates, updates, deletes


def sync_zone(zone_cfg, secrets, dry_run):
    zone = zone_cfg["domain"]

    configs = load_configs(zone)
    desired = desired_records(configs)
    total_records = sum(len(e["records"]) for e in desired.values())
    print(f"\n=== {zone}: {len(desired)} rrset(s), {total_records} record(s) from {len(configs)} subdomain(s)")
    for rec in sorted(desired.values(), key=lambda r: (r["subname"], r["type"])):
        for content in rec["records"]:
            print(f"  = {rec['type']} {rec['subname']}.{zone} → {content} (ttl={rec['ttl']})")

    if secrets is None:
        return True

    token = token_for(zone_cfg, secrets)
    status, _ = api("GET", f"/domains/{zone}/", token=token)
    if status == 404:
        raise RuntimeError(
            f"Zone {zone} does not exist in its deSEC account. "
            "Create it on https://desec.io (or POST /domains/), then point the registrar NS to deSEC."
        )
    if status != 200:
        raise RuntimeError(f"could not access zone {zone}: HTTP {status}")

    existing = fetch_all_rrsets(zone, token)
    creates, updates, deletes = diff(existing, desired, zone)

    print(f"\nPlan for {zone}: {len(creates)} to create, {len(updates)} to update, {len(deletes)} to delete.")
    for rec in creates:
        print(f"  + {rec['type']} {rec['subname']}.{zone} → {' '.join(rec['records'])}")
    for cur, rec in updates:
        print(f"  ~ {rec['type']} {rec['subname']}.{zone} (ttl {cur.get('ttl')} → {rec['ttl']})")
    for cur in deletes:
        print(f"  - {cur['type']} {cur['subname']}.{zone}")

    if dry_run:
        return True
    if not creates and not updates and not deletes:
        print(f"Nothing to do for {zone}. DNS is already in sync. ✅")
        return True

    failures = 0
    for rec in creates:
        try:
            api("POST", f"/domains/{zone}/rrsets/", body={
                "subname": rec["subname"],
                "type": rec["type"],
                "ttl": rec["ttl"],
                "records": rec["records"],
                "comment": rec["comment"],
            }, token=token)
            print(f"created {rec['type']} {rec['subname']}.{zone}")
        except RuntimeError as e:
            failures += 1
            print(e, file=sys.stderr)
    for cur, rec in updates:
        try:
            sub = urllib.parse.quote(rec["subname"])
            api("PATCH", f"/domains/{zone}/rrsets/{sub}/{rec['type']}/", body={
                "ttl": rec["ttl"],
                "records": rec["records"],
                "comment": rec["comment"],
            }, token=token)
            print(f"updated {rec['type']} {rec['subname']}.{zone}")
        except RuntimeError as e:
            failures += 1
            print(e, file=sys.stderr)
    for cur in deletes:
        try:
            sub = urllib.parse.quote(normalize_subname(cur["subname"], zone))
            api("DELETE", f"/domains/{zone}/rrsets/{sub}/{cur['type']}/", token=token)
            print(f"deleted {cur['type']} {cur['subname']}.{zone}")
        except RuntimeError as e:
            failures += 1
            print(e, file=sys.stderr)

    if failures:
        raise RuntimeError(f"{failures} operation(s) failed on {zone}, see logs above")
    print(f"{zone} is now in sync. ✅")
    return True


def main(zone_filter=None):
    dry_run = os.environ.get("OXYD_DRY_RUN") == "true"
    if dry_run:
        print("DRY RUN mode: no changes will be applied.")

    zones = load_zone_registry()
    if zone_filter:
        wanted = zone_filter.lower()
        zones = [z for z in zones if z["domain"].lower() == wanted]
        if not zones:
            raise RuntimeError(f"zone '{wanted}' is not listed in {CONFIG_FILE}")

    secrets = None
    if os.path.exists(SECRETS_FILE):
        secrets = decrypt_secrets()
    elif not dry_run:
        raise RuntimeError(
            f"{SECRETS_FILE} not found. Create it from config/secrets.example.json and encrypt it "
            "with sops (see MAINTAINER.md), or run with OXYD_DRY_RUN=true to plan without tokens."
        )
    elif zones:
        print(f"\nNo {SECRETS_FILE}: showing desired state only (dry run).")

    ok = True
    for zone_cfg in zones:
        try:
            sync_zone(zone_cfg, secrets, dry_run)
        except RuntimeError as e:
            ok = False
            print(f"ERROR syncing {zone_cfg['domain']}: {e}", file=sys.stderr)
    if not ok:
        raise RuntimeError("one or more zone(s) failed to sync")
    print("\nAll zones processed.")


if __name__ == "__main__":
    main(zone_filter=os.environ.get("OXYD_ZONE"))
