"""Skill/agent/workflow dependency tracking & context-leakage detection (Use Case 2).

Primary: attribute each guidance/doc Read to the invocation that caused it, via
the causal chain (parent_uuid), including reads inside spawned subagents
(is_sidechain). Falls back to positional attribution when causal fields are
absent. A read is a "leak" only when it falls outside the invoked artifact's
dependency closure; location decides severity (global skill vs sibling ref).
"""
from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

from .exclusions import estimate_read_tokens
from .models import ArtifactDependencyReport, InvocationDependency, TranscriptEvent

_INVOCATION_KINDS = {"skill", "agent", "workflow"}
# Paths referenced from within a skill file (markdown links, backtick paths, bare paths).
_PATH_REF_RE = re.compile(r"[\w./-]+\.(?:md|txt|yaml|yml|json|prompt)", re.IGNORECASE)


def _read_events_from(invocation: TranscriptEvent, same_line, children_of) -> list[TranscriptEvent]:
    """All Read events whose causal chain roots at this invocation event.

    Includes reads batched in the *same* assistant message as the invocation
    (they share one uuid in real transcripts, so they are siblings, not
    children) as well as reads in descendant messages.
    """
    if not invocation.uuid:
        return []
    reads = []
    seen_events = {id(invocation)}
    stack = []
    # Same-line sibling reads (share the invocation's uuid).
    for sib in same_line.get(invocation.uuid, []):
        if sib is invocation or id(sib) in seen_events:
            continue
        seen_events.add(id(sib))
        if _is_read(sib):
            reads.append(sib)
    stack.extend(children_of.get(invocation.uuid, []))
    seen_uuids = set()
    while stack:
        node = stack.pop()
        if node.uuid in seen_uuids:
            continue
        seen_uuids.add(node.uuid)
        # Another invocation starts its own scope — attribute its reads to it, not us.
        if node.kind in _INVOCATION_KINDS and not _is_read(node):
            continue
        if _is_read(node):
            reads.append(node)
        stack.extend(children_of.get(node.uuid, []))
    return reads


def _is_read(event: TranscriptEvent) -> bool:
    return bool(event.metadata and event.metadata.get("manual_reference") and event.metadata.get("file_path"))


def _primary_key(file_path: str) -> str:
    """Identity for matching a read against the primary artifact file.

    Uses parent/name for SKILL.md-style files so two different skills' SKILL.md
    files don't collide on their shared basename.
    """
    p = Path(file_path)
    if p.name.upper() == "SKILL.MD":
        return f"{p.parent.name}/{p.name}".lower()
    return p.name.lower()


def _parse_closure(primary_path: Path) -> set[str]:
    """Files the primary artifact explicitly references (its declared dependencies)."""
    try:
        content = primary_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return set()
    return {Path(m).name.lower() for m in _PATH_REF_RE.findall(content)}


def _leak_level(file_path: str, primary_source: str | None, in_closure: bool) -> str:
    """Classify a non-primary read by location. '' when not a leak."""
    if in_closure:
        return "none"
    fp_lower = file_path.lower()
    # A read of a user-global skill dir during a project invocation is a near-certain leak.
    if fp_lower.startswith(("~/.claude", "/users/")) and "/.claude/" in fp_lower:
        return "global"
    if "/skills/" in fp_lower or "/agents/" in fp_lower:
        # Sibling project artifact pulled in but not declared → review.
        if primary_source and Path(primary_source).parent.name.lower() in fp_lower:
            return "none"  # within the artifact's own directory
        return "cross-reference"
    return "none"


def analyze_dependencies(
    artifacts,
    events: list[TranscriptEvent],
    repo_path: str,
    artifact_source: dict[str, str] | None = None,
) -> list[ArtifactDependencyReport]:
    artifact_source = artifact_source or {}
    children_of: dict[str, list[TranscriptEvent]] = defaultdict(list)
    same_line: dict[str, list[TranscriptEvent]] = defaultdict(list)
    for e in events:
        if e.parent_uuid:
            children_of[e.parent_uuid].append(e)
        if e.uuid:
            same_line[e.uuid].append(e)

    has_causal = any(e.uuid for e in events)

    # Group invocation events by artifact name.
    invocations: dict[str, list[TranscriptEvent]] = defaultdict(list)
    for e in events:
        if e.kind in _INVOCATION_KINDS and not _is_read(e):
            invocations[e.name].append(e)

    reports = []
    for name, invs in invocations.items():
        kind = invs[0].kind
        source = artifact_source.get(name)
        closure = _parse_closure(Path(repo_path) / source) if source else set()

        # Per-invocation causal attribution.
        per_file: dict[str, InvocationDependency] = {}
        extra_reads_per_inv = []
        overhead_per_inv = []
        # Match the primary file by path identity, not bare basename — every
        # skill's file is "SKILL.md", so basename comparison collides.
        primary_key = _primary_key(source) if source else None
        primary_tokens = 0

        method = "causal" if has_causal else "co-occurrence"
        for inv in invs:
            reads = _read_events_from(inv, same_line, children_of) if has_causal else []
            extra = 0
            overhead = 0
            for r in reads:
                meta = r.metadata or {}
                fp = meta["file_path"]
                tokens = estimate_read_tokens(
                    Path(repo_path) / fp, meta.get("offset"), meta.get("limit")
                )
                is_primary = primary_key is not None and _primary_key(fp) == primary_key
                if is_primary:
                    primary_tokens = max(primary_tokens, tokens)
                    continue
                extra += 1
                overhead += tokens
                in_closure = Path(fp).name.lower() in closure
                dep = per_file.get(fp)
                if dep is None:
                    dep = InvocationDependency(
                        file_path=fp,
                        in_closure=in_closure,
                        leak_level=_leak_level(fp, source, in_closure),
                        via_sidechain=r.is_sidechain,
                    )
                    per_file[fp] = dep
                dep.read_count += 1
                dep.token_estimate = max(dep.token_estimate, tokens)
                dep.via_sidechain = dep.via_sidechain or r.is_sidechain
            extra_reads_per_inv.append(extra)
            overhead_per_inv.append(overhead)

        n = len(invs)
        avg_extra = sum(extra_reads_per_inv) / n if n else 0.0
        avg_overhead = int(sum(overhead_per_inv) / n) if n else 0

        reports.append(ArtifactDependencyReport(
            artifact_name=name,
            artifact_kind=kind,
            invocation_count=n,
            session_count=len(set(i.session_id for i in invs)),
            primary_file=source,
            primary_tokens=primary_tokens,
            dependencies=list(per_file.values()),
            avg_extra_reads=round(avg_extra, 1),
            avg_overhead_tokens=avg_overhead,
            attribution_method=method,
            cooccurrence=_cooccurrence(name, invs, events),
        ))

    # Show the leakiest / most context-heavy artifacts first.
    return sorted(reports, key=lambda r: r.avg_overhead_tokens, reverse=True)


def _cooccurrence(name: str, invs, events) -> dict:
    """Fraction of the artifact's sessions in which each file was also read.

    Aggregate / correlation only — does not imply causation, and cannot resolve
    which of two co-invoked skills owns a shared read.
    """
    sessions = set(i.session_id for i in invs)
    if not sessions:
        return {}
    file_sessions: dict[str, set] = defaultdict(set)
    for e in events:
        if e.session_id in sessions and _is_read(e):
            file_sessions[e.metadata["file_path"]].add(e.session_id)
    return {fp: round(len(s) / len(sessions), 2) for fp, s in file_sessions.items()}
