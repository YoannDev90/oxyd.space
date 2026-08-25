#!/usr/bin/env python3
"""Health Monitor - Periodic health checks for all subdomains."""
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

DOMAINS_DIR = Path("domains")
CONFIG_FILE = Path("config/domains.json")
REPORTS_DIR = Path("reports")


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


def dig_query(fqdn, rtype, timeout=5):
    """Query DNS for a specific record type. Returns list of values."""
    try:
        result = subprocess.run(
            ["dig", "+short", fqdn, rtype],
            capture_output=True, text=True, timeout=timeout
        )
        if result.returncode != 0:
            return []
        lines = [l.strip().rstrip(".") for l in result.stdout.strip().split("\n") if l.strip()]
        return lines
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def check_dns(zone, stem, config):
    """Check DNS records for a subdomain. Returns (ok, issues)."""
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
        
        actual_values = dig_query(fqdn, rtype)
        
        if not actual_values:
            issues.append(f"{rtype}: no records found (expected {expected})")
        elif expected.lower() not in [v.lower() for v in actual_values]:
            issues.append(f"{rtype}: expected {expected}, got {actual_values}")
    
    if www:
        www_fqdn = f"www.{stem}.{zone}"
        for record in records:
            rtype = record.get("type", "")
            expected = record.get("value", "")
            
            actual_values = dig_query(www_fqdn, rtype)
            
            if not actual_values:
                issues.append(f"www.{rtype}: no records found for www prefix")
            elif expected.lower() not in [v.lower() for v in actual_values]:
                issues.append(f"www.{rtype}: expected {expected}, got {actual_values}")
    
    return len(issues) == 0, issues


def check_ssl(hostname, timeout=5):
    """Check SSL certificate. Returns (ok, info)."""
    import socket
    import ssl
    
    try:
        context = ssl.create_default_context()
        with socket.create_connection((hostname, 443), timeout=timeout) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                cert = ssock.getpeercert()
                not_after = cert.get("notAfter", "")
                if not_after:
                    expiry = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z")
                    days_left = (expiry - datetime.utcnow()).days
                    return days_left > 0, {"days_left": days_left}
                return True, {}
    except Exception:
        return False, {}


def generate_report(results, timestamp):
    """Generate a health report."""
    REPORTS_DIR.mkdir(exist_ok=True)
    
    report_file = REPORTS_DIR / f"health_{timestamp}.json"
    report = {
        "timestamp": timestamp,
        "total": len(results),
        "healthy": sum(1 for r in results if r["status"] == "healthy"),
        "warning": sum(1 for r in results if r["status"] == "warning"),
        "critical": sum(1 for r in results if r["status"] == "critical"),
        "results": results,
    }
    
    with open(report_file, "w") as f:
        json.dump(report, f, indent=2)
    
    return report_file


def main():
    """Main entry point."""
    zones = load_zones()
    subdomains = list(iter_subdomains())
    
    if not subdomains:
        print("No subdomains found in domains/ directory.")
        return 0
    
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    print(f"Health Monitor - {datetime.utcnow().isoformat()}")
    print(f"Checking {len(subdomains)} subdomains...\n")
    
    results = []
    
    for zone, stem, config_path in subdomains:
        if zone not in zones:
            continue
        
        config = load_config(config_path)
        fqdn = f"{stem}.{zone}"
        
        # Check DNS
        dns_ok, dns_issues = check_dns(zone, stem, config)
        
        # Check SSL
        ssl_ok, ssl_info = check_ssl(fqdn)
        
        # Determine status
        if dns_ok and ssl_ok:
            status = "healthy"
        elif dns_ok and not ssl_ok:
            status = "warning"
        else:
            status = "critical"
        
        result = {
            "fqdn": fqdn,
            "zone": zone,
            "stem": stem,
            "status": status,
            "dns_ok": dns_ok,
            "dns_issues": dns_issues,
            "ssl_ok": ssl_ok,
            "ssl_info": ssl_info,
        }
        results.append(result)
        
        # Print status
        icon = "✅" if status == "healthy" else "⚠️ " if status == "warning" else "❌"
        print(f"{icon} {fqdn}")
        if dns_issues:
            for issue in dns_issues:
                print(f"   DNS: {issue}")
        if not ssl_ok:
            print(f"   SSL: certificate issue")
    
    # Generate report
    report_file = generate_report(results, timestamp)
    
    # Summary
    healthy = sum(1 for r in results if r["status"] == "healthy")
    warning = sum(1 for r in results if r["status"] == "warning")
    critical = sum(1 for r in results if r["status"] == "critical")
    
    print(f"\n{'=' * 50}")
    print(f"Summary: {healthy} healthy, {warning} warnings, {critical} critical")
    print(f"Report saved to: {report_file}")
    
    return 1 if critical > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
