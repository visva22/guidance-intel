# Testing Strategy

## Approach

Fast, deterministic tests against fixture data. No network, no LLM, no flakiness.

---

## Unit Tests

### test_discovery.py

| Test | Asserts |
|------|---------|
| `test_finds_skills_in_claude_dir` | Discovers .claude/skills/*/SKILL.md |
| `test_finds_agents_from_agents_md` | Parses AGENTS.md for agent names |
| `test_finds_workflows` | Discovers .claude/workflows/*.yaml |
| `test_extracts_skill_triggers` | Name + slash command as triggers |
| `test_empty_repo` | Returns empty list, no crash |
| `test_ignores_unrelated_files` | Doesn't pick up random markdown |

### test_parser.py

| Test | Asserts |
|------|---------|
| `test_parses_skill_tool_use` | Extracts skill name from Skill tool call |
| `test_parses_agent_tool_use` | Extracts agent type from Agent tool call |
| `test_parses_workflow_tool_use` | Extracts workflow name from Workflow tool call |
| `test_skips_malformed_lines` | Continues past bad JSON |
| `test_extracts_timestamp` | Correct ISO timestamp |
| `test_groups_by_session` | Events tagged with session ID |
| `test_generic_jsonl_format` | Parses simplified event format |

### test_counter.py

| Test | Asserts |
|------|---------|
| `test_counts_skill_invocations` | Correct total count |
| `test_counts_across_sessions` | Correct session count |
| `test_identifies_dead_artifacts` | Zero-count artifacts listed |
| `test_coverage_percentage` | Correct math |
| `test_no_events_all_dead` | 0% coverage |
| `test_all_used_full_coverage` | 100% coverage |

### test_reporter.py

| Test | Asserts |
|------|---------|
| `test_json_output_valid` | Parses as JSON, has required fields |
| `test_markdown_has_sections` | Contains expected headings |
| `test_terminal_no_crash` | Produces output without error |

---

## Integration Test

### test_integration.py

End-to-end using fixtures:

1. Point discovery at `tests/fixtures/repo/`
2. Point parser at `tests/fixtures/transcripts/`
3. Run full pipeline
4. Assert:
   - `graphify` has count > 0
   - `dead-skill` has count == 0
   - Coverage percentage matches expected
   - Dead artifacts list is correct

---

## Fixtures

```
tests/fixtures/
├── repo/                              # Fake repo with guidance
│   ├── .claude/
│   │   ├── skills/
│   │   │   ├── graphify/
│   │   │   │   └── SKILL.md
│   │   │   ├── code-review/
│   │   │   │   └── SKILL.md
│   │   │   └── dead-skill/
│   │   │       └── SKILL.md
│   │   └── workflows/
│   │       └── feature-dev.yaml
│   └── AGENTS.md
└── transcripts/
    ├── session-001.jsonl             # Uses graphify, Explore
    ├── session-002.jsonl             # Uses code-review, Plan
    └── session-003.jsonl             # Uses graphify, Explore, code-review
```

### Fixture transcript content (session-001.jsonl):
```json
{"type": "tool_use", "name": "Skill", "input": {"skill": "graphify"}, "timestamp": "2026-06-01T10:00:00Z"}
{"type": "tool_use", "name": "Agent", "input": {"subagent_type": "Explore", "prompt": "find endpoints"}, "timestamp": "2026-06-01T10:01:00Z"}
{"type": "tool_use", "name": "Bash", "input": {"command": "npm test"}, "timestamp": "2026-06-01T10:02:00Z"}
```

---

## Passing Criteria

MVP is complete when:

1. `pytest` passes with 0 failures
2. This works from a clean install:
   ```bash
   pip install -e .
   gi discover --repo tests/fixtures/repo --transcripts tests/fixtures/transcripts
   gi coverage --repo tests/fixtures/repo --transcripts tests/fixtures/transcripts
   ```
3. Output correctly shows:
   - graphify: 2 invocations
   - code-review: 2 invocations
   - dead-skill: 0 invocations (DEAD)
   - Coverage: 75% (or whatever the fixture math gives)
4. JSON output is valid and contains all fields from the data model
5. No runtime errors on empty repos or missing transcripts

---

## Running Tests

```bash
pytest                                    # all tests
pytest --cov=guidance_intel               # with coverage
pytest tests/test_discovery.py            # single module
pytest -x                                 # stop on first failure
```
