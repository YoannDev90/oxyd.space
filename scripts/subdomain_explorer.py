#!/usr/bin/env python3
"""Subdomain Explorer - List all registered subdomains with their targets."""
import json
import os
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


def format_records(records):
    """Format DNS records for display."""
    if not records:
        return "no records"
    
    parts = []
    for rec in records:
        rtype = rec.get("type", "?")
        value = rec.get("value", "?")
        parts.append(f"{rtype}={value}")
    
    return ", ".join(parts)


def main():
    """Main entry point."""
    zones = load_zones()
    subdomains = list(iter_subdomains())
    
    if not subdomains:
        print("No subdomains found in domains/ directory.")
        return 0
    
    print(f" oxyd.space Subdomain Explorer")
    print(f"{'=' * 50}\n")
    
    # Group by zone
    by_zone = {}
    for zone, stem, config_path in subdomains:
        if zone not in by_zone:
            by_zone[zone] = []
        
        config = load_config(config_path)
        owner = config.get("owner", {})
        records = config.get("records", [])
        www = config.get("www", False)
        
        by_zone[zone].append({
            "stem": stem,
            "fqdn": f"{stem}.{zone}",
            "owner": owner.get("github", "unknown"),
            "records": records,
            "www": www,
        })
    
    # Display by zone
    for zone in sorted(by_zone.keys()):
        subs = by_zone[zone]
        print(f"📁 {zone} ({len(subs)} subdomains)")
        print(f"{'-' * 50}")
        
        for sub in sorted(subs, key=lambda x: x["stem"]):
            owner = sub["owner"]
            records_str = format_records(sub["records"])
            www_str = " +www" if sub["www"] else ""
            
            print(f"  {sub['fqdn']}")
            print(f"    Owner: @{owner}")
            print(f"    Records: {records_str}{www_str}")
            print()
    
    # Summary
    total = len(subdomains)
    zones_count = len(by_zone)
    owners = set()
    for subs in by_zone.values():
        for sub in subs:
            owners.add(sub["owner"])
    
    print(f"{'=' * 50}")
    print(f"Summary: {total} subdomains across {zones_count} zones")
    print(f"Unique owners: {len(owners)}")
    
    return 0


def export_json():
    """Export subdomain data as JSON."""
    zones = load_zones()
    subdomains = list(iter_subdomains())
    
    data = []
    for zone, stem, config_path in subdomains:
        config = load_config(config_path)
        owner = config.get("owner", {})
        records = config.get("records", [])
        www = config.get("www", False)
        
        data.append({
            "fqdn": f"{stem}.{zone}",
            "zone": zone,
            "stem": stem,
            "owner": owner.get("github", "unknown"),
            "records": records,
            "www": www,
        })
    
    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    if "--json" in sys.argv:
        export_json()
    else:
        sys.exit(main())
