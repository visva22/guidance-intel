# Repository Structure

## Layout

```
guidance-intel/
├── pyproject.toml
├── README.md
├── LICENSE
├── .gitignore
├── docs/
│   ├── 01-project-overview.md
│   ├── 02-architecture.md
│   ├── 03-data-model.md
│   ├── 04-discovery-specification.md
│   ├── 05-implementation-plan.md
│   ├── 06-testing-strategy.md
│   ├── 07-repository-structure.md
│   └── 08-competitive-landscape.md
├── src/
│   └── guidance_intel/
│       ├── __init__.py        # version
│       ├── models.py          # Artifact, UsageRecord, CoverageReport, TranscriptEvent
│       ├── discovery.py       # find artifacts + transcripts
│       ├── parser.py          # parse transcripts into events
│       ├── counter.py         # match events to artifacts, count usage
│       ├── reporter.py        # format output (terminal, JSON, markdown)
│       └── cli.py             # click CLI entry point
└── tests/
    ├── conftest.py            # shared fixtures
    ├── test_discovery.py
    ├── test_parser.py
    ├── test_counter.py
    ├── test_reporter.py
    ├── test_integration.py
    └── fixtures/
        ├── repo/
        │   ├── .claude/
        │   │   ├── skills/
        │   │   │   ├── graphify/SKILL.md
        │   │   │   ├── code-review/SKILL.md
        │   │   │   └── dead-skill/SKILL.md
        │   │   └── workflows/
        │   │       └── feature-dev.yaml
        │   └── AGENTS.md
        └── transcripts/
            ├── session-001.jsonl
            ├── session-002.jsonl
            └── session-003.jsonl
```

## Module Responsibilities

| File | Lines (est.) | Does |
|------|-------------|------|
| `models.py` | ~40 | Dataclasses only. No logic. |
| `discovery.py` | ~100 | Scan filesystem for artifacts + transcripts |
| `parser.py` | ~120 | Read JSONL, extract events |
| `counter.py` | ~60 | Match events to artifacts, tally |
| `reporter.py` | ~150 | Format terminal/JSON/markdown output |
| `cli.py` | ~80 | Wire everything together via click |

**Total: ~550 lines of production code.**

## Dependencies Flow

```
models.py (no imports)
  ↑
discovery.py (imports models)
  ↑
parser.py (imports models)
  ↑
counter.py (imports models)
  ↑
reporter.py (imports models)
  ↑
cli.py (imports all above)
```

No circular dependencies. Each module imports only `models` and stdlib.
`cli.py` is the composition root.

## Entry Point

```toml
[project.scripts]
gi = "guidance_intel.cli:cli"
```
