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
class CoverageReport:
    repo_path: str
    analyzed_at: str
    sessions_analyzed: int
    total_artifacts: int
    used_artifacts: int
    dead_artifacts: list[str] = field(default_factory=list)
    coverage_percent: float = 0.0
    usage: list[UsageRecord] = field(default_factory=list)
