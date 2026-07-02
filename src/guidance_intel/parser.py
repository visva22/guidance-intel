from __future__ import annotations

import json
import re
from pathlib import Path

from .models import TranscriptEvent

# Blocks the IDE/harness injects into user turns that are NOT the human's words.
# Stripped before treating user text as "what the user asked for" (Use Case 1).
_INJECTED_BLOCK_RE = re.compile(
    r"<(ide_opened_file|ide_selection|system-reminder|local-command-[a-z]+|"
    r"command-[a-z]+|command-name|command-message|command-args)>.*?</\1>",
    re.DOTALL | re.IGNORECASE,
)
# Any remaining self-closing / opening injected tag noise.
_STRAY_TAG_RE = re.compile(r"</?[a-z_-]+>", re.IGNORECASE)
# Explicit @file mentions typed by the user (e.g. "@TEST_PLAN.md").
_AT_MENTION_RE = re.compile(r"@([\w./-]+)")


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
                events.extend(_parse_claude_code_line(line.strip(), session_id))
    except (OSError, UnicodeDecodeError):
        pass
    return events


def _parse_claude_code_line(line: str, session_id: str) -> list[TranscriptEvent]:
    """Parse one transcript line into zero or more events.

    Returns a list because a single assistant message can batch multiple tool
    calls (previously only the first was captured — a data-loss bug that
    undercounted reads and violations).
    """
    if not line:
        return []

    try:
        data = json.loads(line)
    except json.JSONDecodeError:
        return []

    # Causal-chain metadata carried by real Claude Code transcripts. Absent in
    # the flat/generic format, in which case these stay None/False.
    timestamp = data.get("timestamp")
    causal = {
        "uuid": data.get("uuid"),
        "parent_uuid": data.get("parentUuid"),
        "is_sidechain": bool(data.get("isSidechain")),
        "prompt_id": data.get("promptId"),
    }

    line_type = data.get("type")

    # User turns — capture the human's cleaned text (Use Case 1). Tool-result
    # payloads and meta lines are NOT the user speaking, so skip them.
    if line_type == "user":
        user_event = _parse_user_message(data, session_id, timestamp, causal)
        return [user_event] if user_event else []

    # Explicit @file mentions arrive as attachment lines — the cleanest signal
    # of a user-requested file.
    if line_type == "attachment":
        att_event = _parse_attachment(data, session_id, timestamp, causal)
        return [att_event] if att_event else []

    # Extract tool use events - handle both formats:
    # 1. Direct: {"type": "tool_use", "name": "Skill"}
    # 2. Nested: {"type": "assistant", "message": {"content": [{"type": "tool_use"}]}}
    tool_uses = []
    if line_type == "tool_use":
        tool_uses.append(data)
    elif line_type == "assistant":
        message = data.get("message", {})
        content = message.get("content", [])
        if isinstance(content, list):
            tool_uses.extend([item for item in content if item.get("type") == "tool_use"])

    events = []
    for tool_use in tool_uses:
        event = _parse_tool_use(tool_use, session_id, timestamp, causal)
        if event:
            events.append(event)
    return events


