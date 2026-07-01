# Discovery Specification

## What Discovery Does

Automatically finds two things:
1. Guidance artifacts in the current repo
2. Agent session transcripts to analyze

No config. No user input beyond running the command.

---

## Guidance Artifact Discovery

### Scan Rules

| Pattern | Kind | Name Extraction |
|---------|------|-----------------|
| `.claude/skills/<name>/SKILL.md` | skill | directory name |
| `.claude/skills/<name>/` (no SKILL.md) | skill | directory name |
| `AGENTS.md` | agent | parse headings/agent declarations |
| `.claude/agents/<name>.md` | agent | filename without extension |
| `.claude/workflows/<name>.yaml` | workflow | filename without extension |
| `.claude/workflows/<name>.md` | workflow | filename without extension |
| `CLAUDE.md` | instruction | "root-instructions" |
| `.claude/CLAUDE.md` | instruction | "project-instructions" |

### Trigger Extraction

For each discovered artifact, generate trigger patterns:

**Skills:**
- Skill name (e.g., `"graphify"`)
- Slash command (e.g., `"/graphify"`)
- If SKILL.md has a `Trigger:` line, extract that pattern

**Agents:**
- Agent name (e.g., `"Explore"`)
- Agent type variants (e.g., `"Explore"`, `"explore"`)

**Workflows:**
- Workflow name (e.g., `"feature-dev"`)

### AGENTS.md Parsing

AGENTS.md typically declares agents in a structured format. Look for:
- Headings that name agents (`## Explore`, `## Plan`)
- Type declarations in lists (`- Explore: Fast read-only search agent`)
- Agent type definitions with descriptions

Extract each as a separate artifact.

---

## Transcript Discovery

### Claude Code Sessions

**Location**: `~/.claude/projects/`

**Structure:**
```
~/.claude/projects/
└── <project-path-hash>/
    └── sessions/
        └── <session-id>/
            └── transcript.jsonl
```

**Project matching:**
The framework needs to find transcripts for the *current* repo. Strategy:
1. Hash the current repo's absolute path
2. Look for matching project directory in `~/.claude/projects/`
3. If not found, try matching by scanning project directories for path references

**Session selection:**
- Default: all sessions found for this project
- `--last N`: only the N most recent sessions
- `--since DATE`: sessions after a date

### User-Provided Transcripts

```bash
gi coverage --transcripts path/to/sessions/
gi coverage --transcripts file.jsonl
```

Accepts a directory (scans for .jsonl files) or a single file.

---

## Discovery Output

```python
@dataclass
class DiscoveryResult:
    artifacts: list[Artifact]       # all found guidance artifacts
    transcript_paths: list[str]     # all found transcript files
    repo_path: str                  # the repository being analyzed
```

`gi discover` prints this in human-readable form:

```
Repository: /Users/dev/my-project

Guidance Artifacts Found: 8
  [skill] graphify              .claude/skills/graphify/SKILL.md
  [skill] code-review           .claude/skills/code-review/SKILL.md
  [skill] deep-research         .claude/skills/deep-research/SKILL.md
  [skill] simplify              .claude/skills/simplify/SKILL.md
  [agent] Explore               AGENTS.md
  [agent] Plan                  AGENTS.md
  [agent] code-reviewer         AGENTS.md
  [workflow] feature-dev        .claude/workflows/feature-dev.yaml

Transcripts Found: 23 sessions
  Source: ~/.claude/projects/abc123/sessions/
  Date range: 2026-06-01 to 2026-06-29
```

---

## Edge Cases

| Situation | Behavior |
|-----------|----------|
| No guidance artifacts found | Print: "No skills, agents, or workflows found in this repo." Exit 0. |
| No transcripts found | Print: "No sessions found. Use --transcripts to provide." Exit 1. |
| Repo has guidance but no transcripts | Suggest running some sessions first |
| Very large transcript directory | Stream-parse, don't load all into memory |
| Corrupted/incomplete JSONL | Skip malformed lines, warn, continue |
| Permission denied on ~/.claude | Warn, suggest --transcripts flag |
