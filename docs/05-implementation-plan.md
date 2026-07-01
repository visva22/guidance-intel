# Implementation Plan

## Scope

Smallest useful tool: discover guidance, count usage from transcripts, report coverage.

**Total estimated effort: 3-4 days.**

---

## Phase 1: Package Skeleton (Day 1, morning)

| Task | Output |
|------|--------|
| Create src layout | `src/guidance_intel/` |
| pyproject.toml with entry point | `pip install -e .` → `gi` command |
| Data models (4 dataclasses) | `models.py` |
| CLI scaffold with click + rich | `gi --help` works |

**Done when**: `pip install -e . && gi --help` works.

## Phase 2: Discovery (Day 1, afternoon)

| Task | Output |
|------|--------|
| Scan repo for skill/agent/workflow files | List of Artifacts |
| Extract triggers from filenames/content | Trigger patterns per artifact |
| Find Claude Code transcript directory | List of transcript paths |
| `gi discover` command | Prints what was found |

**Done when**: `gi discover` shows correct artifacts for a test repo.

## Phase 3: Transcript Parsing (Day 2)

| Task | Output |
|------|--------|
| Parse Claude Code JSONL transcripts | Stream of TranscriptEvents |
| Extract skill invocations | Events with kind=skill |
| Extract agent spawns | Events with kind=agent |
| Extract workflow runs | Events with kind=workflow |
| Handle malformed lines gracefully | Skip + warn |
| Generic JSONL parser (fallback) | Same event stream |

**Done when**: Can extract events from real Claude Code sessions.

## Phase 4: Counting & Matching (Day 2-3)

| Task | Output |
|------|--------|
| Match events to artifacts by trigger | Matched event → artifact |
| Count per artifact (total, per-session) | UsageRecord list |
| Identify dead artifacts (count == 0) | Dead list |
| Compute coverage percentage | Single number |
| Build CoverageReport | Complete report object |

**Done when**: Produces correct counts for fixture data.

## Phase 5: Reporting (Day 3)

| Task | Output |
|------|--------|
| Terminal reporter (rich tables + bars) | `gi coverage` default output |
| JSON reporter | `gi coverage --format json` |
| Markdown reporter | `gi coverage --format md` |
| `gi dead` command (dead artifacts only) | Filtered output |
| `gi stats` command (detailed per-artifact) | Expanded view |

**Done when**: All three output formats work correctly.

## Phase 6: Testing & Packaging (Day 4)

| Task | Output |
|------|--------|
| Unit tests for discovery | test_discovery.py |
| Unit tests for parsing | test_parser.py |
| Unit tests for counting | test_counter.py |
| Integration test (end-to-end) | test_integration.py |
| Fixture data (fake repo + transcripts) | tests/fixtures/ |
| README.md | User documentation |
| LICENSE (MIT) | License file |
| .gitignore | Standard Python ignores |

**Done when**: `pytest` passes, `pip install .` works cleanly.

---

## External Dependencies

| Package | Purpose |
|---------|---------|
| click | CLI framework |
| rich | Terminal formatting |

**Total: 2 runtime dependencies.** Everything else is stdlib.

Dev dependencies: `pytest`, `pytest-cov`

---

## File Count Estimate

```
src/guidance_intel/
├── __init__.py          (~5 lines)
├── models.py            (~40 lines)
├── discovery.py         (~100 lines)
├── parser.py            (~120 lines)
├── counter.py           (~60 lines)
├── reporter.py          (~150 lines)
└── cli.py               (~80 lines)

tests/
├── test_discovery.py    (~80 lines)
├── test_parser.py       (~100 lines)
├── test_counter.py      (~60 lines)
├── test_reporter.py     (~50 lines)
├── test_integration.py  (~80 lines)
└── fixtures/            (sample data)
```

**~550 lines of source code. ~370 lines of tests.**

Small, focused, maintainable.
