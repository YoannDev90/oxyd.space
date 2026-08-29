#!/usr/bin/env python3
"""Weekly DNS server health check.

Probes every resolver listed in website/public/assets/dns.json against a set
of stable seed domains and flips its ``active`` flag. A server that fails to
answer within the per-server budget is deactivated, and it is brought back as
soon as it answers again. Called from .github/workflows/dns-health.yml.

Stdlib only: each probe is a raw UDP query on port 53 (no dnspython). Any
payload that comes back with a matching transaction id — including NXDOMAIN
or empty answers — proves the resolver is alive.
"""

import concurrent.futures
import json
import random
import socket
import struct
import sys
import time
from datetime import UTC, datetime

DNS_JSON = "website/public/assets/dns.json"

SEED_DOMAINS = [
    "example.com",
    "google.com",
    "cloudflare.com",
    "wikipedia.org",
    "github.com",
    "mozilla.org",
    "python.org",
    "debian.org",
    "iana.org",
    "duckduckgo.com",
]

QUERY_TIMEOUT = 3  # hard cap per query; 10 domains == 30s budget per server
WORKERS = 64
IPV6_PROBE = "2606:4700:4700::1111"  # Cloudflare public DNS (IPv6 route probe)
MAX_INACTIVE_RATIO = 0.5  # abort the write if more than half the fleet looks dead


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def save(path, data):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def now_utc():
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_query(domain):
    tid = random.getrandbits(16)
    qname = b"".join(
        bytes([len(label)]) + label.encode("ascii") for label in domain.split(".")
    )
    qname += b"\x00"
    header = struct.pack(">HHHHHH", tid, 0x0100, 1, 0, 0, 0)  # RD=1
    question = qname + struct.pack(">HH", 1, 1)  # A record, class IN
    return tid, header + question


def send_query(server, packet, timeout):
    family = socket.AF_INET6 if ":" in server else socket.AF_INET
    try:
        sock = socket.socket(family, socket.SOCK_DGRAM)
    except OSError:
        return None
    sock.settimeout(timeout)
    try:
        sock.sendto(packet, (server, 53))
        data, _ = sock.recvfrom(4096)
        return data
    except (OSError, socket.timeout):
        return None
    finally:
        sock.close()


def has_ipv6_route():
    tid, packet = build_query(SEED_DOMAINS[0])
    data = send_query(IPV6_PROBE, packet, QUERY_TIMEOUT)
    return data is not None and len(data) >= 12


def responds(server, domains):
    """True when the resolver answers at least one domain within the budget."""
    for domain in domains:
        tid, packet = build_query(domain)
        data = send_query(server, packet, QUERY_TIMEOUT)
        if (
            data is not None
            and len(data) >= 12
            and struct.unpack(">H", data[0:2])[0] == tid
        ):
            return True
    return False


def check_server(entry, domains, ipv6_ok):
    ip = entry["ip"]
    if ":" in ip and not ipv6_ok:
        return entry, "skipped-ipv6"
    alive = responds(ip, domains)
    entry["active"] = alive
    entry["lastChecked"] = now_utc()
    return entry, "ok" if alive else "inactive"


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else DNS_JSON
    data = load(path)
    ipv6_ok = has_ipv6_route()
    print(f"ipv6 route on runner: {ipv6_ok}")

    start = time.time()
    statuses = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = [
            pool.submit(check_server, entry, SEED_DOMAINS, ipv6_ok) for entry in data
        ]
        for future in concurrent.futures.as_completed(futures):
            statuses.append(future.result()[1])

    elapsed = time.time() - start
    active = sum(1 for s in statuses if s == "ok")
    inactive = sum(1 for s in statuses if s == "inactive")
    skipped = sum(1 for s in statuses if s == "skipped-ipv6")
    print(
        f"checked {len(data)} servers in {elapsed:.1f}s: "
        f"{active} active, {inactive} inactive, {skipped} ipv6 skipped"
    )

    if inactive / len(data) > MAX_INACTIVE_RATIO:
        print(
            "too many inactive — aborting write to avoid wiping the fleet on a network blip"
        )
        sys.exit(1)

    save(path, data)
    print("dns.json updated")


if __name__ == "__main__":
    main()
