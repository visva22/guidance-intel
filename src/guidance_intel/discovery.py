"""Discovery for all AI coding assistants using industry-standard patterns.

Auto-discovers artifacts from multiple platforms:
- Claude Code (.claude/)
- GitHub Copilot (.github/copilot/)
- Cursor AI (.cursor/)
- Generic convention (.agents/)
- And more...

See docs/discovery-spec.md for full specification.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

from .models import Artifact

# Industry-standard directory patterns for AI coding assistants
# Using wildcard patterns to match ANY tool's directory structure
# See INDUSTRY_STANDARDS.md for conventions
DISCOVERY_PATTERNS = {
    "skill": [
        # SKILL.md convention - matches .*/skills/*/SKILL.md or skills/*/SKILL.md
        ("*/skills/*/SKILL.md", "parent_dir", True),  # Any dotfolder with skills/
        ("skills/*/SKILL.md", "parent_dir", True),    # No dotfolder
        # Standalone prompts (not in skill directories)
        ("prompts/**/*.md", "stem", False),
        ("prompts/**/*.txt", "stem", False),
        ("prompts/**/*.prompt", "stem", False),
        ("*/prompts/**/*.md", "stem", False),  # Any dotfolder with prompts/
    ],
    "agent": [
        # Special files
        ("AGENTS.md", "special:agents_md", False),  # Agent registry
        # .agent.md suffix convention - matches any location
        ("*/agents/*/*.agent.md", "stem", False),   # Any dotfolder with agents/
        ("agents/*/*.agent.md", "stem", False),     # No dotfolder
        # Direct .md files in agents/ directory
        ("*/agents/*.md", "stem", False),           # Any dotfolder
        ("agents/*.md", "stem", False),             # No dotfolder
    ],
    "workflow": [
        # Generic workflow patterns - any dotfolder or no dotfolder
        ("*/workflows/*.yaml", "stem", False),
        ("*/workflows/*.yml", "stem", False),
        ("*/workflows/*.md", "stem", False),
        ("*/workflows/*.json", "stem", False),
        ("workflows/*.yaml", "stem", False),
        ("workflows/*.yml", "stem", False),
        ("workflows/*.md", "stem", False),
        ("workflows/*.json", "stem", False),
        # Tool definitions (common pattern)
        ("*/tools/**/*.yaml", "stem", False),
        ("*/tools/**/*.yml", "stem", False),
        ("*/tools/**/*.json", "stem", False),
        ("tools/**/*.yaml", "stem", False),
        ("tools/**/*.yml", "stem", False),
        ("tools/**/*.json", "stem", False),
    ],
    "instruction": [
        # Root-level instruction files (common naming patterns)
        ("CLAUDE.md", "special:instruction", False),
        ("INSTRUCTIONS.md", "special:instruction", False),
        ("AI_INSTRUCTIONS.md", "special:instruction", False),
        ("SYSTEM_PROMPT.md", "special:instruction", False),
        # Instruction files in any dotfolder
        ("*/CLAUDE.md", "special:instruction", False),
        ("*/INSTRUCTIONS.md", "special:instruction", False),
        ("*/instructions.md", "special:instruction", False),
        ("*/rules.md", "special:instruction", False),
    ],
    "command": [
        ("*/commands/**/*.md", "stem", False),
        ("*/commands/**/*.yaml", "stem", False),
        ("*/commands/**/*.yml", "stem", False),
        ("commands/**/*.md", "stem", False),
        ("commands/**/*.yaml", "stem", False),
        ("commands/**/*.yml", "stem", False),
    ],
    "template": [
        ("*/templates/**/*.md", "stem", False),
        ("*/templates/**/*.txt", "stem", False),
        ("*/templates/**/*.j2", "stem", False),
        ("*/templates/**/*.jinja", "stem", False),
        ("*/templates/**/*.template", "stem", False),
        ("templates/**/*.md", "stem", False),
        ("templates/**/*.txt", "stem", False),
        ("templates/**/*.j2", "stem", False),
        ("templates/**/*.jinja", "stem", False),
    ],
    "config": [
        ("*/settings.json", "special:config", False),
        ("*/settings.local.json", "special:config", False),
        ("*/config.json", "special:config", False),
        ("*/config.yaml", "special:config", False),
        ("*/config.yml", "special:config", False),
    ],
    "tool": [
        ("*/tools/**/*.yaml", "stem", False),
        ("*/tools/**/*.yml", "stem", False),
        ("*/tools/**/*.json", "stem", False),
        ("tools/**/*.yaml", "stem", False),
        ("tools/**/*.yml", "stem", False),
        ("tools/**/*.json", "stem", False),
    ],
    "context": [
        ("*/context/**/*.md", "stem", False),
        ("*/context/**/*.txt", "stem", False),
        ("context/**/*.md", "stem", False),
        ("context/**/*.txt", "stem", False),
    ],
    "persona": [
        ("*/personas/**/*.md", "stem", False),
        ("*/personas/**/*.yaml", "stem", False),
        ("personas/**/*.md", "stem", False),
        ("personas/**/*.yaml", "stem", False),
    ],
    "example": [
        ("*/examples/**/*.md", "stem", False),
        ("examples/**/*.md", "stem", False),
    ],
    "prompt": [
        ("*/prompts/**/*.md", "stem", False),
        ("*/prompts/**/*.txt", "stem", False),
        ("*/prompts/**/*.prompt", "stem", False),
        ("prompts/**/*.md", "stem", False),
        ("prompts/**/*.txt", "stem", False),
        ("prompts/**/*.prompt", "stem", False),
    ],
    "memory": [
        ("*/memory/**/*.md", "stem", False),
        ("memory/**/*.md", "stem", False),
    ],
}

# Transcript patterns by platform
TRANSCRIPT_PATTERNS = {
    "claude": [
        ("~/.claude/projects/{project}/*.jsonl", "direct"),
        ("~/.claude/projects/{project}/sessions/*/transcript.jsonl", "sessions"),
    ],
    "langchain": [
        (".langchain/*.jsonl", "direct"),
        (".langchain/sessions/*.jsonl", "direct"),
        ("~/.langchain/*.jsonl", "direct"),
        ("~/.langchain/sessions/*.jsonl", "direct"),
    ],
    "crewai": [
        (".crewai/*.jsonl", "direct"),
        (".crewai/sessions/*.jsonl", "direct"),
        (".crewai/logs/*.jsonl", "direct"),
        ("~/.crewai/*.jsonl", "direct"),
        ("~/.crewai/sessions/*.jsonl", "direct"),
        ("~/.crewai/logs/*.jsonl", "direct"),
    ],
    "generic": [
        (".sessions/**/*.jsonl", "direct"),
        ("sessions/**/*.jsonl", "direct"),
        (".transcripts/**/*.jsonl", "direct"),
        ("transcripts/**/*.jsonl", "direct"),
        (".logs/**/*.jsonl", "direct"),
        ("logs/**/*.jsonl", "direct"),
    ],
}


def discover_artifacts(repo_path: str) -> list[Artifact]:
    """Auto-discover all artifacts from any AI assistant using industry-standard patterns.

    Args:
        repo_path: Absolute path to repository root.

    Returns:
        List of discovered artifacts.
    """
    root = Path(repo_path)
    artifacts = []
    seen = set()  # Deduplication: (kind, name, source_path)

    for kind, patterns in DISCOVERY_PATTERNS.items():
        for pattern, name_strategy, extract_triggers in patterns:
            discovered = _discover_pattern(root, kind, pattern, name_strategy, extract_triggers)
            for artifact in discovered:
                key = (artifact.kind, artifact.name, artifact.source_path)
                if key not in seen:
                    seen.add(key)
                    artifacts.append(artifact)

    return artifacts


def discover_transcripts(repo_path: str, transcripts_path: str | None = None) -> list[str]:
    """Auto-discover transcript files from all AI assistants.

    Args:
        repo_path: Absolute path to repository root.
        transcripts_path: Optional explicit path to transcripts (overrides auto-discovery).

    Returns:
        List of transcript file paths.
    """
    if transcripts_path:
        return _find_jsonl_files(Path(transcripts_path))

    transcripts = []
    seen = set()

    # Check Claude Code transcripts
    claude_transcripts = _discover_claude_transcripts(repo_path)
    for t in claude_transcripts:
        if t not in seen:
            seen.add(t)
            transcripts.append(t)

    # Check LangChain transcripts
    repo_root = Path(repo_path)
    for base_dir in [repo_root / ".langchain", Path.home() / ".langchain"]:
        if base_dir.exists():
            for sessions_dir in [base_dir / "sessions", base_dir]:
                if sessions_dir.exists():
                    for jsonl_file in sorted(sessions_dir.glob("*.jsonl")):
                        if jsonl_file.is_file() and str(jsonl_file) not in seen:
                            seen.add(str(jsonl_file))
                            transcripts.append(str(jsonl_file))

    # Check CrewAI transcripts
    for base_dir in [repo_root / ".crewai", Path.home() / ".crewai"]:
        if base_dir.exists():
            for subdir_name in ["sessions", "logs", "."]:
                subdir = base_dir / subdir_name if subdir_name != "." else base_dir
                if subdir.exists():
                    for jsonl_file in sorted(subdir.glob("*.jsonl")):
                        if jsonl_file.is_file() and str(jsonl_file) not in seen:
                            seen.add(str(jsonl_file))
                            transcripts.append(str(jsonl_file))

    # Generic fallback
    common_transcript_dirs = [".sessions", "sessions", ".transcripts", "transcripts", ".logs", "logs"]
    for dir_name in common_transcript_dirs:
        transcript_dir = repo_root / dir_name
        if transcript_dir.exists() and transcript_dir.is_dir():
            for jsonl_file in sorted(transcript_dir.glob("*.jsonl")):
                if jsonl_file.is_file() and str(jsonl_file) not in seen:
                    seen.add(str(jsonl_file))
                    transcripts.append(str(jsonl_file))

    return sorted(list(seen))


def _discover_pattern(
    root: Path,
    kind: str,
    pattern: str,
    name_strategy: str,
    extract_triggers: bool
) -> list[Artifact]:
    """Discover artifacts matching a single pattern.

    Args:
        root: Repository root path.
        kind: Artifact kind.
        pattern: Glob pattern to match.
        name_strategy: How to derive artifact name ("stem", "parent_dir", "special:*").
        extract_triggers: Whether to extract triggers from file content.

    Returns:
        List of artifacts matching this pattern.
    """
    artifacts = []

    # Handle special parsing strategies
    if name_strategy.startswith("special:"):
        special_type = name_strategy.split(":", 1)[1]
        return _discover_special(root, kind, pattern, special_type)

    # Standard glob-based discovery
    try:
        for file_path in sorted(root.glob(pattern)):
            # Skip symlinks (we'll discover the real file)
            if not file_path.is_file() or file_path.is_symlink():
                continue

            # Skip common documentation files that aren't artifacts
            if file_path.name in {"README.md", "CHANGELOG.md", "CONTRIBUTING.md", "LICENSE.md"}:
                continue

            # Skip non-AI dotfolders (IDE configs, etc.)
            path_parts = file_path.parts
            non_ai_dotfolders = {".vscode", ".idea", ".git", ".svn", ".hg", ".DS_Store", "node_modules"}
            if any(part in non_ai_dotfolders for part in path_parts):
                continue

            # Skip reference/support files inside skill directories (applies to ALL platforms)
            if kind == "skill":
                path_parts = file_path.parts

                # Rule 1: Skip files in references/ subdirectory
                if "references" in path_parts:
                    continue

                # Rule 2: If SKILL.md exists in the same directory, only discover SKILL.md
                if "skills" in path_parts and file_path.name != "SKILL.md":
                    parent_dir = file_path.parent
                    # Skip if there's a SKILL.md sibling (this is a reference/support file)
                    if (parent_dir / "SKILL.md").exists():
                        continue
                    # Skip if there's a SKILL.md in parent (this is in a subdirectory like references/)
                    if parent_dir.parent and (parent_dir.parent / "SKILL.md").exists():
                        continue

                # Rule 3: Skip common reference file names regardless of location
                reference_filenames = {"TEST_PLAN.md", "README.md", "NOTES.md", "CHANGELOG.md"}
                if file_path.name in reference_filenames and "skills" in path_parts:
                    continue

            # Skip .agents/skills/ when discovering agents (avoid duplication)
            if kind == "agent":
                try:
                    if ".agents" in file_path.parts:
                        rel_parts = file_path.relative_to(root / ".agents").parts
                        if len(rel_parts) > 0 and rel_parts[0] == "skills":
                            continue
                    # Also skip nested subdirectories under plan/sdd (like .agents/plan/sdd/*)
                    if ".agents" in file_path.parts:
                        rel_parts = file_path.relative_to(root / ".agents").parts
                        # Skip anything more than 2 levels deep under .agents/ (except agents/ subdir)
                        if len(rel_parts) > 2 and rel_parts[0] != "agents":
                            continue
                except ValueError:
                    pass

            # Derive name based on strategy
            if name_strategy == "stem":
                name = file_path.stem
            elif name_strategy == "parent_dir":
                name = file_path.parent.name
            else:
                name = file_path.name

            # Build triggers
            triggers = [name, f"/{name}"]
            if extract_triggers:
                triggers.extend(_extract_triggers_from_file(file_path))

            artifacts.append(Artifact(
                name=name,
                kind=kind,
                source_path=str(file_path.relative_to(root)),
                triggers=triggers
            ))
    except (OSError, ValueError):
        # Pattern doesn't match or invalid path
        pass

    return artifacts


def _discover_special(root: Path, kind: str, pattern: str, special_type: str) -> list[Artifact]:
    """Handle special discovery cases requiring custom parsing logic.

    Args:
        root: Repository root path.
        kind: Artifact kind.
        pattern: File pattern to match (can include wildcards).
        special_type: Type of special handler.

    Returns:
        List of artifacts.
    """
    artifacts = []

    try:
        # Support glob patterns in special handlers
        if "*" in pattern:
            matched_files = list(root.glob(pattern))
        else:
            file_path = root / pattern
            matched_files = [file_path] if file_path.exists() else []

        for file_path in matched_files:
            if not file_path.is_file():
                continue

            # Skip non-AI dotfolders
            path_parts = file_path.parts
            non_ai_dotfolders = {".vscode", ".idea", ".git", ".svn", ".hg", "node_modules"}
            if any(part in non_ai_dotfolders for part in path_parts):
                continue

            rel_path = str(file_path.relative_to(root))

            if special_type == "agents_md":
                # Parse AGENTS.md to extract agent names
                agent_names = _parse_agents_md(file_path)
                if agent_names:
                    # Found actual agent definitions
                    for name in agent_names:
                        artifacts.append(Artifact(
                            name=name,
                            kind="agent",
                            source_path=rel_path,
                            triggers=[name, name.lower()]
                        ))
                else:
                    # No agent definitions found - treat as instruction document
                    artifacts.append(Artifact(
                        name=f"instructions:{rel_path}",
                        kind="instruction",
                        source_path=rel_path,
                        triggers=[]
                    ))

            elif special_type == "instruction":
                # Generic instruction file
                artifacts.append(Artifact(
                    name=f"instructions:{rel_path}",
                    kind="instruction",
                    source_path=rel_path,
                    triggers=[]
                ))

            elif special_type == "config":
                # Configuration file
                artifacts.append(Artifact(
                    name=f"config:{file_path.name}",
                    kind="config",
                    source_path=rel_path,
                    triggers=[]
                ))

    except (OSError, ValueError):
        pass

    return artifacts


def _extract_triggers_from_file(path: Path) -> list[str]:
    """Extract trigger patterns from a file."""
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
    """Parse AGENTS.md to extract agent names.

    CONSERVATIVE approach: Only extracts lowercase-kebab-case agent names (e.g., "my-agent").
    ALL CAPS or Title Case headers are assumed to be documentation sections, not agents.

    If no valid agent names are found, treats the entire file as an instruction document
    (returns empty list so special handler treats it as instruction).
    """
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []

    agents = []

    for line in content.splitlines():
        # Only look for H2 (##) or H3 (###) headers - NOT H1 (#)
        match = re.match(r"^#{2,3}\s+(.+)", line)
        if match:
            name = match.group(1).strip()

            # STRICT CRITERIA: Only kebab-case lowercase names are agents
            # Examples: "local-search", "qdrant-memory", "sdlc-executor"
            # This excludes:
            # - ALL CAPS: "ROLE", "CORE MISSION" (documentation)
            # - Title Case: "Phase 1", "Session Summary" (documentation)
            # - CamelCase: "ExecutorAgent" (rare, but if needed add pattern)

            # Must contain a hyphen and be mostly lowercase
            if "-" in name and name.islower():
                agents.append(name)
            continue

        # Also look for bold list items like: - **agent-name**
        match = re.match(r"^-\s+\*\*([a-z][a-z0-9-]*)\*\*", line)
        if match:
            name = match.group(1).strip()
            if "-" in name:  # Only kebab-case agents
                agents.append(name)

    return agents


def _discover_claude_transcripts(repo_path: str) -> list[str]:
    """Discover Claude Code transcripts."""
    transcripts = []

    claude_dir = Path.home() / ".claude" / "projects"
    if not claude_dir.exists():
        return transcripts

    project_dir = _find_claude_project_dir(claude_dir, repo_path)
    if not project_dir:
        return transcripts

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

    return transcripts


def _find_claude_project_dir(claude_dir: Path, repo_path: str) -> Path | None:
    """Find the Claude project directory for the given repo."""
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
    """Find all JSONL files in a path."""
    if path.is_file() and path.suffix == ".jsonl":
        return [str(path)]

    if not path.is_dir():
        return []

    return sorted(str(f) for f in path.rglob("*.jsonl"))
