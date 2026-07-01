# Guidance Intelligence

**Code coverage, but for your AI guidance files.**

Find out which of your Skills, Agents, and Workflows are actually being used by AI coding agents — and which are dead weight.

```bash
pip install guidance-intel
cd my-repo
gi coverage
```

```
Guidance Coverage Report
========================

Skills (4 total)
  graphify          ██████████ 47 invocations  (high)
  code-review       ████░░░░░░ 12 invocations  (moderate)
  deep-research     ░░░░░░░░░░  0 invocations  (DEAD)
  simplify          █░░░░░░░░░  2 invocations  (low)

Agents (3 total)
  Explore           ██████████ 89 spawns
  Plan              ███░░░░░░░  8 spawns
  code-reviewer     ░░░░░░░░░░  0 spawns       (DEAD)

Overall Coverage: 64% (7/11 artifacts used)
Dead Guidance: 3 artifacts never triggered across 23 sessions
```

## Why

Teams invest significant effort writing CLAUDE.md, Skills, Agents, and Workflows. But today there's no way to know:

- Which skills are actually being invoked?
- Which agents are never spawned?
- Which workflows are dead code?
- What can be safely removed?

Guidance Intelligence answers these questions by analyzing real agent session transcripts.

## How It Works

1. **Discovers** all guidance artifacts in your repo (skills, agents, workflows)
2. **Parses** Claude Code session transcripts from `~/.claude/`
3. **Counts** how often each artifact is triggered
4. **Reports** coverage, dead guidance, and usage statistics

Zero configuration. No setup. No YAML files to write.

## Commands

```bash
gi coverage                    # Full coverage report (default)
gi discover                    # Show discovered artifacts and transcripts
gi dead                        # Show only unused/dead guidance
gi stats                       # Detailed per-artifact statistics

# Options
gi coverage --format json      # JSON output (for CI)
gi coverage --format md        # Markdown output (for sharing)
gi coverage --last 10          # Only last 10 sessions
gi coverage --transcripts ./   # Use custom transcript directory
```

## What It Discovers

Works with multiple directory structures and AI agent frameworks:

| Pattern | Type | Examples |
|---------|------|----------|
| `.claude/skills/*/SKILL.md` | Skills | Claude Code standard |
| `.agents/skills/**/*.md` | Skills | Custom agent frameworks |
| `skills/**/*.md` | Skills | Generic skills directory |
| `prompts/**/*.{md,txt,prompt}` | Skills | Prompt libraries |
| `AGENTS.md` | Agents | Agent definitions |
| `.claude/agents/*.md` | Agents | Individual agent files |
| `.agents/**/*.md` | Agents | Custom agent frameworks |
| `agents/**/*.md` | Agents | Generic agents directory |
| `.claude/workflows/*.{yaml,yml,md}` | Workflows | Claude Code workflows |
| `workflows/**/*.{yaml,yml,json}` | Workflows | Generic workflows |
| `tools/**/*.{yaml,json}` | Tools | LangChain/CrewAI style |
| `CLAUDE.md`, `INSTRUCTIONS.md` | Instructions | System prompts |

## Requirements

- Python 3.9+
- Works with Claude Code session transcripts
- Framework-agnostic: discovers guidance in any directory structure
- Also accepts generic JSONL event files for other agents

## How It Differs From Other Tools

| Tool | Purpose | Our difference |
|------|---------|---------------|
| agnix | Lint instruction file structure | We measure *usage*, not structure |
| cceval / AgentProbe | A/B test if instructions change behavior | We measure *real usage frequency* |
| Claude Code Auditor | Grade artifact quality (A-F) | We measure *actual invocation counts* |
| OpenAI eval-skills | QA: test if a skill works | We measure *if it's used in practice* |

They're linters and test runners. We're `pytest --cov` for guidance.

## Installation

```bash
pip install guidance-intel
```

## Development

```bash
git clone https://github.com/anthropics/guidance-intel.git
cd guidance-intel
pip install -e ".[dev]"
pytest
```

## License

MIT

