from __future__ import annotations

import json
from pathlib import Path

from .models import TranscriptEvent


def parse_transcripts(paths: list[str]) -> list[TranscriptEvent]:
    events = []
    for path in paths:
        p = Path(path)
        if p.name == "transcript.jsonl":
            session_id = p.parent.name
        else:
            session_id = p.stem
        if not session_id or session_id == ".":
            session_id = p.stem
        events.extend(_parse_single_transcript(path, session_id))
    return events


def parse_generic_jsonl(paths: list[str]) -> list[TranscriptEvent]:
    events = []
    for path in paths:
        session_id = Path(path).stem
        events.extend(_parse_generic_file(path, session_id))
    return events


def _parse_single_transcript(path: str, session_id: str) -> list[TranscriptEvent]:
    events = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                event = _parse_claude_code_line(line.strip(), session_id)
                if event:
                    events.append(event)
    except (OSError, UnicodeDecodeError):
        pass
    return events


def _parse_claude_code_line(line: str, session_id: str) -> TranscriptEvent | None:
    if not line:
        return None

    try:
        data = json.loads(line)
    except json.JSONDecodeError:
        return None

    if data.get("type") != "tool_use":
        return None

    tool_name = data.get("name", "")
    tool_input = data.get("input", {})
    timestamp = data.get("timestamp")

    if tool_name == "Skill":
        skill_name = tool_input.get("skill", "")
        if skill_name:
            return TranscriptEvent(kind="skill", name=skill_name, session_id=session_id, timestamp=timestamp)

    elif tool_name == "Agent":
        agent_type = tool_input.get("subagent_type") or tool_input.get("description", "")
        if agent_type:
            return TranscriptEvent(kind="agent", name=agent_type, session_id=session_id, timestamp=timestamp)

    elif tool_name == "Workflow":
        wf_name = tool_input.get("name", "")
        if wf_name:
            return TranscriptEvent(kind="workflow", name=wf_name, session_id=session_id, timestamp=timestamp)

    return None


def _parse_generic_file(path: str, session_id: str) -> list[TranscriptEvent]:
    events = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue

                kind = data.get("kind", "")
                name = data.get("name", "")
                if kind and name:
                    events.append(TranscriptEvent(
                        kind=kind,
                        name=name,
                        session_id=data.get("session_id", session_id),
                        timestamp=data.get("timestamp"),
                    ))
    except (OSError, UnicodeDecodeError):
        pass
    return events
