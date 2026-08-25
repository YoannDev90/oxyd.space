#!/usr/bin/env python3
"""SSL Checker - Verify HTTPS certificates for subdomains."""

import json
import socket
import ssl
import subprocess
import sys
from datetime import datetime
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


def check_ssl_certificate(hostname, port=443, timeout=5):
    """Check SSL certificate for a hostname. Returns (ok, info, error)."""
    try:
        context = ssl.create_default_context()
        with socket.create_connection((hostname, port), timeout=timeout) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                cert = ssock.getpeercert()

                # Extract certificate info
                subject = dict(x[0] for x in cert.get("subject", []))
                issuer = dict(x[0] for x in cert.get("issuer", []))

                # Parse expiration date
                not_after = cert.get("notAfter", "")
                if not_after:
                    # Format: "Mar 15 23:59:59 2025 GMT"
                    expiry = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z")
                    days_left = (expiry - datetime.utcnow()).days
                else:
                    days_left = -1

                info = {
                    "subject": subject.get("commonName", "unknown"),
                    "issuer": issuer.get(
                        "organizationName", issuer.get("commonName", "unknown")
                    ),
                    "expiry": not_after,
                    "days_left": days_left,
                    "version": ssock.version(),
                    "cipher": ssock.cipher()[0] if ssock.cipher() else "unknown",
                }

                # Check for issues
                issues = []
                if days_left < 0:
                    issues.append(f"Certificate expired {abs(days_left)} days ago")
                elif days_left < 30:
                    issues.append(f"Certificate expires in {days_left} days")

                # Check subject matches
                cert_cn = subject.get("commonName", "")
                cert_san = [e[1] for e in cert.get("subjectAltName", [])]
                if hostname not in cert_san and cert_cn != hostname:
                    # Allow wildcard matches
                    if not (
                        cert_cn.startswith("*.") and hostname.endswith(cert_cn[1:])
                    ):
                        issues.append(f"Hostname mismatch: cert is for {cert_cn}")

                return len(issues) == 0, info, issues

    except ssl.SSLCertVerificationError as e:
        return False, {}, [f"SSL verification failed: {e}"]
    except socket.timeout:
        return False, {}, ["Connection timeout"]
    except socket.gaierror:
        return False, {}, ["DNS resolution failed"]
    except ConnectionRefusedError:
        return False, {}, ["Connection refused"]
    except Exception as e:
        return False, {}, [f"Error: {e}"]


def check_http_redirect(hostname, timeout=5):
    """Check if HTTP redirects to HTTPS. Returns (ok, info)."""
    try:
        result = subprocess.run(
            ["curl", "-sI", "-m", str(timeout), f"http://{hostname}/"],
            capture_output=True,
            text=True,
            timeout=timeout + 2,
        )

        lines = result.stdout.split("\n")
        status_line = next((line for line in lines if line.startswith("HTTP/")), None)
        location_line = next(
            (line for line in lines if line.lower().startswith("location:")), None
        )

        if not status_line:
            return False, {"error": "No HTTP response"}

        status_code = int(status_line.split()[1]) if len(status_line.split()) > 1 else 0

        info = {
            "status": status_code,
            "redirects_to_https": False,
            "redirect_url": "",
        }

        if location_line:
            redirect_url = location_line.split(":", 1)[1].strip()
            info["redirect_url"] = redirect_url
            info["redirects_to_https"] = redirect_url.startswith("https://")

        return info["redirects_to_https"], info

    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False, {"error": "HTTP check failed"}


def main():
    """Main entry point."""
    subdomains = list(iter_subdomains())

    if not subdomains:
        print("No subdomains found in domains/ directory.")
        return 0

    print(f"Checking SSL certificates for {len(subdomains)} subdomains...\n")

    total = 0
    healthy = 0
    issues_found = 0

    for zone, stem, config_path in subdomains:
        fqdn = f"{stem}.{zone}"
        total += 1

        # Check SSL certificate
        cert_ok, cert_info, cert_issues = check_ssl_certificate(fqdn)

        # Check HTTP redirect (only for CNAME records pointing to web hosts)
        config = json.loads(config_path.read_text())
        records = config.get("records", [])
        has_cname = any(r.get("type") == "CNAME" for r in records)

        http_ok = True
        http_info = {}
        if has_cname:
            http_ok, http_info = check_http_redirect(fqdn)

        # Report
        if cert_ok and http_ok:
            healthy += 1
            expiry_info = ""
            if cert_info.get("days_left") is not None:
                expiry_info = f" (expires in {cert_info['days_left']} days)"
            print(f"✅ {fqdn}{expiry_info}")
        else:
            issues_found += 1
            print(f"❌ {fqdn}")
            for issue in cert_issues:
                print(f"   - {issue}")
            if not http_ok and http_info.get("error"):
                print(f"   - HTTP: {http_info['error']}")

    print(f"\nSummary: {healthy}/{total} healthy, {issues_found} with issues")
    return 1 if issues_found > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
