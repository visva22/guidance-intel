from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Artifact:
    name: str
    kind: str  # "skill" | "agent" | "workflow" | "instruction"
    source_path: str
    triggers: list[str] = field(default_factory=list)


@dataclass
class TranscriptEvent:
    kind: str  # "skill" | "agent" | "workflow" | "tool"
    name: str
    session_id: str
    timestamp: str | None = None
    metadata: dict | None = None  # For Read tool calls: file_path, offset, limit, manual_reference


@dataclass
class UsageRecord:
    artifact_name: str
    artifact_kind: str
    total_count: int = 0
    session_count: int = 0
    sessions_total: int = 0
    first_seen: str | None = None
    last_seen: str | None = None


@dataclass
class Section:
    """Represents a section within a guidance file."""
    title: str
    start_line: int
    end_line: int
    content: str
    usage_count: int = 0
    sessions_used: set[str] = field(default_factory=set)
    token_estimate: int = 0  # Rough token count


@dataclass
class SectionUsageRecord:
    """Usage statistics for a specific section."""
    section_title: str
    line_range: str  # e.g., "32-45"
    usage_count: int
    usage_percentage: float  # % of total artifact invocations
    token_estimate: int
    is_dead: bool  # True if never used


@dataclass
class ArtifactSectionReport:
    """Section-level coverage for a single artifact."""
    artifact_name: str
    artifact_kind: str
    file_path: str
    total_invocations: int
    sections: list[SectionUsageRecord] = field(default_factory=list)
    dead_section_count: int = 0
    token_waste_estimate: int = 0  # Tokens in unused sections


@dataclass
class ExclusionViolation:
    """Represents AI reading a file marked as excluded."""
    file_path: str
    exclusion_reason: str
    access_count: int
    sessions: list[str]
    token_estimate: int
    total_token_waste: int


@dataclass
class CoverageReport:
    repo_path: str
    analyzed_at: str
    sessions_analyzed: int
    total_artifacts: int
    used_artifacts: int
    dead_artifacts: list[str] = field(default_factory=list)
    coverage_percent: float = 0.0
    usage: list[UsageRecord] = field(default_factory=list)
    section_reports: list[ArtifactSectionReport] = field(default_factory=list)  # Section-level data
    exclusion_violations: list[ExclusionViolation] = field(default_factory=list)  # Exclusion violations
