#!/usr/bin/env python3
"""DNS Health Check - Verify subdomain DNS records match configuration."""

import json
import subprocess
import sys
from pathlib import Path

DOMAINS_DIR = Path("domains")
CONFIG_FILE = Path("config/domains.json")


def load_zones():
    """Load configured zones from config/domains.json."""
    try:
        with open(CONFIG_FILE) as f:
            data = json.load(f)
        return [z["domain"] for z in data.get("zones", []) if "domain" in z]
    except (FileNotFoundError, json.JSONDecodeError):
        return ["oxyd.space"]


def iter_subdomains():
    """Yield (zone, stem, config_path) for all registered subdomains."""
    for zone_dir in sorted(DOMAINS_DIR.iterdir()):
        if not zone_dir.is_dir() or zone_dir.name.startswith(("_", ".")):
            continue
        zone = zone_dir.name.lower()
        for json_file in sorted(zone_dir.glob("*.json")):
            if not json_file.name.startswith(("_", ".")):
                yield zone, json_file.stem, json_file


def load_config(path):
    """Load and return subdomain configuration."""
    with open(path) as f:
        return json.load(f)


def dig_query(fqdn, rtype):
    """Query DNS for a specific record type. Returns list of values."""
    try:
        result = subprocess.run(
            ["dig", "+short", fqdn, rtype], capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            return []
        lines = [
            line.strip().rstrip(".")
            for line in result.stdout.strip().split("\n")
            if line.strip()
        ]
        return lines
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def normalize_value(value, rtype):
    """Normalize DNS record value for comparison."""
    if not value:
        return ""
    value = value.strip().rstrip(".")
    if rtype in ("A", "AAAA"):
        return value.lower()
    return value.lower()


def check_subdomain(zone, stem, config):
    """Check DNS records for a single subdomain. Returns (ok, issues)."""
    fqdn = f"{stem}.{zone}"
    issues = []
    records = config.get("records", [])
    www = config.get("www", False)

    for record in records:
        rtype = record.get("type", "")
        expected = record.get("value", "")

        if not rtype or not expected:
            issues.append(f"Invalid record: {record}")
            continue

        # Query DNS
        actual_values = dig_query(fqdn, rtype)
        normalized_expected = normalize_value(expected, rtype)

        if not actual_values:
            issues.append(f"{rtype}: no records found (expected {expected})")
        elif normalized_expected not in [
            normalize_value(v, rtype) for v in actual_values
        ]:
            issues.append(f"{rtype}: expected {expected}, got {actual_values}")

    # Check www prefix if enabled
    if www:
        www_fqdn = f"www.{stem}.{zone}"
        for record in records:
            rtype = record.get("type", "")
            expected = record.get("value", "")

            actual_values = dig_query(www_fqdn, rtype)
            normalized_expected = normalize_value(expected, rtype)

            if not actual_values:
                issues.append(f"www.{rtype}: no records found for www prefix")
            elif normalized_expected not in [
                normalize_value(v, rtype) for v in actual_values
            ]:
                issues.append(f"www.{rtype}: expected {expected}, got {actual_values}")

    return len(issues) == 0, issues


def main():
    """Main entry point."""
    zones = load_zones()
    subdomains = list(iter_subdomains())

    if not subdomains:
        print("No subdomains found in domains/ directory.")
        return 0

    print(f"Checking {len(subdomains)} subdomains across {len(zones)} zones...\n")

    total = 0
    healthy = 0
    issues_found = 0

    for zone, stem, config_path in subdomains:
        if zone not in zones:
            print(f"⚠️  {stem}.{zone}: unknown zone (not in config)")
            continue

        total += 1
        config = load_config(config_path)
        ok, issues = check_subdomain(zone, stem, config)

        if ok:
            healthy += 1
            print(f"✅ {stem}.{zone}")
        else:
            issues_found += 1
            print(f"❌ {stem}.{zone}")
            for issue in issues:
                print(f"   - {issue}")

    print(f"\nSummary: {healthy}/{total} healthy, {issues_found} with issues")
    return 1 if issues_found > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
