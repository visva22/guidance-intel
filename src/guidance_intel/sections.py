"""Section parsing for guidance files."""
from __future__ import annotations

import re
from pathlib import Path

from .models import Section


def parse_sections(file_path: str | Path) -> list[Section]:
    """
    Parse a Markdown guidance file into sections based on headers.

    Returns list of Section objects with title, line ranges, and content.
    """
    try:
        with open(file_path, encoding="utf-8") as f:
            lines = f.readlines()
    except (OSError, UnicodeDecodeError):
        return []

    sections = []
    current_section = None
    current_lines = []
    line_num = 0

    for i, line in enumerate(lines, start=1):
        # Detect Markdown headers (##, ###, etc.)
        header_match = re.match(r"^(#{1,6})\s+(.+)$", line)

        if header_match:
            # Save previous section
            if current_section:
                content = "".join(current_lines)
                sections.append(Section(
                    title=current_section["title"],
                    start_line=current_section["start"],
                    end_line=i - 1,
                    content=content,
                    token_estimate=estimate_tokens(content),
                ))

            # Start new section
            level = len(header_match.group(1))
            title = header_match.group(2).strip()
            current_section = {"title": title, "start": i, "level": level}
            current_lines = [line]
        elif current_section:
            current_lines.append(line)
        line_num = i

    # Save last section
    if current_section:
        content = "".join(current_lines)
        sections.append(Section(
            title=current_section["title"],
            start_line=current_section["start"],
            end_line=line_num,
            content=content,
            token_estimate=estimate_tokens(content),
        ))

    # Handle files with no headers (treat entire file as one section)
    if not sections and lines:
        content = "".join(lines)
        sections.append(Section(
            title="(Entire File)",
            start_line=1,
            end_line=len(lines),
            content=content,
            token_estimate=estimate_tokens(content),
        ))

    return sections


def estimate_tokens(text: str) -> int:
    """
    Rough token estimate using character count.

    Rule of thumb: 1 token ≈ 4 characters for English text.
    This is a simplification; real tokenization varies by model.
    """
    return len(text) // 4


def find_section_by_line(sections: list[Section], line_num: int) -> Section | None:
    """Find which section contains the given line number."""
    for section in sections:
        if section.start_line <= line_num <= section.end_line:
            return section
    return None


def detect_section_mentions(text: str, sections: list[Section]) -> list[Section]:
    """
    Detect which sections are mentioned in the given text.

    Uses multiple strategies:
    1. Exact title match
    2. Keyword overlap (>50% of significant words)
    3. Key phrase extraction from section content
    """
    text_lower = text.lower()
    mentioned = []

    for section in sections:
        score = 0

        # Strategy 1: Exact title match
        title_lower = section.title.lower()
        if title_lower in text_lower:
            score += 10

        # Strategy 2: Title words overlap
        title_words = set(re.findall(r'\w+', title_lower))
        # Filter out common words
        title_words = {w for w in title_words if len(w) > 3 and w not in {'this', 'that', 'with', 'from', 'have', 'will', 'your'}}

        if title_words:
            text_words = set(re.findall(r'\w+', text_lower))
            overlap = title_words & text_words
            overlap_pct = len(overlap) / len(title_words)

            if overlap_pct >= 0.5:  # 50% of title words mentioned
                score += int(overlap_pct * 5)

        # Strategy 3: Extract key phrases from section content (first 200 chars)
        content_sample = section.content[:200].lower()
        key_phrases = _extract_key_phrases(content_sample)

        for phrase in key_phrases:
            if phrase in text_lower and len(phrase) > 5:
                score += 2

        # Threshold: score >= 3 means section was likely referenced
        if score >= 3:
            mentioned.append(section)

    return mentioned


def _extract_key_phrases(text: str) -> list[str]:
    """Extract potential key phrases from text (simple heuristic)."""
    # Find words in **bold** or `code`
    bold_words = re.findall(r'\*\*([^*]+)\*\*', text)
    code_words = re.findall(r'`([^`]+)`', text)

    # Find capitalized terms (likely important concepts)
    cap_words = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b', text)

    phrases = bold_words + code_words + cap_words
    return [p.lower() for p in phrases if len(p) > 3]
