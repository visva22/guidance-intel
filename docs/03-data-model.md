# Data Model

## Overview

Three lightweight data structures. No database. All in-memory during a run.

---

## 1. Artifact

A discovered skill, agent, or workflow in the repository.

```python
@dataclass
class Artifact:
    name: str           # e.g., "graphify", "Explore", "feature-dev"
    kind: str           # "skill" | "agent" | "workflow" | "instruction"
    source_path: str    # where it was found
    triggers: list[str] # patterns that indicate usage in transcripts
```

Examples:
```python
Artifact(name="graphify", kind="skill", source_path=".claude/skills/graphify/SKILL.md", triggers=["graphify", "/graphify"])
Artifact(name="Explore", kind="agent", source_path="AGENTS.md", triggers=["Explore"])
Artifact(name="feature-dev", kind="workflow", source_path=".claude/workflows/feature-dev.yaml", triggers=["feature-dev"])
```

---

## 2. UsageRecord

Tracks how an artifact was used across sessions.

```python
@dataclass
class UsageRecord:
    artifact_name: str
    artifact_kind: str
    total_count: int            # total invocations across all sessions
    session_count: int          # number of sessions where it appeared
    sessions_total: int         # total sessions analyzed
    first_seen: str | None      # ISO timestamp of first use
    last_seen: str | None       # ISO timestamp of most recent use
```

---

## 3. CoverageReport

The final output of a coverage run.

```python
@dataclass
class CoverageReport:
    repo_path: str
    analyzed_at: str                    # ISO timestamp
    sessions_analyzed: int
    total_artifacts: int
    used_artifacts: int
    dead_artifacts: list[str]           # names of never-used artifacts
    coverage_percent: float             # used / total * 100
    usage: list[UsageRecord]            # per-artifact usage data
```

---

## Transcript Event (Internal)

Extracted from Claude Code JSONL during parsing. Not persisted.

```python
@dataclass
class TranscriptEvent:
    timestamp: str
    kind: str           # "skill" | "agent" | "workflow" | "tool"
    name: str           # what was invoked
    session_id: str     # which session this came from
```

---

## Claude Code Transcript Format

Located at: `~/.claude/projects/<project-hash>/sessions/<session-id>/transcript.jsonl`

Relevant entries we extract from:

```json
{"type": "tool_use", "name": "Skill", "input": {"skill": "graphify"}}
{"type": "tool_use", "name": "Agent", "input": {"subagent_type": "Explore", "prompt": "..."}}
{"type": "tool_use", "name": "Workflow", "input": {"name": "feature-dev", "script": "..."}}
```

Extraction rules:
- `name == "Skill"` → skill invocation, artifact name = `input.skill`
- `name == "Agent"` → agent spawn, artifact name = `input.subagent_type` or `input.description`
- `name == "Workflow"` → workflow run, artifact name = `input.name`

---

## Generic JSONL Format (Fallback)

For non-Claude agents:

```json
{"timestamp": "2026-06-29T10:00:00Z", "kind": "skill", "name": "graphify"}
{"timestamp": "2026-06-29T10:00:05Z", "kind": "agent", "name": "Explore"}
{"timestamp": "2026-06-29T10:00:30Z", "kind": "workflow", "name": "deploy"}
```

Required fields: `kind`, `name`
Optional: `timestamp`

---

## JSON Output Format

```json
{
  "repo_path": "/Users/dev/my-project",
  "analyzed_at": "2026-06-30T14:00:00Z",
  "sessions_analyzed": 23,
  "total_artifacts": 11,
  "used_artifacts": 7,
  "dead_artifacts": ["deep-research", "code-reviewer", "security-review"],
  "coverage_percent": 63.6,
  "usage": [
    {
      "artifact_name": "graphify",
      "artifact_kind": "skill",
      "total_count": 47,
      "session_count": 18,
      "sessions_total": 23,
      "first_seen": "2026-06-01T09:00:00Z",
      "last_seen": "2026-06-29T16:30:00Z"
    },
    {
      "artifact_name": "deep-research",
      "artifact_kind": "skill",
      "total_count": 0,
      "session_count": 0,
      "sessions_total": 23,
      "first_seen": null,
      "last_seen": null
    }
  ]
}
```