def _parse_tool_use(tool_use: dict, session_id: str, timestamp: str | None, causal: dict) -> TranscriptEvent | None:
    tool_name = tool_use.get("name", "")
    tool_input = tool_use.get("input", {})

    if tool_name == "Skill":
        skill_name = tool_input.get("skill", "")
        if skill_name:
            return TranscriptEvent(kind="skill", name=skill_name, session_id=session_id, timestamp=timestamp, **causal)

    elif tool_name == "Agent":
        agent_type = tool_input.get("subagent_type") or tool_input.get("description", "")
        if agent_type:
            return TranscriptEvent(kind="agent", name=agent_type, session_id=session_id, timestamp=timestamp, **causal)

    elif tool_name == "Workflow":
        wf_name = tool_input.get("name", "")
        if wf_name:
            return TranscriptEvent(kind="workflow", name=wf_name, session_id=session_id, timestamp=timestamp, **causal)

    elif tool_name == "Read":
        file_path = tool_input.get("file_path", "")
        if not file_path:
            return None
        is_guidance = _is_guidance_file(file_path)
        # Also capture reads of doc-like files (TEST_PLAN, CHANGELOG, ...) so
        # exclusion violations can fire on them. Detection is name-based only —
        # no file IO in the parser. These are marked doc_reference so coverage
        # counting (which matches on artifact triggers) never picks them up.
        is_doc = (not is_guidance) and _looks_like_doc_name(file_path)
        if is_guidance or is_doc:
            artifact_name = _extract_artifact_name_from_path(file_path)
            kind = _detect_guidance_kind(file_path) if is_guidance else "document"
            metadata = {
                "file_path": file_path,
                "offset": tool_input.get("offset"),
                "limit": tool_input.get("limit"),
                "manual_reference": True,  # Flag as manual, not tool invocation
                "doc_reference": is_doc,  # Doc-like file, not a guidance artifact
            }
            return TranscriptEvent(
                kind=kind,
                name=artifact_name,
                session_id=session_id,
                timestamp=timestamp,
                metadata=metadata,
                **causal,
            )

    return None


# Doc-like filename patterns (mirrors exclusions.is_likely_documentation, but
# name-only and cheap so it can run in the hot parse path).
_DOC_NAME_RE = re.compile(
    r"(TEST[_-]?PLAN|VALIDATION[_-]?REPORT|MEETING[_-]?NOTES|MINUTES|ADR[_-]?\d+|"
    r"CHANGELOG|CONTRIBUTING|AUTHORS|NOTES)",
    re.IGNORECASE,
)


def _looks_like_doc_name(file_path: str) -> bool:
    return bool(_DOC_NAME_RE.search(Path(file_path).name))


def _parse_user_message(data: dict, session_id: str, timestamp: str | None, causal: dict) -> TranscriptEvent | None:
    """Extract genuine human text from a user line, or None if it's not human input."""
    # Tool-result payloads are logged as type:"user" but are tool output, not
    # the human. Meta lines are harness-injected. Neither is user intent.
    if data.get("toolUseResult") is not None or data.get("isMeta"):
        return None

    message = data.get("message", {})
    content = message.get("content")

    text_parts = []
    if isinstance(content, str):
        text_parts.append(content)
    elif isinstance(content, list):
        for block in content:
            if not isinstance(block, dict):
                continue
            # A tool_result block anywhere means this "user" line is tool output.
            if block.get("type") == "tool_result":
                return None
            if block.get("type") == "text":
                text_parts.append(block.get("text", ""))

    raw = "\n".join(p for p in text_parts if p)
    cleaned = clean_user_text(raw)
    if not cleaned:
        return None

    mentions = _AT_MENTION_RE.findall(raw)
    return TranscriptEvent(
        kind="user_message",
        name="user",
        session_id=session_id,
        timestamp=timestamp,
        metadata={"text": cleaned, "mentions": mentions},
        **causal,
    )


def _parse_attachment(data: dict, session_id: str, timestamp: str | None, causal: dict) -> TranscriptEvent | None:
    """Capture @file mentions / attached files as explicit user file references."""
    attachment = data.get("attachment") or {}
    file_path = (
        attachment.get("file_path")
        or attachment.get("filePath")
        or attachment.get("path")
        or attachment.get("filename")
    )
    if not file_path:
        return None
    return TranscriptEvent(
        kind="user_message",
        name="user",
        session_id=session_id,
        timestamp=timestamp,
        metadata={"text": "", "mentions": [file_path], "attachment": True},
        **causal,
    )


def clean_user_text(raw: str) -> str:
    """Strip harness/IDE-injected blocks so only the human's words remain."""
    if not raw:
        return ""
    text = _INJECTED_BLOCK_RE.sub(" ", raw)
    text = _STRAY_TAG_RE.sub(" ", text)
    return " ".join(text.split()).strip()


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
