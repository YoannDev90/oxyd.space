#!/usr/bin/env python3
"""Local Dev Server - Simulate the bot locally with mock DNS."""

import http.server
import json
import socketserver
from pathlib import Path

DOMAINS_DIR = Path("domains")
MOCK_PORT = 8053
HTTP_PORT = 8080


class MockDNSHandler(http.server.BaseHTTPRequestHandler):
    """Mock DNS server that serves records from domains/ directory."""

    def do_GET(self):
        """Handle GET requests."""
        if self.path.startswith("/dns/"):
            self.handle_dns_query()
        elif self.path == "/health":
            self.handle_health()
        elif self.path == "/domains":
            self.handle_list_domains()
        else:
            self.send_error(404)

    def handle_dns_query(self):
        """Handle DNS query requests."""
        # Parse query: /dns/{fqdn}/{type}
        parts = self.path.strip("/").split("/")
        if len(parts) < 3:
            self.send_error(400, "Usage: /dns/{fqdn}/{type}")
            return

        fqdn = parts[1]
        rtype = parts[2].upper()

        # Load config
        config = self.load_config(fqdn)
        if config is None:
            self.send_json(404, {"error": f"Domain {fqdn} not found"})
            return

        # Find matching records
        records = config.get("records", [])
        matching = [r for r in records if r.get("type") == rtype]

        if not matching:
            self.send_json(200, {"records": [], "fqdn": fqdn, "type": rtype})
            return

        result = {
            "fqdn": fqdn,
            "type": rtype,
            "records": [
                {"value": r.get("value", ""), "ttl": r.get("ttl", 3600)}
                for r in matching
            ],
        }
        self.send_json(200, result)

    def handle_health(self):
        """Health check endpoint."""
        self.send_json(200, {"status": "ok", "service": "oxyd.local-dev-server"})

    def handle_list_domains(self):
        """List all registered domains."""
        domains = []
        if DOMAINS_DIR.exists():
            for zone_dir in sorted(DOMAINS_DIR.iterdir()):
                if not zone_dir.is_dir() or zone_dir.name.startswith(("_", ".")):
                    continue
                for json_file in sorted(zone_dir.glob("*.json")):
                    if not json_file.name.startswith(("_", ".")):
                        fqdn = f"{json_file.stem}.{zone_dir.name}"
                        domains.append(fqdn)

        self.send_json(200, {"domains": domains, "count": len(domains)})

    def load_config(self, fqdn):
        """Load configuration for a fully qualified domain name."""
        parts = fqdn.split(".")
        if len(parts) < 2:
            return None

        stem = parts[0]
        zone = ".".join(parts[1:])

        config_path = DOMAINS_DIR / zone / f"{stem}.json"
        if not config_path.exists():
            return None

        with open(config_path) as f:
            return json.load(f)

    def send_json(self, code, data):
        """Send JSON response."""
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode())

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass


class MockDNSDaemon:
    """Simple DNS daemon that responds to queries."""

    def __init__(self, port=MOCK_PORT):
        self.port = port
        self.running = False

    def start(self):
        """Start the DNS daemon."""
        import threading

        self.running = True
        thread = threading.Thread(target=self._run, daemon=True)
        thread.start()
        print(f"Mock DNS daemon listening on port {self.port}")
        return thread

    def _run(self):
        """Run the DNS daemon."""
        import socket

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("127.0.0.1", self.port))

        while self.running:
            try:
                data, addr = sock.recvfrom(512)
                # Simple DNS response - just acknowledge
                response = self._build_dns_response(data)
                sock.sendto(response, addr)
            except Exception:
                pass

    def _build_dns_response(self, request):
        """Build a mock DNS response."""
        # This is a simplified mock - just return the request with response flags
        response = bytearray(request)
        # Set response flag (bit 15 of flags)
        if len(response) > 3:
            response[2] |= 0x80
        return bytes(response)


def main():
    """Main entry point."""
    print(" oxyd.space Local Development Server")
    print(f"{'=' * 50}\n")

    # Start mock DNS daemon
    dns_daemon = MockDNSDaemon()
    dns_daemon.start()

    # Start HTTP server
    print(f"HTTP server listening on http://localhost:{HTTP_PORT}")
    print(f"Mock DNS server on UDP port {MOCK_PORT}")
    print("\nEndpoints:")
    print("  GET /health        - Health check")
    print("  GET /domains       - List all domains")
    print("  GET /dns/{fqdn}/{type} - Query DNS records")
    print("\nPress Ctrl+C to stop.\n")

    with socketserver.TCPServer(("", HTTP_PORT), MockDNSHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down...")
            dns_daemon.running = False


if __name__ == "__main__":
    main()
