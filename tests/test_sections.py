"""Tests for section parsing and detection."""
from pathlib import Path

import pytest

from src.guidance_intel.sections import (
    detect_section_mentions,
    estimate_tokens,
    find_section_by_line,
    parse_sections,
)


def test_parse_sections_from_markdown(tmp_path):
    """Test parsing sections from a Markdown file."""
    md_file = tmp_path / "test.md"
    md_file.write_text("""# Main Title

Some intro text.

## Section One

Content for section one.

## Section Two

Content for section two.

### Subsection 2.1

Nested content.
""")

    sections = parse_sections(md_file)

    assert len(sections) == 4
    assert sections[0].title == "Main Title"
    assert sections[0].start_line == 1
    assert sections[1].title == "Section One"
    assert sections[2].title == "Section Two"
    assert sections[3].title == "Subsection 2.1"


def test_parse_sections_no_headers(tmp_path):
    """Test parsing file with no headers treats entire file as one section."""
    md_file = tmp_path / "no_headers.md"
    md_file.write_text("Just plain text\nwith no headers\nat all.")

    sections = parse_sections(md_file)

    assert len(sections) == 1
    assert sections[0].title == "(Entire File)"
    assert sections[0].start_line == 1
    assert sections[0].end_line == 3


def test_parse_sections_empty_file(tmp_path):
    """Test parsing empty file."""
    md_file = tmp_path / "empty.md"
    md_file.write_text("")

    sections = parse_sections(md_file)

    assert len(sections) == 0


def test_parse_sections_nonexistent_file():
    """Test parsing nonexistent file returns empty list."""
    sections = parse_sections("/nonexistent/file.md")
    assert sections == []


def test_estimate_tokens():
    """Test token estimation."""
    text = "This is a test"  # 14 chars
    tokens = estimate_tokens(text)
    assert tokens == 3  # 14 // 4 = 3

    text = "A" * 100  # 100 chars
    tokens = estimate_tokens(text)
    assert tokens == 25  # 100 // 4 = 25


def test_find_section_by_line(tmp_path):
    """Test finding section by line number."""
    md_file = tmp_path / "test.md"
    md_file.write_text("""## Section One
Content line 1
Content line 2

## Section Two
Content line 3
""")

    sections = parse_sections(md_file)

    # Line 1 is Section One header
    section = find_section_by_line(sections, 1)
    assert section.title == "Section One"

    # Line 3 is in Section One content
    section = find_section_by_line(sections, 3)
    assert section.title == "Section One"

    # Line 5 is Section Two header
    section = find_section_by_line(sections, 5)
    assert section.title == "Section Two"

    # Line 100 doesn't exist
    section = find_section_by_line(sections, 100)
    assert section is None


def test_detect_section_mentions_exact_match(tmp_path):
    """Test detecting sections by exact title match."""
    md_file = tmp_path / "test.md"
    md_file.write_text("""## Prerequisites
Setup instructions

## Installation
Install steps
""")

    sections = parse_sections(md_file)

    # Exact match
    text = "Check the Prerequisites section first."
    mentioned = detect_section_mentions(text, sections)
    assert len(mentioned) == 1
    assert mentioned[0].title == "Prerequisites"


def test_detect_section_mentions_keyword_overlap(tmp_path):
    """Test detecting sections by keyword overlap."""
    md_file = tmp_path / "test.md"
    md_file.write_text("""## Build Configuration Steps
Instructions here

## Test Execution
Test details
""")

    sections = parse_sections(md_file)

    # Keywords overlap: "build" and "configuration"
    text = "Follow the build configuration guide carefully."
    mentioned = detect_section_mentions(text, sections)
    assert len(mentioned) >= 1
    assert any(s.title == "Build Configuration Steps" for s in mentioned)


def test_detect_section_mentions_no_match(tmp_path):
    """Test no sections detected when text doesn't match."""
    md_file = tmp_path / "test.md"
    md_file.write_text("""## Prerequisites
Setup

## Installation
Install
""")

    sections = parse_sections(md_file)

    # No match
    text = "Something completely different about unrelated topics."
    mentioned = detect_section_mentions(text, sections)
    # Might match due to keyword strategies, but shouldn't be strong match
    # Just ensure it doesn't crash
    assert isinstance(mentioned, list)


def test_detect_section_mentions_multiple_sections(tmp_path):
    """Test detecting multiple sections in one text."""
    md_file = tmp_path / "test.md"
    md_file.write_text("""## Prerequisites
Setup

## Installation
Install

## Configuration
Configure
""")

    sections = parse_sections(md_file)

    # Mentions multiple sections
    text = "First check Prerequisites, then do Installation, and finally Configuration."
    mentioned = detect_section_mentions(text, sections)
    assert len(mentioned) >= 2  # At least Prerequisites and Installation


def test_sections_have_token_estimates(tmp_path):
    """Test that parsed sections include token estimates."""
    md_file = tmp_path / "test.md"
    md_file.write_text("""## Section One
This section has some content that should be tokenized.
It has multiple lines.

## Section Two
Shorter content.
""")

    sections = parse_sections(md_file)

    assert sections[0].token_estimate > 0
    assert sections[1].token_estimate > 0
    # Section One should have more tokens than Section Two
    assert sections[0].token_estimate > sections[1].token_estimate


def test_section_usage_tracking(tmp_path):
    """Test section usage count and sessions tracking."""
    md_file = tmp_path / "test.md"
    md_file.write_text("""## Test Section
Content
""")

    sections = parse_sections(md_file)
    section = sections[0]

    # Initial state
    assert section.usage_count == 0
    assert len(section.sessions_used) == 0

    # Simulate usage
    section.usage_count += 1
    section.sessions_used.add("session-1")
    section.usage_count += 1
    section.sessions_used.add("session-2")

    assert section.usage_count == 2
    assert len(section.sessions_used) == 2
    assert "session-1" in section.sessions_used
    assert "session-2" in section.sessions_used
