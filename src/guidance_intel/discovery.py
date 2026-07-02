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

    transcripts = []

    # Check multiple agent platform locations
    # Claude Code: ~/.claude/projects/{project-dir}/*.jsonl or {project-dir}/sessions/*/transcript.jsonl
    claude_dir = Path.home() / ".claude" / "projects"
    if claude_dir.exists():
        project_dir = _find_project_dir(claude_dir, repo_path)
        if project_dir:
            # UUID-named JSONL files directly in project folder
            for jsonl_file in sorted(project_dir.glob("*.jsonl")):
                if jsonl_file.is_file():
                    transcripts.append(str(jsonl_file))
            # Legacy sessions/ subdirectory structure
            sessions_dir = project_dir / "sessions"
            if sessions_dir.exists():
                for session_dir in sorted(sessions_dir.iterdir()):
                    transcript = session_dir / "transcript.jsonl"
                    if transcript.exists():
                        transcripts.append(str(transcript))

    # LangChain: .langchain/ in repo or ~/.langchain/
    langchain_dirs = [
        Path(repo_path) / ".langchain",
        Path.home() / ".langchain",
    ]
    for base_dir in langchain_dirs:
        if base_dir.exists():
            # Check for sessions/ subdirectory
            sessions_dir = base_dir / "sessions"
            if sessions_dir.exists():
                for session_file in sorted(sessions_dir.glob("*.jsonl")):
                    if session_file.is_file():
                        transcripts.append(str(session_file))
            # Also check root for JSONL files
            for jsonl_file in sorted(base_dir.glob("*.jsonl")):
                if jsonl_file.is_file() and str(jsonl_file) not in transcripts:
                    transcripts.append(str(jsonl_file))

    # CrewAI: .crewai/ in repo or ~/.crewai/
    crewai_dirs = [
        Path(repo_path) / ".crewai",
        Path.home() / ".crewai",
    ]
    for base_dir in crewai_dirs:
        if base_dir.exists():
            # Check for sessions/ or logs/ subdirectories
            for subdir_name in ["sessions", "logs"]:
                subdir = base_dir / subdir_name
                if subdir.exists():
                    for session_file in sorted(subdir.glob("*.jsonl")):
                        if session_file.is_file() and str(session_file) not in transcripts:
                            transcripts.append(str(session_file))
            # Also check root for JSONL files
            for jsonl_file in sorted(base_dir.glob("*.jsonl")):
                if jsonl_file.is_file() and str(jsonl_file) not in transcripts:
                    transcripts.append(str(jsonl_file))

    # Generic fallback: check repo root for common patterns
    repo_root = Path(repo_path)
    common_transcript_dirs = [".sessions", "sessions", ".transcripts", "transcripts", ".logs", "logs"]
    for dir_name in common_transcript_dirs:
        transcript_dir = repo_root / dir_name
        if transcript_dir.exists() and transcript_dir.is_dir():
            for jsonl_file in sorted(transcript_dir.glob("*.jsonl")):
                if jsonl_file.is_file() and str(jsonl_file) not in transcripts:
                    transcripts.append(str(jsonl_file))

    return sorted(list(set(transcripts)))  # Deduplicate and sort


