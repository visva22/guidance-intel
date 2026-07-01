"""Exclusion pattern detection and frontmatter parsing."""
from __future__ import annotations

import re
from pathlib import Path


def parse_frontmatter_exclusion(file_path: str | Path) -> tuple[bool, str]:
    """
    Check if file has ai-exclude: true in YAML frontmatter.

    Returns (is_excluded, reason).
    """
    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()
    except (OSError, UnicodeDecodeError):
        return False, ""

    # Check for YAML frontmatter
    if not content.startswith("---"):
        return False, ""

    # Extract frontmatter
    parts = content.split("---", 2)
    if len(parts) < 3:
        return False, ""

    frontmatter = parts[1]

    # Check for ai-exclude: true
    if not re.search(r"ai-exclude:\s*true", frontmatter, re.IGNORECASE):
        return False, ""

    # Extract reason if present
    reason_match = re.search(r'reason:\s*["\']?([^"\'\n]+)["\']?', frontmatter)
    reason = reason_match.group(1).strip() if reason_match else "Marked as ai-exclude"

    return True, reason


def is_likely_documentation(file_path: str) -> tuple[bool, str]:
    """
    Detect if file is likely documentation based on name patterns.

    Returns (is_doc, reason).
    """
    basename = Path(file_path).name.upper()

    # Common documentation file patterns
    patterns = {
        r"TEST[_-]?PLAN": "Test documentation",
        r"VALIDATION[_-]?REPORT": "Validation records",
        r"MEETING[_-]?NOTES": "Meeting notes",
        r"MINUTES": "Meeting minutes",
        r"ADR[_-]?\d+": "Architecture Decision Record",
        r"CHANGELOG": "Change log",
        r"CONTRIBUTING": "Contribution guidelines",
        r"AUTHORS": "Author list",
        r"NOTES": "General notes",
    }

    for pattern, reason in patterns.items():
        if re.search(pattern, basename):
            return True, reason

    return False, ""


def scan_excluded_files(repo_path: str) -> dict[str, str]:
    """
    Scan repository for files marked with ai-exclude frontmatter.

    Returns dict of {relative_path: exclusion_reason}.
    """
    root = Path(repo_path)
    excluded = {}

    # Scan all .md files for frontmatter
    for md_file in root.rglob("*.md"):
        try:
            rel_path = md_file.relative_to(root)
            is_excluded, reason = parse_frontmatter_exclusion(md_file)

            if is_excluded:
                excluded[str(rel_path)] = reason
        except (ValueError, OSError):
            continue

    return excluded


def estimate_file_tokens(file_path: str | Path) -> int:
    """Estimate tokens in a file (rough estimate: 1 token ≈ 4 chars)."""
    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()
        return len(content) // 4
    except (OSError, UnicodeDecodeError):
        return 0
