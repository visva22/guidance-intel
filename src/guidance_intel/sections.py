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

    Returns list of sections whose titles appear in the text.
    """
    text_lower = text.lower()
    mentioned = []

    for section in sections:
        # Check if section title is mentioned
        title_lower = section.title.lower()
        if title_lower in text_lower:
            mentioned.append(section)

    return mentioned
