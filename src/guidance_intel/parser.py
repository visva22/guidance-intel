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

    # Extract tool use events - handle both formats:
    # 1. Direct: {"type": "tool_use", "name": "Skill"}
    # 2. Nested: {"type": "assistant", "message": {"content": [{"type": "tool_use"}]}}
    tool_uses = []
    timestamp = data.get("timestamp")

    if data.get("type") == "tool_use":
        tool_uses.append(data)
    elif data.get("type") == "assistant":
        message = data.get("message", {})
        content = message.get("content", [])
        if isinstance(content, list):
            tool_uses.extend([item for item in content if item.get("type") == "tool_use"])

    if not tool_uses:
        return None

    # Process first tool use (could extend to handle multiple)
    tool_use = tool_uses[0]
    tool_name = tool_use.get("name", "")
    tool_input = tool_use.get("input", {})

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

    elif tool_name == "Read":
        # Track Read tool calls to guidance files (manual skill/agent reference)
        file_path = tool_input.get("file_path", "")
        if file_path and _is_guidance_file(file_path):
            # Extract artifact name from path
            artifact_name = _extract_artifact_name_from_path(file_path)
            kind = _detect_guidance_kind(file_path)

            # Store with metadata about the read
            metadata = {
                "file_path": file_path,
                "offset": tool_input.get("offset"),
                "limit": tool_input.get("limit"),
                "manual_reference": True,  # Flag as manual, not tool invocation
            }

            return TranscriptEvent(
                kind=kind,
                name=artifact_name,
                session_id=session_id,
                timestamp=timestamp,
                metadata=metadata
            )

    return None


def _is_guidance_file(file_path: str) -> bool:
    """Check if file path points to a guidance artifact."""
    path_lower = file_path.lower()

    # Skills
    if "/skills/" in path_lower and file_path.endswith(".md"):
        return True
    if ("prompts/" in path_lower or "/prompts/" in path_lower) and file_path.endswith((".md", ".txt", ".prompt")):
        return True

    # Agents
    if file_path.endswith("AGENTS.md"):
        return True
    if "/agents/" in path_lower and file_path.endswith(".md"):
        return True

    # Workflows
    if "/workflows/" in path_lower and any(file_path.endswith(ext) for ext in [".yaml", ".yml", ".md", ".json"]):
        return True
    if "/tools/" in path_lower and any(file_path.endswith(ext) for ext in [".yaml", ".json"]):
        return True

    # Instructions
    if any(file_path.endswith(name) for name in ["CLAUDE.md", "INSTRUCTIONS.md", "AI_INSTRUCTIONS.md"]):
        return True

    return False


def _extract_artifact_name_from_path(file_path: str) -> str:
    """Extract artifact name from file path."""
    from pathlib import Path
    p = Path(file_path)

    # For SKILL.md, use parent directory name
    if p.name == "SKILL.md":
        return p.parent.name

    # For other .md files in skills/, use filename
    if "/skills/" in file_path:
        return p.stem

    # For agents/, use filename
    if "/agents/" in file_path:
        return p.stem

    # For workflows/, use filename
    if "/workflows/" in file_path:
        return p.stem

    # Default to stem
    return p.stem


def _detect_guidance_kind(file_path: str) -> str:
    """Detect whether file is skill, agent, workflow, or instruction."""
    path_lower = file_path.lower()
    if "/skills/" in path_lower or "prompts/" in path_lower:
        return "skill"
    elif "/agents/" in path_lower or file_path.endswith("AGENTS.md"):
        return "agent"
    elif "/workflows/" in path_lower or "/tools/" in path_lower or "tools/" in path_lower:
        return "workflow"
    else:
        return "instruction"


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
