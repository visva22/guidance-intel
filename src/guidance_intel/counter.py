from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .classification import build_uuid_index, classify_read
from .dependencies import analyze_dependencies
from .exclusions import estimate_file_tokens, is_likely_documentation, parse_frontmatter_exclusion
from .models import Artifact, ArtifactSectionReport, CoverageReport, ExclusionViolation, SectionUsageRecord, TranscriptEvent, UsageRecord
from .sections import detect_section_mentions, parse_sections


def compute_coverage(
    artifacts: list[Artifact],
    events: list[TranscriptEvent],
    repo_path: str,
    include_sections: bool = False,
    check_violations: bool = False,
    include_dependencies: bool = False,
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

    # Compute section-level coverage if requested
    section_reports = []
    if include_sections:
        section_reports = _compute_section_coverage(artifacts, events, repo_path)

    # Detect exclusion violations if requested
    violations = []
    if check_violations:
        violations = _detect_exclusion_violations(events, repo_path)

    # Dependency / context-leakage analysis if requested
    dependency_reports = []
    if include_dependencies:
        artifact_source = {a.name: a.source_path for a in artifacts}
        dependency_reports = analyze_dependencies(artifacts, events, repo_path, artifact_source)

    return CoverageReport(
        repo_path=repo_path,
        analyzed_at=datetime.now(timezone.utc).isoformat(),
        sessions_analyzed=sessions_total,
        total_artifacts=total,
        used_artifacts=len(used),
        dead_artifacts=dead,
        coverage_percent=round(coverage_pct, 1),
        usage=sorted(usage_records, key=lambda r: r.total_count, reverse=True),
        section_reports=section_reports,
        exclusion_violations=violations,
        dependency_reports=dependency_reports,
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


def _compute_section_coverage(
    artifacts: list[Artifact],
    events: list[TranscriptEvent],
    repo_path: str,
) -> list[ArtifactSectionReport]:
    """Compute section-level coverage for used artifacts."""
    section_reports = []

    for artifact in artifacts:
        # Only analyze artifacts that were actually used
        matching_events = _find_matching_events(artifact, events)
        if not matching_events:
            continue

        # Build full path to artifact file
        file_path = Path(repo_path) / artifact.source_path
        if not file_path.exists():
            continue

        # Parse sections from the file
        sections = parse_sections(file_path)
        if not sections:
            continue

        # For each Read event, correlate with sections
        for event in matching_events:
            # Check if Read tool specified line ranges (offset/limit)
            if event.metadata and event.metadata.get("manual_reference"):
                offset = event.metadata.get("offset")
                limit = event.metadata.get("limit")

                # If line range specified, mark those sections as used
                if offset is not None:
                    start_line = offset + 1  # offset is 0-based, lines are 1-based
                    end_line = start_line + (limit or 100) - 1

                    for section in sections:
                        # Check if section overlaps with read range
                        if not (section.end_line < start_line or section.start_line > end_line):
                            section.usage_count += 1
                            section.sessions_used.add(event.session_id)

            # Get subsequent events in same session (next 5 assistant messages)
            subsequent = _get_subsequent_events(event, events, limit=5)

            # Extract text from subsequent events to detect section mentions
            subsequent_text = " ".join([e.name for e in subsequent])

            # Also include the event name itself (might be description)
            if event.name:
                subsequent_text = event.name + " " + subsequent_text

            # Detect which sections were mentioned
            mentioned_sections = detect_section_mentions(subsequent_text, sections)

            # Mark sections as used
            for section in mentioned_sections:
                section.usage_count += 1
                section.sessions_used.add(event.session_id)

        # Build section usage records
        total_invocations = len(matching_events)
        section_usages = []
        dead_section_count = 0
        token_waste = 0

        for section in sections:
            usage_pct = (section.usage_count / total_invocations * 100) if total_invocations > 0 else 0
            is_dead = section.usage_count == 0

            if is_dead:
                dead_section_count += 1
                token_waste += section.token_estimate

            section_usages.append(SectionUsageRecord(
                section_title=section.title,
                line_range=f"{section.start_line}-{section.end_line}",
                usage_count=section.usage_count,
                usage_percentage=round(usage_pct, 1),
                token_estimate=section.token_estimate,
                is_dead=is_dead,
            ))

        section_reports.append(ArtifactSectionReport(
            artifact_name=artifact.name,
            artifact_kind=artifact.kind,
            file_path=artifact.source_path,
            total_invocations=total_invocations,
            sections=section_usages,
            dead_section_count=dead_section_count,
            token_waste_estimate=token_waste,
        ))

    return sorted(section_reports, key=lambda r: r.token_waste_estimate, reverse=True)


def _get_subsequent_events(
    event: TranscriptEvent,
    all_events: list[TranscriptEvent],
    limit: int = 3,
) -> list[TranscriptEvent]:
    """Get the next N events in the same session after the given event."""
    # Find event index
    try:
        idx = all_events.index(event)
    except ValueError:
        return []

    # Get subsequent events from same session
    subsequent = []
    for e in all_events[idx + 1:]:
        if e.session_id == event.session_id:
            subsequent.append(e)
            if len(subsequent) >= limit:
                break

    return subsequent


def _detect_exclusion_violations(
    events: list[TranscriptEvent],
    repo_path: str,
) -> list[ExclusionViolation]:
    """Detect when AI reads files marked as excluded, classifying each access
    as user-requested vs autonomous (Use Case 1)."""
    violations_map = {}
    index = build_uuid_index(events)

    # Confidence ranking, so the file's headline classification reflects its
    # strongest single access.
    conf_rank = {"high": 3, "medium": 2, "low": 1, "none": 0}
    # Priority for classification types (autonomous violations are most important).
    classification_priority = {"autonomous": 3, "system": 2, "uncertain": 1, "user_requested": 0, "unknown": 0}

    # Deduplication for resumed/compacted sessions (spec §1.0 Corner Cases).
    # Prefer uuid-based dedup; fall back to (file_path, prompt_id) for generic JSONL.
    seen = set()

    for event in events:
        # Only Read events carry a file_path; user_message events set manual_reference-less metadata.
        if not event.metadata or not event.metadata.get("manual_reference"):
            continue
        file_path = event.metadata.get("file_path", "")
        if not file_path:
            continue

        # Dedup: prefer uuid, fall back to (file_path, prompt_id), then (session_id, timestamp, file_path)
        if event.uuid:
            dedup_key = (event.uuid, file_path)
        elif event.prompt_id:
            dedup_key = (event.prompt_id, file_path, event.session_id)
        else:
            dedup_key = (event.session_id, event.timestamp, file_path)

        if dedup_key in seen:
            continue
        seen.add(dedup_key)

        full_path = Path(repo_path) / file_path

        # Check if file has ai-exclude frontmatter
        is_excluded, reason = parse_frontmatter_exclusion(full_path)
        # If not explicitly excluded, check if it looks like documentation
        if not is_excluded:
            is_excluded, reason = is_likely_documentation(file_path)
            if is_excluded:
                reason = f"[Auto-detected] {reason}"

        if not is_excluded:
            continue

        result = classify_read(event, events, index)

        key = file_path
        if key not in violations_map:
            violations_map[key] = {
                "file_path": file_path,
                "exclusion_reason": reason,
                "sessions": set(),
                "access_count": 0,
                "user_requested_count": 0,
                "autonomous_count": 0,
                "uncertain_count": 0,
                "best": None,  # strongest classification for the headline
            }
        v = violations_map[key]
        v["access_count"] += 1
        v["sessions"].add(event.session_id)

        if result.classification == "user_requested":
            v["user_requested_count"] += 1
        elif result.classification == "autonomous":
            v["autonomous_count"] += 1
        elif result.classification == "uncertain":
            v["uncertain_count"] += 1

        # Headline = the highest-priority classification, then most confident.
        # Prioritizes: autonomous > system > uncertain > user_requested/unknown.
        if v["best"] is None:
            v["best"] = result
        else:
            cur = v["best"]
            cur_priority = classification_priority.get(cur.classification, 0)
            new_priority = classification_priority.get(result.classification, 0)
            # Replace if higher priority, or same priority with higher confidence.
            if new_priority > cur_priority or (
                new_priority == cur_priority and conf_rank[result.confidence] > conf_rank[cur.confidence]
            ):
                v["best"] = result

    violations = []
    for v in violations_map.values():
        full_path = Path(repo_path) / v["file_path"]
        token_estimate = estimate_file_tokens(full_path)
        best = v["best"]

        violations.append(ExclusionViolation(
            file_path=v["file_path"],
            exclusion_reason=v["exclusion_reason"],
            access_count=v["access_count"],
            sessions=sorted(v["sessions"]),
            token_estimate=token_estimate,
            total_token_waste=token_estimate * v["access_count"],
            classification=best.classification if best else "unknown",
            confidence=best.confidence if best else "none",
            classification_reason=best.reason if best else "",
            detection_method=best.method if best else "none",
            user_requested_count=v["user_requested_count"],
            autonomous_count=v["autonomous_count"],
            uncertain_count=v["uncertain_count"],
        ))

    return sorted(violations, key=lambda x: x.total_token_waste, reverse=True)
