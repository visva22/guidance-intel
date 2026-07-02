"""Classify guidance/doc Read events as user-requested vs autonomous (Use Case 1).

Primary path: walk the causal chain (parent_uuid) from a Read back to the user
turn that initiated it, then match that turn's cleaned text / @mentions against
the file. Falls back to positional heuristics when causal fields are absent
(generic JSONL, older transcripts). Every result carries a machine-readable
reason and the detection method used, so nothing is hidden.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .models import TranscriptEvent

# Causal chain traversal limit: prevents infinite loops in malformed transcripts
# while allowing deep nesting (workflows, multi-turn deferred requests).
MAX_CAUSAL_CHAIN_HOPS = 200

# Heuristic lookback limit: when causal fields are absent, how many recent user
# messages to check. Balances false matches (too many) vs missed deferred requests.
HEURISTIC_LOOKBACK = 3

_ACTION_VERBS = ("read", "check", "review", "look at", "open", "see", "load", "inspect", "execute")
_STOPWORDS = {"the", "a", "an", "md", "txt", "and", "or", "to", "of", "for", "in", "file", "doc", "docs"}


@dataclass
class Classification:
    classification: str  # user_requested | autonomous | uncertain | system | unknown
    confidence: str  # high | medium | low | none
    reason: str
    method: str  # causal | heuristic | none


def build_uuid_index(events: list[TranscriptEvent]) -> dict[str, TranscriptEvent]:
    return {e.uuid: e for e in events if e.uuid}


def _tokens(name: str) -> set[str]:
    """Split a filename/dir into meaningful lowercase tokens."""
    base = re.split(r"[\s_\-./]+", name.lower())
    return {t for t in base if t and t not in _STOPWORDS and len(t) > 1}


def _reference_names(file_path: str) -> tuple[str, str, set[str]]:
    """Return (filename, artifact/dir identifier, keyword tokens) for a path."""
    p = Path(file_path)
    filename = p.name.lower()
    # Prefer the parent dir for SKILL.md-style files (artifact identity lives there).
    identifier = p.parent.name.lower() if p.name.upper() == "SKILL.MD" else p.stem.lower()
    keyword_tokens = _tokens(p.stem) | _tokens(p.parent.name)
    return filename, identifier, keyword_tokens


def _match_text(file_path: str, text: str, mentions: list[str]) -> Classification | None:
    """Score how strongly a user turn refers to file_path. None = no match."""
    filename, identifier, keyword_tokens = _reference_names(file_path)
    text_lower = text.lower()

    # Strongest: explicit @file mention / attachment of this path.
    for m in mentions:
        m_low = m.lower()
        if m_low.endswith(filename) or filename.endswith(Path(m_low).name):
            return Classification("user_requested", "high", "Explicit @mention of file", "causal")

    # Exact filename appears in the human's words.
    if filename and filename in text_lower:
        return Classification("user_requested", "high", "Exact filename in user message", "causal")

    # Artifact/dir identifier + an action verb → confident but not exact.
    if identifier and identifier in text_lower and any(v in text_lower for v in _ACTION_VERBS):
        return Classification("user_requested", "medium", "Artifact name + action verb", "causal")

    # Keyword overlap only → ambiguous (could be a different file with same words).
    if keyword_tokens and keyword_tokens <= set(re.split(r"\W+", text_lower)):
        return Classification("uncertain", "medium", "Keyword overlap only (ambiguous)", "causal")

    return None


def _resolve_user_turn(
    read_event: TranscriptEvent,
    index: dict[str, TranscriptEvent],
) -> TranscriptEvent | None:
    """Walk parent_uuid links back to the originating user_message.

    Tracks visited node UUIDs (not just parent_uuid) to properly detect cycles
    in malformed transcripts.
    """
    seen = set()
    cur = read_event
    hops = 0
    while cur is not None and hops < MAX_CAUSAL_CHAIN_HOPS:
        if cur.uuid:
            if cur.uuid in seen:
                break  # Cycle detected
            seen.add(cur.uuid)
        if cur.parent_uuid is None:
            break
        parent = index.get(cur.parent_uuid)
        if parent is None:
            break
        if parent.kind == "user_message":
            return parent
        cur = parent
        hops += 1
    return None


def classify_read(
    read_event: TranscriptEvent,
    events: list[TranscriptEvent],
    index: dict[str, TranscriptEvent],
) -> Classification:
    file_path = (read_event.metadata or {}).get("file_path", "")
    if not file_path:
        return Classification("unknown", "none", "No file path", "none")

    # Reads inside a subagent are autonomous w.r.t. the user by definition:
    # the user requested the agent, the agent chose the file.
    if read_event.is_sidechain:
        return Classification(
            "autonomous", "high", "Read inside a spawned subagent (sidechain)", "causal"
        )

    # --- Primary path: causal chain available ---
    if read_event.uuid is not None or read_event.parent_uuid is not None:
        user_turn = _resolve_user_turn(read_event, index)
        if user_turn is not None:
            meta = user_turn.metadata or {}
            match = _match_text(file_path, meta.get("text", ""), meta.get("mentions", []))
            if match is not None:
                return match
            return Classification(
                "autonomous", "high", "No user reference in originating turn", "causal"
            )
        # Chain rooted without ever hitting a user message → system/hook-driven.
        return Classification(
            "system", "medium", "No originating user turn in causal chain", "causal"
        )

    # --- Fallback path: no causal fields (generic JSONL / old transcripts) ---
    return _classify_heuristic(read_event, events, file_path)


def _classify_heuristic(
    read_event: TranscriptEvent,
    events: list[TranscriptEvent],
    file_path: str,
) -> Classification:
    """Positional fallback: match against nearest preceding user_message in-session.

    Looks back at most HEURISTIC_LOOKBACK user messages. This limit prevents
    false matches in long sessions while catching recent explicit mentions.
    """
    try:
        idx = events.index(read_event)
    except ValueError:
        idx = len(events)

    user_msgs = []
    for i in range(idx - 1, -1, -1):
        e = events[i]
        if e.session_id != read_event.session_id:
            continue
        if e.kind == "user_message":
            user_msgs.append((idx - i, e))
        if len(user_msgs) >= HEURISTIC_LOOKBACK:
            break

    if not user_msgs:
        # No user text captured at all — cannot determine intent. Do NOT hide it.
        return Classification("unknown", "none", "No user messages available in source", "none")

    for distance, msg in user_msgs:
        meta = msg.metadata or {}
        match = _match_text(file_path, meta.get("text", ""), meta.get("mentions", []))
        if match is not None:
            # Downgrade confidence: positional matching is weaker than causal.
            # Exception: explicit @mentions remain high-confidence regardless of method.
            if match.reason.startswith("Explicit @mention"):
                conf = match.confidence  # Keep HIGH for explicit mentions
            else:
                conf = "medium" if match.confidence == "high" else "low"
            return Classification(match.classification, conf, match.reason + " (positional)", "heuristic")

    return Classification("autonomous", "low", "No user reference in recent messages", "heuristic")
