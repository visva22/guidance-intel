from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

from .models import Artifact


def discover_artifacts(repo_path: str) -> list[Artifact]:
    root = Path(repo_path)
    artifacts = []

    artifacts.extend(_discover_skills(root))
    artifacts.extend(_discover_agents(root))
    artifacts.extend(_discover_workflows(root))
    artifacts.extend(_discover_instructions(root))

    return artifacts


def discover_transcripts(repo_path: str, transcripts_path: str | None = None) -> list[str]:
    if transcripts_path:
        return _find_jsonl_files(Path(transcripts_path))

    claude_dir = Path.home() / ".claude" / "projects"
    if not claude_dir.exists():
        return []

    project_dir = _find_project_dir(claude_dir, repo_path)
    if not project_dir:
        return []

    sessions_dir = project_dir / "sessions"
    if not sessions_dir.exists():
        return []

    transcripts = []
    for session_dir in sorted(sessions_dir.iterdir()):
        transcript = session_dir / "transcript.jsonl"
        if transcript.exists():
            transcripts.append(str(transcript))

    return transcripts


def _discover_skills(root: Path) -> list[Artifact]:
    skills_dir = root / ".claude" / "skills"
    if not skills_dir.exists():
        return []

    artifacts = []
    for skill_dir in sorted(skills_dir.iterdir()):
        if not skill_dir.is_dir():
            continue
        name = skill_dir.name
        skill_md = skill_dir / "SKILL.md"
        source = str(skill_md.relative_to(root)) if skill_md.exists() else str(skill_dir.relative_to(root))
        triggers = [name, f"/{name}"]

        if skill_md.exists():
            triggers.extend(_extract_triggers_from_file(skill_md))

        artifacts.append(Artifact(name=name, kind="skill", source_path=source, triggers=triggers))

    return artifacts


def _discover_agents(root: Path) -> list[Artifact]:
    artifacts = []

    agents_md = root / "AGENTS.md"
    if agents_md.exists():
        agents = _parse_agents_md(agents_md)
        for name in agents:
            artifacts.append(Artifact(
                name=name,
                kind="agent",
                source_path=str(agents_md.relative_to(root)),
                triggers=[name, name.lower()],
            ))

    agents_dir = root / ".claude" / "agents"
    if agents_dir.exists():
        for f in sorted(agents_dir.iterdir()):
            if f.suffix == ".md":
                name = f.stem
                if not any(a.name == name for a in artifacts):
                    artifacts.append(Artifact(
                        name=name,
                        kind="agent",
                        source_path=str(f.relative_to(root)),
                        triggers=[name, name.lower()],
                    ))

    return artifacts


def _discover_workflows(root: Path) -> list[Artifact]:
    workflows_dir = root / ".claude" / "workflows"
    if not workflows_dir.exists():
        return []

    artifacts = []
    for f in sorted(workflows_dir.iterdir()):
        if f.suffix in (".yaml", ".yml", ".md"):
            name = f.stem
            artifacts.append(Artifact(
                name=name,
                kind="workflow",
                source_path=str(f.relative_to(root)),
                triggers=[name],
            ))

    return artifacts


def _discover_instructions(root: Path) -> list[Artifact]:
    artifacts = []
    for path in [root / "CLAUDE.md", root / ".claude" / "CLAUDE.md"]:
        if path.exists():
            rel = str(path.relative_to(root))
            artifacts.append(Artifact(
                name=f"instructions:{rel}",
                kind="instruction",
                source_path=rel,
                triggers=[],
            ))
    return artifacts


def _extract_triggers_from_file(path: Path) -> list[str]:
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []

    triggers = []
    for line in content.splitlines():
        lower = line.lower().strip()
        if lower.startswith("trigger:") or lower.startswith("- trigger:"):
            value = line.split(":", 1)[1].strip().strip("`\"'")
            if value:
                triggers.append(value)

    slash_commands = re.findall(r"`(/[\w-]+)`", content)
    triggers.extend(slash_commands)

    return triggers


def _parse_agents_md(path: Path) -> list[str]:
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []

    agents = []
    for line in content.splitlines():
        match = re.match(r"^#{1,3}\s+(.+)", line)
        if match:
            name = match.group(1).strip()
            if name.lower() not in ("agents", "available agents", "agent types"):
                agents.append(name)
            continue

        match = re.match(r"^-\s+\*\*(\w[\w\s-]*)\*\*", line)
        if match:
            agents.append(match.group(1).strip())

    return agents


def _find_project_dir(claude_dir: Path, repo_path: str) -> Path | None:
    abs_path = os.path.abspath(repo_path)

    for project_dir in claude_dir.iterdir():
        if not project_dir.is_dir():
            continue
        if project_dir.name.startswith("."):
            continue

        project_file = project_dir / "project.json"
        if project_file.exists():
            try:
                data = json.loads(project_file.read_text())
                if data.get("path") == abs_path:
                    return project_dir
            except (OSError, json.JSONDecodeError):
                pass

    path_hash = hashlib.sha256(abs_path.encode()).hexdigest()[:16]
    candidate = claude_dir / path_hash
    if candidate.exists():
        return candidate

    safe_name = abs_path.replace("/", "-").strip("-")
    candidate = claude_dir / safe_name
    if candidate.exists():
        return candidate

    return None


def _find_jsonl_files(path: Path) -> list[str]:
    if path.is_file() and path.suffix == ".jsonl":
        return [str(path)]

    if not path.is_dir():
        return []

    return sorted(str(f) for f in path.rglob("*.jsonl"))
