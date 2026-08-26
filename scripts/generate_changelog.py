#!/usr/bin/env python3
"""
Generate a changelog entry from git commit history.

Usage:
    python scripts/generate_changelog.py v1.3.0
    python scripts/generate_changelog.py v1.3.0 --repo YoannDev90/oxyd.space
    python scripts/generate_changelog.py v1.3.0 --since abc1234
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

try:
    import requests
except ImportError:
    requests = None  # type: ignore[assignment]

# Conventional commit type → changelog section heading
TYPE_MAP = {
    "feat": "Added",
    "fix": "Fixed",
    "perf": "Improved",
    "refactor": "Changed",
    "docs": "Documentation",
    "chore": "Maintenance",
    "ci": "CI/CD",
    "test": "Tests",
    "style": "Style",
    "build": "Build",
}

# Sections in display order
SECTION_ORDER = [
    "Added",
    "Changed",
    "Fixed",
    "Improved",
    "Documentation",
    "CI/CD",
    "Maintenance",
    "Tests",
    "Build",
    "Style",
]

CONVENTIONAL_RE = re.compile(
    r"^(?P<type>\w+)"
    r"(?:\((?P<scope>[^)]+)\))?"
    r"(?P<breaking>!)?"
    r":\s*(?P<description>.+)$"
)

CHANGELOG_DIR = Path(__file__).resolve().parent.parent / "docs" / "changelogs"


def run(cmd: list[str], check: bool = False, **kwargs) -> str:
    """Run a shell command and return stripped stdout."""
    result = subprocess.run(cmd, capture_output=True, text=True, check=check, **kwargs)
    return result.stdout.strip()


def get_last_version_tag() -> str | None:
    """Return the most recent version tag, or None."""
    tag = run(["git", "describe", "--tags", "--abbrev=0"], check=True)
    return tag if tag else None


def get_commits_since(since: str | None) -> list[tuple[str, str]]:
    """Return list of (sha, commit_message) tuples since a ref (or all if None)."""
    if since:
        cmd = ["git", "log", f"{since}..HEAD", "--pretty=format:%H %s"]
    else:
        cmd = ["git", "log", "--pretty=format:%H %s"]
    output = run(cmd, check=True)
    if not output:
        return []
    commits = []
    for line in output.splitlines():
        sha = line[:40]
        message = line[41:] if len(line) > 41 else ""
        commits.append((sha, message))
    return commits


def parse_commit(message: str) -> tuple[str | None, str | None, str, str]:
    """Parse a conventional commit message.

    Returns (type, scope, description, original_message).
    """
    m = CONVENTIONAL_RE.match(message)
    if not m:
        return (None, None, message, message)
    return (
        m.group("type"),
        m.group("scope"),
        m.group("description").strip(),
        message,
    )


def try_fetch_pr_number(commit_sha: str, repo: str) -> int | None:
    """Try to find a PR number for a commit via GitHub API."""
    if not requests or not repo:
        return None
    token = os.environ.get("GITHUB_TOKEN", "")
    headers = {"Authorization": f"token {token}"} if token else {}
    url = f"https://api.github.com/repos/{repo}/pulls?state=all&sha={commit_sha}"
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.ok:
            pulls = resp.json()
            if pulls:
                return pulls[0]["number"]
    except Exception:
        pass
    return None


def build_changelog(version: str, repo: str, since: str | None) -> str:
    """Build the markdown changelog content for a version."""
    # Find the last changelog entry to use as --since reference
    if since is None:
        existing = sorted(CHANGELOG_DIR.glob("v*.md"), reverse=True)
        if existing:
            since = existing[0].stem  # e.g., "v1.2.0"

    commits = get_commits_since(since)
    if not commits:
        print("No commits found since the specified reference.", file=sys.stderr)
        sys.exit(1)

    sections: dict[str, list[str]] = {}
    for sha, msg in commits:
        ctype, scope, desc, original = parse_commit(msg)
        if ctype is None or ctype not in TYPE_MAP:
            # Non-conventional commits go under "Changed"
            heading = "Changed"
        else:
            heading = TYPE_MAP[ctype]

        # Try to find PR number from the commit
        # (only when running in CI with GITHUB_TOKEN)
        pr_number = None
        if sha:
            pr_number = try_fetch_pr_number(sha, repo)

        # Format the entry
        entry = f"- {desc}"
        if scope:
            entry += f" ({scope})"
        if pr_number:
            entry += f" (#{pr_number})"

        sections.setdefault(heading, []).append(entry)

    # Build markdown
    today = date.today().isoformat()
    lines = [
        "---",
        f"version: {version}",
        f"date: {today}",
        "---",
        "",
    ]

    for heading in SECTION_ORDER:
        if heading in sections:
            lines.append(f"## {heading}")
            lines.extend(sections[heading])
            lines.append("")

    # Append any sections not in SECTION_ORDER
    for heading, items in sections.items():
        if heading not in SECTION_ORDER:
            lines.append(f"## {heading}")
            lines.extend(items)
            lines.append("")

    return "\n".join(lines)


def update_index(version: str, filename: str, today: str) -> None:
    """Add or update the entry in index.json."""
    index_path = CHANGELOG_DIR / "index.json"
    if index_path.exists():
        with open(index_path) as f:
            index = json.load(f)
    else:
        index = []

    # Remove existing entry for this version (if re-generating)
    index = [e for e in index if e["version"] != version]

    # Insert at the beginning (newest first)
    index.insert(0, {"version": version, "file": filename, "date": today})

    with open(index_path, "w") as f:
        json.dump(index, f, indent=2)
        f.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a changelog entry.")
    parser.add_argument("version", help="Version tag (e.g. v1.3.0)")
    parser.add_argument(
        "--repo",
        default="YoannDev90/oxyd.space",
        help="GitHub repo slug for PR lookup (default: YoannDev90/oxyd.space)",
    )
    parser.add_argument(
        "--since",
        default=None,
        help="Git ref to start from (default: auto-detect from last changelog)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the markdown to stdout instead of writing a file",
    )
    args = parser.parse_args()

    version = args.version
    if not version.startswith("v"):
        version = f"v{version}"

    content = build_changelog(version, args.repo, args.since)
    today = date.today().isoformat()
    filename = f"{version}.md"

    if args.dry_run:
        print(content)
        return

    # Write changelog file
    CHANGELOG_DIR.mkdir(parents=True, exist_ok=True)
    filepath = CHANGELOG_DIR / filename
    with open(filepath, "w") as f:
        f.write(content)
    print(f"Created {filepath}")

    # Update index.json
    update_index(version, filename, today)
    print(f"Updated {CHANGELOG_DIR / 'index.json'}")


if __name__ == "__main__":
    main()
