"""Exclusion pattern detection and frontmatter parsing."""
from __future__ import annotations

import re
from pathlib import Path

# Token estimation: rough heuristic of 1 token ≈ 4 characters (common for English text).
# Actual token count varies by model and content, but this provides a consistent estimate.
CHARS_PER_TOKEN = 4

# Claude Code Read tool defaults (when offset/limit not specified or limit=None).
# Used to avoid over-counting unbounded reads as "reading entire file to EOF."
DEFAULT_READ_LIMIT = 2000


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
    """Estimate tokens in a file using CHARS_PER_TOKEN heuristic."""
    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()
        return len(content) // CHARS_PER_TOKEN
    except (OSError, UnicodeDecodeError):
        return 0


def estimate_read_tokens(file_path: str | Path, offset: int | None = None, limit: int | None = None) -> int:
    """Estimate tokens for the portion of a file actually read.

    Uses offset/limit (from the Read tool) to count only the lines that were
    loaded, rather than the whole file — so partial reads aren't over-counted.
    Falls back to the whole-file estimate when no range is given.

    When limit is None but offset is specified, assumes Claude Code's default
    limit (DEFAULT_READ_LIMIT) rather than reading to EOF to avoid over-counting.
    """
    if offset is None and limit is None:
        return estimate_file_tokens(file_path)
    try:
        with open(file_path, encoding="utf-8") as f:
            lines = f.readlines()
    except (OSError, UnicodeDecodeError):
        return 0
    start = offset if offset is not None else 0
    start = max(0, start)
    end = start + (limit if limit is not None else DEFAULT_READ_LIMIT)
    end = min(end, len(lines))
    chunk = "".join(lines[start:end])
    return len(chunk) // CHARS_PER_TOKEN
