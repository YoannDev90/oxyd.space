#!/usr/bin/env python3
"""Orphan Detector - Find subdomains pointing to dead targets."""
import json
import os
import socket
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


def check_target_alive(target, rtype, timeout=5):
    """Check if a DNS target is reachable. Returns (alive, reason)."""
    try:
        if rtype == "CNAME":
            # Check if hostname resolves
            result = subprocess.run(
                ["dig", "+short", target, "A"],
                capture_output=True, text=True, timeout=timeout
            )
            if not result.stdout.strip():
                return False, "CNAME target does not resolve"
            return True, "OK"
        
        elif rtype == "A":
            # Check if IP is reachable (TCP port 80)
            ip = target.strip()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            try:
                result = sock.connect_ex((ip, 80))
                sock.close()
                if result == 0:
                    return True, "Port 80 reachable"
                else:
                    return False, f"Port 80 unreachable (error {result})"
            except Exception as e:
                return False, f"Connection failed: {e}"
        
        elif rtype == "AAAA":
            # Check if IP is reachable (TCP port 80)
            ip = target.strip()
            sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            try:
                result = sock.connect_ex((ip, 80))
                sock.close()
                if result == 0:
                    return True, "Port 80 reachable"
                else:
                    return False, f"Port 80 unreachable (error {result})"
            except Exception as e:
                return False, f"Connection failed: {e}"
        
        elif rtype == "TXT":
            # TXT records are just text, no reachability check needed
            return True, "TXT record (no check needed)"
        
        else:
            return False, f"Unknown record type: {rtype}"
    
    except subprocess.TimeoutExpired:
        return False, "DNS query timeout"
    except socket.timeout:
        return False, "Connection timeout"
    except Exception as e:
        return False, f"Error: {e}"


def check_www_targets(zone, stem, config):
    """Check www prefix targets if enabled."""
    issues = []
    if not config.get("www", False):
        return issues
    
    www_fqdn = f"www.{stem}.{zone}"
    records = config.get("records", [])
    
    for record in records:
        rtype = record.get("type", "")
        value = record.get("value", "")
        
        if not value:
            continue
        
        alive, reason = check_target_alive(value, rtype)
        if not alive:
            issues.append({
                "fqdn": www_fqdn,
                "type": rtype,
                "value": value,
                "reason": reason,
            })
    
    return issues


def main():
    """Main entry point."""
    zones = load_zones()
    subdomains = list(iter_subdomains())
    
    if not subdomains:
        print("No subdomains found in domains/ directory.")
        return 0
    
    print(f"Checking {len(subdomains)} subdomains for dead targets...\n")
    
    total = 0
    healthy = 0
    orphans = 0
    
    for zone, stem, config_path in subdomains:
        if zone not in zones:
            continue
        
        total += 1
        config = load_config(config_path)
        fqdn = f"{stem}.{zone}"
        records = config.get("records", [])
        
        issues = []
        
        for record in records:
            rtype = record.get("type", "")
            value = record.get("value", "")
            
            if not value:
                issues.append(f"{rtype}: empty value")
                continue
            
            alive, reason = check_target_alive(value, rtype)
            if not alive:
                issues.append(f"{rtype} {value}: {reason}")
        
        # Check www targets
        www_issues = check_www_targets(zone, stem, config)
        for issue in www_issues:
            issues.append(f"www.{issue['type']} {issue['value']}: {issue['reason']}")
        
        if issues:
            orphans += 1
            print(f"⚠️  {fqdn}")
            for issue in issues:
                print(f"   - {issue}")
        else:
            healthy += 1
            print(f"✅ {fqdn}")
    
    print(f"\nSummary: {healthy}/{total} healthy, {orphans} with dead targets")
    return 1 if orphans > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