def _discover_skills(root: Path) -> list[Artifact]:
    """Discover skills using multiple common patterns."""
    artifacts = []
    seen_names = set()

    # Pattern 1: .claude/skills/*/SKILL.md (Claude Code standard)
    skills_dir = root / ".claude" / "skills"
    if skills_dir.exists():
        for skill_dir in sorted(skills_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            name = skill_dir.name
            if name in seen_names:
                continue
            seen_names.add(name)

            skill_md = skill_dir / "SKILL.md"
            source = str(skill_md.relative_to(root)) if skill_md.exists() else str(skill_dir.relative_to(root))
            triggers = [name, f"/{name}"]

            if skill_md.exists():
                triggers.extend(_extract_triggers_from_file(skill_md))

            artifacts.append(Artifact(name=name, kind="skill", source_path=source, triggers=triggers))

    # Pattern 2: .agents/skills/**/SKILL.md (custom agent frameworks)
    # Only discover SKILL.md files; other .md files in skill dirs are references/metadata
    agents_skills_dir = root / ".agents" / "skills"
    if agents_skills_dir.exists():
        for skill_md in sorted(agents_skills_dir.rglob("SKILL.md")):
            if skill_md.is_file():
                # Use parent directory name as skill name
                name = skill_md.parent.name

                if name in seen_names:
                    continue
                seen_names.add(name)

                source = str(skill_md.relative_to(root))
                triggers = [name, f"/{name}"]
                triggers.extend(_extract_triggers_from_file(skill_md))

                artifacts.append(Artifact(name=name, kind="skill", source_path=source, triggers=triggers))

    # Pattern 3: skills/**/*.md (generic skills directory)
    skills_root = root / "skills"
    if skills_root.exists():
        for md_file in sorted(skills_root.rglob("*.md")):
            if md_file.is_file():
                # Try to use directory name for structure, fallback to filename
                if md_file.parent != skills_root:
                    name = md_file.parent.name
                else:
                    name = md_file.stem

                if name in seen_names:
                    continue
                seen_names.add(name)

                source = str(md_file.relative_to(root))
                triggers = [name, f"/{name}"]
                triggers.extend(_extract_triggers_from_file(md_file))

                artifacts.append(Artifact(name=name, kind="skill", source_path=source, triggers=triggers))

    # Pattern 4: prompts/**/*.{md,txt,prompt} (prompt libraries)
    prompts_dir = root / "prompts"
    if prompts_dir.exists():
        for ext in ["*.md", "*.txt", "*.prompt"]:
            for prompt_file in sorted(prompts_dir.rglob(ext)):
                if prompt_file.is_file():
                    name = prompt_file.stem

                    if name in seen_names:
                        continue
                    seen_names.add(name)

                    source = str(prompt_file.relative_to(root))
                    triggers = [name, f"/{name}"]

                    artifacts.append(Artifact(name=name, kind="skill", source_path=source, triggers=triggers))

    return artifacts


def _discover_agents(root: Path) -> list[Artifact]:
    """Discover agents using multiple common patterns."""
    artifacts = []
    seen_names = set()

    # Pattern 1: AGENTS.md (Claude Code standard)
    agents_md = root / "AGENTS.md"
    if agents_md.exists():
        agents = _parse_agents_md(agents_md)
        for name in agents:
            if name not in seen_names:
                seen_names.add(name)
                artifacts.append(Artifact(
                    name=name,
                    kind="agent",
                    source_path=str(agents_md.relative_to(root)),
                    triggers=[name, name.lower()],
                ))

    # Pattern 2: .claude/agents/*.md (individual agent files)
    claude_agents_dir = root / ".claude" / "agents"
    if claude_agents_dir.exists():
        for f in sorted(claude_agents_dir.iterdir()):
            if f.suffix == ".md":
                name = f.stem
                if name not in seen_names:
                    seen_names.add(name)
                    artifacts.append(Artifact(
                        name=name,
                        kind="agent",
                        source_path=str(f.relative_to(root)),
                        triggers=[name, name.lower()],
                    ))

    # Pattern 3: .agents/**/*.md (custom agent frameworks)
    # Skip .agents/skills/ to avoid duplication with skill discovery
    agents_dir = root / ".agents"
    if agents_dir.exists():
        for md_file in sorted(agents_dir.rglob("*.md")):
            if md_file.is_file() and md_file.name != "AGENTS.md":
                # Skip files in .agents/skills/ directory (already discovered as skills)
                try:
                    rel_path = md_file.relative_to(agents_dir)
                    if rel_path.parts[0] == "skills":
                        continue
                except (ValueError, IndexError):
                    pass

                name = md_file.stem
                if name not in seen_names:
                    seen_names.add(name)
                    artifacts.append(Artifact(
                        name=name,
                        kind="agent",
                        source_path=str(md_file.relative_to(root)),
                        triggers=[name, name.lower()],
                    ))

    # Pattern 4: agents/**/*.md (generic agents directory)
    agents_root = root / "agents"
    if agents_root.exists():
        for md_file in sorted(agents_root.rglob("*.md")):
            if md_file.is_file() and md_file.name != "AGENTS.md":
                name = md_file.stem
                if name not in seen_names:
                    seen_names.add(name)
                    artifacts.append(Artifact(
                        name=name,
                        kind="agent",
                        source_path=str(md_file.relative_to(root)),
                        triggers=[name, name.lower()],
                    ))

    return artifacts


def _discover_workflows(root: Path) -> list[Artifact]:
    """Discover workflows using multiple common patterns."""
    artifacts = []
    seen_names = set()

    # Pattern 1: .claude/workflows/*.{yaml,yml,md} (Claude Code standard)
    claude_workflows_dir = root / ".claude" / "workflows"
    if claude_workflows_dir.exists():
        for f in sorted(claude_workflows_dir.iterdir()):
            if f.suffix in (".yaml", ".yml", ".md"):
                name = f.stem
                if name not in seen_names:
                    seen_names.add(name)
                    artifacts.append(Artifact(
                        name=name,
                        kind="workflow",
                        source_path=str(f.relative_to(root)),
                        triggers=[name],
                    ))

    # Pattern 2: workflows/**/*.{yaml,yml,md,json} (generic workflows directory)
    workflows_root = root / "workflows"
    if workflows_root.exists():
        for ext in [".yaml", ".yml", ".md", ".json"]:
            for wf_file in sorted(workflows_root.rglob(f"*{ext}")):
                if wf_file.is_file():
                    name = wf_file.stem
                    if name not in seen_names:
                        seen_names.add(name)
                        artifacts.append(Artifact(
                            name=name,
                            kind="workflow",
                            source_path=str(wf_file.relative_to(root)),
                            triggers=[name],
                        ))

    # Pattern 3: .agents/workflows/*.{yaml,yml,md} (custom agent frameworks)
    agents_workflows_dir = root / ".agents" / "workflows"
    if agents_workflows_dir.exists():
        for ext in [".yaml", ".yml", ".md", ".json"]:
            for wf_file in sorted(agents_workflows_dir.rglob(f"*{ext}")):
                if wf_file.is_file():
                    name = wf_file.stem
                    if name not in seen_names:
                        seen_names.add(name)
                        artifacts.append(Artifact(
                            name=name,
                            kind="workflow",
                            source_path=str(wf_file.relative_to(root)),
                            triggers=[name],
                        ))

    # Pattern 4: tools/**/*.{yaml,yml,json} (LangChain/CrewAI style)
    tools_dir = root / "tools"
    if tools_dir.exists():
        for ext in [".yaml", ".yml", ".json"]:
            for tool_file in sorted(tools_dir.rglob(f"*{ext}")):
                if tool_file.is_file():
                    name = tool_file.stem
                    if name not in seen_names:
                        seen_names.add(name)
                        artifacts.append(Artifact(
                            name=name,
                            kind="workflow",  # treat tools as workflow-like artifacts
                            source_path=str(tool_file.relative_to(root)),
                            triggers=[name],
                        ))

    return artifacts


def _discover_instructions(root: Path) -> list[Artifact]:
    """Discover instruction files using multiple common patterns."""
    artifacts = []
    seen_paths = set()

    # Common instruction file patterns
    instruction_patterns = [
        root / "CLAUDE.md",
        root / ".claude" / "CLAUDE.md",
        root / "INSTRUCTIONS.md",
        root / ".agents" / "INSTRUCTIONS.md",
        root / "AI_INSTRUCTIONS.md",
        root / "SYSTEM_PROMPT.md",
        root / ".ai" / "instructions.md",
    ]

    for path in instruction_patterns:
        if path.exists() and path not in seen_paths:
            seen_paths.add(path)
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

    # Also check with leading hyphen (Claude Code stores projects as -Users-...-project-name)
    safe_name_with_hyphen = "-" + safe_name
    candidate = claude_dir / safe_name_with_hyphen
    if candidate.exists():
        return candidate

    return None


def _find_jsonl_files(path: Path) -> list[str]:
    if path.is_file() and path.suffix == ".jsonl":
        return [str(path)]

    if not path.is_dir():
        return []

    return sorted(str(f) for f in path.rglob("*.jsonl"))
