# Generic Discovery Design

## Problem

Current implementation is too Claude Code-specific:
- Hardcoded paths: `.claude/skills/`, `AGENTS.md`, `.claude/workflows/`
- Assumes specific file structures
- Can't discover skills in custom locations (e.g., `.agents/skills/`, `prompts/`, `tools/`)
- Limits adoption by other AI agent frameworks

## Solution: Configuration-Driven Discovery

### 1. Discovery Configuration File (Optional)

Projects can provide `.guidance-intel.yaml`:

```yaml
discovery:
  skills:
    - pattern: ".claude/skills/*/SKILL.md"
      name_from: directory  # or: filename, content
      triggers_from: [name, file_content]
    - pattern: ".agents/skills/**/*.md"
      name_from: filename
      triggers_from: [name]
    - pattern: "prompts/*.prompt"
      name_from: filename
      triggers_from: [name]
  
  agents:
    - pattern: "AGENTS.md"
      parse_as: markdown_headers
    - pattern: ".claude/agents/*.md"
      name_from: filename
  
  workflows:
    - pattern: ".claude/workflows/*.{yaml,yml,md}"
      name_from: filename
  
  instructions:
    - pattern: "CLAUDE.md"
    - pattern: ".claude/CLAUDE.md"

transcripts:
  format: claude_code  # or: generic_jsonl, custom
  event_mappings:
    skill: "Skill"       # Tool name for skills
    agent: "Agent"       # Tool name for agents
    workflow: "Workflow" # Tool name for workflows
```

### 2. Smart Defaults (No Config Needed)

If no config file exists, use sensible defaults:

```python
DEFAULT_PATTERNS = {
    "skill": [
        ".claude/skills/*/SKILL.md",
        ".agents/skills/**/*.md",
        "skills/**/*.md",
        "prompts/**/*.prompt",
    ],
    "agent": [
        "AGENTS.md",
        ".claude/agents/*.md",
        "agents/**/*.md",
    ],
    "workflow": [
        ".claude/workflows/*.{yaml,yml,md}",
        "workflows/**/*.{yaml,yml,md}",
    ],
    "instruction": [
        "CLAUDE.md",
        ".claude/CLAUDE.md",
        "INSTRUCTIONS.md",
        "AI_INSTRUCTIONS.md",
    ],
}
```

### 3. Recursive Discovery

Use `glob` patterns for flexible discovery:

```python
def discover_by_pattern(root: Path, pattern: str) -> list[Path]:
    """Find files matching glob pattern, recursively."""
    return list(root.glob(pattern))
```

### 4. Flexible Name Extraction

```python
def extract_name(path: Path, strategy: str) -> str:
    """Extract artifact name based on strategy."""
    if strategy == "filename":
        return path.stem
    elif strategy == "directory":
        return path.parent.name
    elif strategy == "content":
        return _extract_from_frontmatter(path)  # YAML frontmatter
    else:
        return path.stem  # default
```

### 5. Pluggable Transcript Parsers

```python
class TranscriptParser(Protocol):
    def parse(self, path: str) -> list[TranscriptEvent]:
        ...

class ClaudeCodeParser(TranscriptParser):
    """Parse Claude Code JSONL format."""
    ...

class GenericJSONLParser(TranscriptParser):
    """Parse generic JSONL with custom field mappings."""
    ...

# Usage
parser = get_parser(config.transcripts.format)
events = parser.parse(transcript_path)
```

## Benefits

1. **Generic**: Works with any AI agent framework
2. **Flexible**: Custom project structures supported
3. **Zero config**: Smart defaults work out of the box
4. **Extensible**: Easy to add new patterns/formats
5. **Migration-friendly**: Old projects work without changes

## Migration Path

Phase 1: Keep current hardcoded discovery as default
Phase 2: Add config file support (opt-in)
Phase 3: Migrate to pattern-based with smart defaults
Phase 4: Document custom framework integration

## Implementation Estimate

- Config file parser: 1 hour
- Pattern-based discovery: 2 hours
- Pluggable parsers: 2 hours
- Tests + docs: 2 hours
**Total: 7 hours (1 day)**
