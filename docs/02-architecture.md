# Architecture Document

## Design Principle

Zero config. Install. Run. See what's used, what's dead.

```
┌──────────────────────────────────────────────────────────┐
│                    CLI: gi coverage                        │
└──────────┬───────────────────────────────────────────────┘
           │
┌──────────▼───────────────────────────────────────────────┐
│                    Discovery                              │
│                                                          │
│  1. Scan repo for guidance artifacts                     │
│     (skills, agents, workflows)                          │
│                                                          │
│  2. Find agent session transcripts                       │
│     (~/.claude/projects/ or provided files)              │
└──────────┬───────────────────────────────────────────────┘
           │
┌──────────▼───────────────────────────────────────────────┐
│                    Parser                                 │
│                                                          │
│  1. Parse guidance files → artifact registry             │
│  2. Parse transcripts → event stream                     │
└──────────┬───────────────────────────────────────────────┘
           │
┌──────────▼───────────────────────────────────────────────┐
│                    Counter                                │
│                                                          │
│  For each event, check: does it match a known artifact?  │
│  Increment usage counts. Track per-session and total.    │
└──────────┬───────────────────────────────────────────────┘
           │
┌──────────▼───────────────────────────────────────────────┐
│                    Reporter                               │
│                                                          │
│  Format: terminal (rich), JSON, or Markdown              │
│  Show: usage counts, dead artifacts, coverage %          │
└───────────────────────────────────────────────────────────┘
```

## Components

### 1. CLI (`gi`)

Commands:
- `gi coverage` — full pipeline: discover → parse → count → report (default)
- `gi discover` — show what artifacts and transcripts were found
- `gi dead` — show only unused/dead guidance artifacts
- `gi stats` — show usage statistics per artifact

### 2. Discovery

Scans known locations:

**Guidance artifacts:**
| Location | Type |
|----------|------|
| `.claude/skills/*/SKILL.md` | skill |
| `.claude/skills/*/` (directory name) | skill |
| `AGENTS.md` (parse for agent names) | agent |
| `.claude/agents/*.md` | agent |
| `.claude/workflows/*.yaml` | workflow |
| `.claude/workflows/*.md` | workflow |
| `CLAUDE.md` | instruction |
| `.claude/CLAUDE.md` | instruction |

**Transcripts:**
| Location | Source |
|----------|--------|
| `~/.claude/projects/<hash>/sessions/` | Claude Code |
| CLI-provided path | Any agent |

### 3. Parser

**Guidance parser** — extracts artifact names and trigger patterns:
- Skill name from directory name or SKILL.md heading
- Agent names from AGENTS.md (look for agent type declarations)
- Workflow names from file names
- Trigger patterns (slash commands, `subagent_type:`, skill names)

**Transcript parser** — extracts events from Claude Code JSONL:
- `Skill` tool calls → skill invocations
- `Agent` tool calls → agent spawns (with `subagent_type`)
- `Workflow` tool calls → workflow runs
- Timestamps and session boundaries

### 4. Counter

Simple and deterministic:
- For each event, match against known artifact triggers
- Increment count for matched artifact
- Track: total invocations, sessions where used, first/last use
- Unmatched events are ignored (we only care about guidance artifacts)

No ML, no heuristics, no fuzzy matching for MVP. Exact name/trigger matching.

### 5. Reporter

Three formats:
- **Terminal** (default): colored bars, tables via `rich`
- **JSON**: machine-readable for CI pipelines
- **Markdown**: shareable reports

Key metrics reported:
- Usage count per artifact
- Coverage percentage (artifacts used / total artifacts)
- Dead artifacts list (zero usage)
- Usage trend (if multiple sessions available)
- Sessions analyzed count

## Data Flow (simplified)

```
Repo files ──► discover skills/agents/workflows
                         │
                         ▼
                   Artifact Registry
                   (name, kind, triggers)
                         │
Transcripts ──► extract events ──► match against registry ──► counts
                                                                │
                                                                ▼
                                                          Coverage Report
```

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| No storage/database | Coverage runs are fast, no need to cache. Stateless. |
| No config files | Nothing to configure. Discovers everything. |
| Exact matching only | Avoids false positives. If we can't confidently match, skip. |
| Count-based metrics | Simple, understandable, actionable. No scores or percentages that need explaining. |
| Terminal-first output | Where developers already are. CI gets JSON. |
