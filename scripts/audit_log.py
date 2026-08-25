#!/usr/bin/env python3
"""Audit Log - Track changes to subdomains via git history."""

import subprocess
import sys
from pathlib import Path

DOMAINS_DIR = "domains"


def git_log(path=None, limit=50, author=None):
    """Get git log entries. Returns list of dicts."""
    cmd = ["git", "log", f"--max-count={limit}", "--format=%H|%ai|%an|%s"]
    if path:
        cmd.extend(["--", path])
    if author:
        cmd.extend(["--author", author])

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Git error: {result.stderr}", file=sys.stderr)
        return []

    entries = []
    for line in result.stdout.strip().split("\n"):
        if not line or "|" not in line:
            continue
        parts = line.split("|", 3)
        if len(parts) == 4:
            entries.append(
                {
                    "hash": parts[0],
                    "date": parts[1],
                    "author": parts[2],
                    "message": parts[3],
                }
            )
    return entries


def get_file_changes(commit_hash):
    """Get files changed in a commit. Returns list of (status, path)."""
    result = subprocess.run(
        ["git", "diff-tree", "--no-commit-id", "-r", "--name-status", commit_hash],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []

    changes = []
    for line in result.stdout.strip().split("\n"):
        if not line or "\t" not in line:
            continue
        parts = line.split("\t", 1)
        if len(parts) == 2:
            changes.append((parts[0], parts[1]))
    return changes


def filter_domain_changes(entries):
    """Filter entries to only those affecting domains/ directory."""
    filtered = []
    for entry in entries:
        changes = get_file_changes(entry["hash"])
        domain_changes = [c for c in changes if c[1].startswith(DOMAINS_DIR + "/")]
        if domain_changes:
            entry["changes"] = domain_changes
            filtered.append(entry)
    return filtered


def format_entry(entry, verbose=False):
    """Format a log entry for display."""
    date = entry["date"][:10] if entry["date"] else "unknown"
    author = entry["author"] or "unknown"
    message = entry["message"] or "no message"
    short_hash = entry["hash"][:8] if entry["hash"] else "?"

    line = f"[{date}] {short_hash} {author}: {message}"

    if verbose and "changes" in entry:
        for status, path in entry["changes"]:
            icon = (
                "+"
                if status == "A"
                else "-"
                if status == "D"
                else "~"
                if status == "M"
                else "?"
            )
            # Extract just the filename from path
            filename = Path(path).name
            line += f"\n    {icon} {filename}"

    return line


def main():
    """Main entry point."""
    verbose = "-v" in sys.argv or "--verbose" in sys.argv
    limit = 50
    author = None

    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == "--limit" and i < len(sys.argv) - 1:
            limit = int(sys.argv[i + 1])
        elif arg == "--author" and i < len(sys.argv) - 1:
            author = sys.argv[i + 1]

    print(" oxyd.space Audit Log")
    print(f"{'=' * 60}\n")

    # Get all commits
    entries = git_log(limit=limit, author=author)
    if not entries:
        print("No commits found.")
        return 0

    # Filter to domain changes
    domain_entries = filter_domain_changes(entries)

    if not domain_entries:
        print("No domain changes found in recent commits.")
        return 0

    print(f"Showing {len(domain_entries)} domain-related changes:\n")

    for entry in domain_entries:
        print(format_entry(entry, verbose))
        print()

    # Summary
    authors = set(e["author"] for e in domain_entries if e["author"])
    print(f"{'=' * 60}")
    print(f"Total: {len(domain_entries)} changes by {len(authors)} authors")

    return 0


if __name__ == "__main__":
    sys.exit(main())
