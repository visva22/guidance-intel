from __future__ import annotations

from datetime import datetime, timezone

from .models import Artifact, CoverageReport, TranscriptEvent, UsageRecord


def compute_coverage(
    artifacts: list[Artifact],
    events: list[TranscriptEvent],
    repo_path: str,
) -> CoverageReport:
    session_ids = sorted(set(e.session_id for e in events))
    sessions_total = len(session_ids)

    usage_records = []
    for artifact in artifacts:
        record = _count_artifact_usage(artifact, events, sessions_total)
        usage_records.append(record)

    used = [r for r in usage_records if r.total_count > 0]
    dead = [r.artifact_name for r in usage_records if r.total_count == 0]

    total = len(artifacts)
    coverage_pct = (len(used) / total * 100) if total > 0 else 0.0

    return CoverageReport(
        repo_path=repo_path,
        analyzed_at=datetime.now(timezone.utc).isoformat(),
        sessions_analyzed=sessions_total,
        total_artifacts=total,
        used_artifacts=len(used),
        dead_artifacts=dead,
        coverage_percent=round(coverage_pct, 1),
        usage=sorted(usage_records, key=lambda r: r.total_count, reverse=True),
    )


def _count_artifact_usage(
    artifact: Artifact,
    events: list[TranscriptEvent],
    sessions_total: int,
) -> UsageRecord:
    matching_events = _find_matching_events(artifact, events)

    total_count = len(matching_events)
    sessions_with_usage = set(e.session_id for e in matching_events)
    session_count = len(sessions_with_usage)

    timestamps = [e.timestamp for e in matching_events if e.timestamp]
    first_seen = min(timestamps) if timestamps else None
    last_seen = max(timestamps) if timestamps else None

    return UsageRecord(
        artifact_name=artifact.name,
        artifact_kind=artifact.kind,
        total_count=total_count,
        session_count=session_count,
        sessions_total=sessions_total,
        first_seen=first_seen,
        last_seen=last_seen,
    )


def _find_matching_events(artifact: Artifact, events: list[TranscriptEvent]) -> list[TranscriptEvent]:
    if not artifact.triggers:
        return []

    matched = []
    triggers_lower = [t.lower() for t in artifact.triggers]

    for event in events:
        event_name_lower = event.name.lower()
        for trigger in triggers_lower:
            trigger_clean = trigger.lstrip("/")
            if event_name_lower == trigger_clean or event_name_lower == trigger:
                matched.append(event)
                break

    return matched
